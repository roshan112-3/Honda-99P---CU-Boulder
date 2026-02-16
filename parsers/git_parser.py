"""
GitPython-based parser for extracting git metadata from a code repository.

Extracts: commits, timestamps, authors, diffs (per-commit file changes),
and blame (line-to-commit mapping) for knowledge graph construction and
test-failure risk prediction.
"""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Iterator, Optional

try:
    import git
except ImportError:
    raise ImportError("GitPython is required. Install with: pip install GitPython")


# ---------------------------------------------------------------------------
# Data structures for extracted metadata
# ---------------------------------------------------------------------------


@dataclass
class CommitInfo:
    """Metadata for a single commit."""

    sha: str
    short_sha: str
    author: str
    author_email: str
    timestamp: float  # Unix epoch
    timestamp_iso: str
    message: str
    message_subject: str  # First line of message
    parent_shas: list[str] = field(default_factory=list)


@dataclass
class DiffHunk:
    """A single hunk within a file diff."""

    old_start: int
    old_count: int
    new_start: int
    new_count: int
    content: str  # Unified diff content (with +/- prefixes)


@dataclass
class FileChange:
    """A file changed in a commit."""

    path: str
    change_type: str  # 'A' add, 'D' delete, 'M' modify, 'R' rename
    old_path: Optional[str] = None  # Set for renames
    hunks: list[DiffHunk] = field(default_factory=list)
    insertions: int = 0
    deletions: int = 0


@dataclass
class BlameLine:
    """Blame info for a single line in a file."""

    line_number: int
    content: str
    commit_sha: str
    author: str
    timestamp: float


# ---------------------------------------------------------------------------
# Git parser implementation
# ---------------------------------------------------------------------------


class GitParser:
    """
    Parser for extracting git metadata from a repository.
    """

    # File extensions to include when filtering (None = all files)
    DEFAULT_SOURCE_EXTENSIONS = {".cpp", ".h", ".py", ".sh", ".md", ".txt"}

    def __init__(self, repo_path: str | Path):
        """
        Initialize the parser with a path to the git repository root.

        Args:
            repo_path: Path to the repository (e.g., Data/ or .)
        """
        self.repo_path = Path(repo_path).resolve()
        self.repo = git.Repo(self.repo_path)

    def iter_commits(
        self,
        branch: str = "HEAD",
        max_count: Optional[int] = None,
        reverse: bool = False,
    ) -> Iterator[CommitInfo]:
        """
        Iterate over commits in the repository.

        Args:
            branch: Branch or ref to traverse (default: HEAD).
            max_count: Maximum number of commits to yield (None = all).
            reverse: If True, yield oldest first (chronological order).

        Yields:
            CommitInfo for each commit.
        """
        kwargs = {"rev": branch, "reverse": reverse}
        if max_count is not None:
            kwargs["max_count"] = max_count

        for commit in self.repo.iter_commits(**kwargs):
            yield CommitInfo(
                sha=commit.hexsha,
                short_sha=commit.hexsha[:7],
                author=commit.author.name,
                author_email=commit.author.email,
                timestamp=commit.committed_date,
                timestamp_iso=datetime.fromtimestamp(commit.committed_date).isoformat(),
                message=commit.message,
                message_subject=commit.message.split("\n")[0] if commit.message else "",
                parent_shas=[p.hexsha for p in commit.parents],
            )

    def get_commit_diff(
        self,
        commit_sha: str,
        file_extensions: Optional[set[str]] = None,
        create_patch: bool = True,
    ) -> list[FileChange]:
        """
        Get the diff for a specific commit (changes introduced by that commit).

        Args:
            commit_sha: Full or short SHA of the commit.
            file_extensions: If set, only include files with these extensions.
            create_patch: If True, include full hunk content; else just stats.

        Returns:
            List of FileChange objects.
        """
        file_extensions = file_extensions or self.DEFAULT_SOURCE_EXTENSIONS
        commit = self.repo.commit(commit_sha)

        if not commit.parents:
            # Root commit: diff against empty tree using the proper method
            diffs = commit.diff(git.NULL_TREE, create_patch=create_patch)
        else:
            parent = commit.parents[0]
            diffs = commit.diff(parent, create_patch=create_patch)

        changes = []
        for diff in diffs:
            # Handle None paths gracefully
            a_path = diff.a_path if diff.a_path else ""
            b_path = diff.b_path if diff.b_path else ""
            path = a_path if a_path and a_path != "/dev/null" else b_path
            if not path:
                continue
                
            ext = Path(path).suffix
            if file_extensions and ext not in file_extensions:
                continue

            change_type = _diff_change_type(diff)
            hunks = []
            if create_patch and diff.diff:
                hunks = _parse_diff_hunks(diff.diff.decode("utf-8", errors="replace"))

            changes.append(
                FileChange(
                    path=path,
                    change_type=change_type,
                    old_path=diff.a_path if change_type == "R" and diff.a_path != diff.b_path else None,
                    hunks=hunks,
                    insertions=getattr(diff, "insertions", None) or 0,
                    deletions=getattr(diff, "deletions", None) or 0,
                )
            )
        return changes

    def get_file_history(
        self,
        filepath: str,
        branch: str = "HEAD",
        max_commits: Optional[int] = None,
    ) -> list[tuple[str, str, float]]:
        """
        Get commit history for a specific file.

        Args:
            filepath: Path relative to repo root.
            branch: Branch to traverse.
            max_commits: Max commits to return (None = all).

        Returns:
            List of (sha, message_subject, timestamp) tuples, newest first.
        """
        result = []
        for commit in self.repo.iter_commits(branch, paths=filepath, max_count=max_commits):
            result.append((
                commit.hexsha,
                commit.message.split("\n")[0] if commit.message else "",
                commit.committed_date,
            ))
        return result

    def get_blame(
        self,
        filepath: str,
        rev: str = "HEAD",
    ) -> list[BlameLine]:
        """
        Get blame info for a file: which commit last modified each line.

        Args:
            filepath: Path relative to repo root.
            rev: Revision to blame (default: HEAD).

        Returns:
            List of BlameLine, one per line in the file.
        """
        try:
            blame_tuples = self.repo.blame(rev, filepath)
        except git.GitCommandError:
            return []

        lines = []
        line_num = 1
        for commit, line_contents in blame_tuples:
            # line_contents can be a list of lines or a single line
            contents = line_contents if isinstance(line_contents, list) else [line_contents]
            for content in contents:
                # content may be bytes
                text = content.decode("utf-8", errors="replace") if isinstance(content, bytes) else str(content)
                lines.append(
                    BlameLine(
                        line_number=line_num,
                        content=text.rstrip("\n"),
                        commit_sha=commit.hexsha,
                        author=commit.author.name,
                        timestamp=commit.committed_date,
                    )
                )
                line_num += 1
        return lines

    def get_all_commits_with_diffs(
        self,
        branch: str = "HEAD",
        max_count: Optional[int] = None,
        file_extensions: Optional[set[str]] = None,
    ) -> Iterator[tuple[CommitInfo, list[FileChange]]]:
        """
        Iterate over all commits with their diffs (convenience method).

        Yields:
            (CommitInfo, list[FileChange]) for each commit.
        """
        for commit in self.iter_commits(branch=branch, max_count=max_count):
            changes = self.get_commit_diff(commit.sha, file_extensions=file_extensions)
            yield commit, changes


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _diff_change_type(diff) -> str:
    """Map git diff change type to single letter."""
    if diff.new_file:
        return "A"
    if diff.deleted_file:
        return "D"
    if diff.renamed_file:
        return "R"
    return "M"


def _parse_diff_hunks(diff_text: str) -> list[DiffHunk]:
    """Parse unified diff text into DiffHunk objects."""
    hunks = []
    for block in diff_text.split("\n@@ "):
        if not block.strip() or not block.startswith("-") and "@@" not in block[:100]:
            # First block may not start with @@
            if "@@" in block:
                part = block[block.index("@@"):]
            else:
                continue
        else:
            part = block if block.lstrip().startswith("@") else "@@ " + block

        lines = part.split("\n")
        header = lines[0] if lines else ""
        if not header.startswith("@@"):
            continue

        # Parse @@ -old_start,old_count +new_start,new_count @@
        rest = header[2:].split("@@")[0].strip()
        try:
            old_part, new_part = rest.split(" ")
            old_start = int(old_part.split(",")[0].lstrip("-"))
            old_count = int(old_part.split(",")[1]) if "," in old_part else 1
            new_start = int(new_part.split(",")[0].lstrip("+"))
            new_count = int(new_part.split(",")[1]) if "," in new_part else 1
        except (ValueError, IndexError):
            continue

        content = "\n".join(lines[1:]) if len(lines) > 1 else ""
        hunks.append(
            DiffHunk(
                old_start=old_start,
                old_count=old_count,
                new_start=new_start,
                new_count=new_count,
                content=content,
            )
        )
    return hunks


# ---------------------------------------------------------------------------
# Serialization for JSON / knowledge graph ingestion
# ---------------------------------------------------------------------------


def commit_to_dict(c: CommitInfo) -> dict:
    """Convert CommitInfo to a JSON-serializable dict."""
    return {
        "sha": c.sha,
        "short_sha": c.short_sha,
        "author": c.author,
        "author_email": c.author_email,
        "timestamp": c.timestamp,
        "timestamp_iso": c.timestamp_iso,
        "message": c.message,
        "message_subject": c.message_subject,
        "parent_shas": c.parent_shas,
    }


def file_change_to_dict(fc: FileChange) -> dict:
    """Convert FileChange to a JSON-serializable dict."""
    return {
        "path": fc.path,
        "change_type": fc.change_type,
        "old_path": fc.old_path,
        "insertions": fc.insertions,
        "deletions": fc.deletions,
        "hunks": [
            {
                "old_start": h.old_start,
                "old_count": h.old_count,
                "new_start": h.new_start,
                "new_count": h.new_count,
                "content": h.content[:500] + "..." if len(h.content) > 500 else h.content,
            }
            for h in fc.hunks
        ],
    }


def blame_line_to_dict(bl: BlameLine) -> dict:
    """Convert BlameLine to a JSON-serializable dict."""
    return {
        "line_number": bl.line_number,
        "content": bl.content[:200] + "..." if len(bl.content) > 200 else bl.content,
        "commit_sha": bl.commit_sha,
        "author": bl.author,
        "timestamp": bl.timestamp,
    }


def generate_git_knowledge_base(parser: "GitParser", max_commits: int = 50) -> dict:
    """
    Generate a knowledge base output compatible with tree-sitter output.
    
    This extracts the most valuable git metadata for knowledge enrichment:
    - File ownership (who owns which files based on commits/blame)
    - Change history (when files were modified)
    - Commit context (why changes were made - from messages)
    - Change frequency (hotspots for potential bugs)
    """
    from datetime import datetime as dt
    from collections import defaultdict
    
    # Collect all commits
    commits = list(parser.iter_commits(max_count=max_commits))
    
    # File-level aggregations
    file_authors = defaultdict(lambda: defaultdict(int))  # file -> author -> count
    file_commits = defaultdict(list)  # file -> list of commit summaries
    file_last_modified = {}  # file -> {timestamp, author, message}
    
    # Process commits and their diffs
    for commit in commits:
        changes = parser.get_commit_diff(commit.sha, create_patch=False)
        for fc in changes:
            file_authors[fc.path][commit.author] += 1
            file_commits[fc.path].append({
                "sha": commit.short_sha,
                "author": commit.author,
                "timestamp_iso": commit.timestamp_iso,
                "message": commit.message_subject[:100]
            })
            # Track most recent modification
            if fc.path not in file_last_modified or commit.timestamp > file_last_modified[fc.path]["timestamp"]:
                file_last_modified[fc.path] = {
                    "timestamp": commit.timestamp,
                    "timestamp_iso": commit.timestamp_iso,
                    "author": commit.author,
                    "message": commit.message_subject
                }
    
    # Calculate file ownership (primary author per file)
    file_ownership = {}
    for filepath, authors in file_authors.items():
        if authors:
            primary_author = max(authors.items(), key=lambda x: x[1])
            file_ownership[filepath] = {
                "primary_author": primary_author[0],
                "commit_count": primary_author[1],
                "all_contributors": dict(authors)
            }
    
    # Get blame for key source files
    blame_by_file = {}
    source_files = [
        "firmware/sensors.cpp",
        "firmware/canbus.cpp",
        "firmware/gps.cpp",
        "cloud/ingest.py",
        "cloud/utils.py"
    ]
    for filepath in source_files:
        try:
            blame = parser.get_blame(filepath)
            if blame:
                # Summarize blame: group consecutive lines by author
                author_ranges = []
                current_author = None
                start_line = 1
                for bl in blame:
                    if bl.author != current_author:
                        if current_author:
                            author_ranges.append({
                                "author": current_author,
                                "lines": f"{start_line}-{bl.line_number - 1}"
                            })
                        current_author = bl.author
                        start_line = bl.line_number
                if current_author:
                    author_ranges.append({
                        "author": current_author,
                        "lines": f"{start_line}-{blame[-1].line_number}"
                    })
                blame_by_file[filepath] = {
                    "total_lines": len(blame),
                    "author_ranges": author_ranges[:10]  # Limit to first 10 ranges
                }
        except Exception:
            pass
    
    # Recent activity summary
    recent_commits = [
        {
            "sha": c.short_sha,
            "author": c.author,
            "timestamp_iso": c.timestamp_iso,
            "message": c.message_subject,
            "files_changed": len(parser.get_commit_diff(c.sha, create_patch=False))
        }
        for c in commits[:10]
    ]
    
    # Change frequency (hotspots)
    change_frequency = {
        path: len(commits_list)
        for path, commits_list in file_commits.items()
    }
    hotspots = sorted(change_frequency.items(), key=lambda x: x[1], reverse=True)[:10]
    
    return {
        "metadata": {
            "generated_at": dt.now().isoformat(),
            "repo": str(parser.repo_path),
            "analyzer": "GitPython Git Metadata Extractor v1.0",
            "branch": parser.repo.active_branch.name if not parser.repo.head.is_detached else "detached",
            "total_commits_analyzed": len(commits)
        },
        "summary": {
            "total_commits": len(commits),
            "total_authors": len(set(c.author for c in commits)),
            "files_with_history": len(file_commits),
            "files_with_blame": len(blame_by_file)
        },
        "file_ownership": file_ownership,
        "file_last_modified": file_last_modified,
        "blame_summary": blame_by_file,
        "recent_commits": recent_commits,
        "change_hotspots": [{"file": f, "changes": c} for f, c in hotspots],
        "file_commit_history": {
            path: commits_list[:5]  # Last 5 commits per file
            for path, commits_list in file_commits.items()
        }
    }


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def main():
    """Run the parser on the repository and generate knowledge base JSON."""
    import json

    # Look for .git in parent directory (project root)
    repo_path = Path(__file__).resolve().parent.parent
    if not (repo_path / ".git").exists():
        print(f"Error: No git repository found at {repo_path}")
        return

    parser = GitParser(repo_path)
    print(f"Repository: {parser.repo_path}")
    print(f"Branch: {parser.repo.active_branch.name if not parser.repo.head.is_detached else 'detached'}")
    print("-" * 60)

    commits = list(parser.iter_commits(max_count=5))
    print(f"Latest {len(commits)} commits:")
    for c in commits:
        print(f"  {c.short_sha} | {c.timestamp_iso} | {c.author} | {c.message_subject[:50]}")

    print("\n" + "-" * 60)
    if commits:
        c = commits[0]
        changes = parser.get_commit_diff(c.sha)
        print(f"Diff for {c.short_sha} ({len(changes)} files changed):")
        for fc in changes[:5]:
            print(f"  [{fc.change_type}] {fc.path} (+{fc.insertions} -{fc.deletions})")

    print("\n" + "-" * 60)
    for test_file in ["cloud/ingest.py", "firmware/sensors.cpp"]:
        if (repo_path / test_file).exists():
            blame = parser.get_blame(test_file)
            if blame:
                print(f"Blame for {test_file}: {len(blame)} lines")
                sample = blame[:3]
                for bl in sample:
                    print(f"  L{bl.line_number}: {bl.commit_sha[:7]} | {bl.content[:50]}...")
            break
    
    # Generate and save knowledge base JSON
    print("\n" + "-" * 60)
    print("Generating Git Knowledge Base...")
    kb = generate_git_knowledge_base(parser, max_commits=100)
    
    output_file = Path(__file__).parent / "git_knowledge_base.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(kb, f, indent=2, default=str)
    
    print(f"\n[OUTPUT] Git knowledge base saved to: {output_file}")
    print(f"  - {kb['summary']['total_commits']} commits analyzed")
    print(f"  - {kb['summary']['total_authors']} authors found")
    print(f"  - {kb['summary']['files_with_history']} files with history")
    print(f"  - {kb['summary']['files_with_blame']} files with blame")


if __name__ == "__main__":
    main()
