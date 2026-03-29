"""
Merge Knowledge Base
====================

Combines the tree-sitter code analysis with git metadata
to create a unified, enriched knowledge base.

Tree-sitter provides:
- Function definitions and locations
- Call graph relationships
- HSI traceability
- Class/struct definitions

GitPython provides:
- File ownership (who owns code)
- Change history (when code was modified)
- Commit context (why changes were made)
- Change hotspots (frequently modified areas)
- Line-level blame (authorship per line)

The merged output enriches code entities with version control context.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, Optional


def load_json(filepath: Path) -> Optional[Dict[str, Any]]:
    """Load a JSON file, return None if not found."""
    if filepath.exists():
        with open(filepath, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None


def normalize_path(path: str) -> str:
    """Normalize path separators for consistent matching."""
    return path.replace('\\', '/').strip('/')


def merge_knowledge_bases(
    treesitter_kb: Dict[str, Any],
    git_kb: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Merge tree-sitter code analysis with git metadata.
    
    Returns a unified knowledge base with enriched entities.
    """
    
    # Normalize git KB paths for lookup
    git_ownership = {
        normalize_path(k): v 
        for k, v in git_kb.get('file_ownership', {}).items()
    }
    git_last_modified = {
        normalize_path(k): v 
        for k, v in git_kb.get('file_last_modified', {}).items()
    }
    git_blame = {
        normalize_path(k): v 
        for k, v in git_kb.get('blame_summary', {}).items()
    }
    git_history = {
        normalize_path(k): v 
        for k, v in git_kb.get('file_commit_history', {}).items()
    }
    
    # Enrich functions with git metadata
    enriched_functions = {}
    for filepath, functions in treesitter_kb.get('functions_by_file', {}).items():
        norm_path = normalize_path(filepath)
        
        # Get git metadata for this file
        ownership = git_ownership.get(norm_path, {})
        last_mod = git_last_modified.get(norm_path, {})
        blame = git_blame.get(norm_path, {})
        history = git_history.get(norm_path, [])
        
        enriched_funcs = []
        for func in functions:
            enriched_func = {
                **func,
                "git_context": {
                    "file_owner": ownership.get("primary_author", "unknown"),
                    "contributors": list(ownership.get("all_contributors", {}).keys()),
                    "last_modified": last_mod.get("timestamp_iso"),
                    "last_modified_by": last_mod.get("author"),
                    "last_modified_reason": last_mod.get("message"),
                    "total_file_changes": ownership.get("commit_count", 0)
                }
            }
            
            # Try to find blame info for the function's line range
            if blame:
                func_line = func.get('line', 0)
                # Find which author range contains this function
                for author_range in blame.get('author_ranges', []):
                    lines = author_range.get('lines', '')
                    if '-' in lines:
                        start, end = map(int, lines.split('-'))
                        if start <= func_line <= end:
                            enriched_func['git_context']['function_author'] = author_range['author']
                            break
            
            enriched_funcs.append(enriched_func)
        
        enriched_functions[filepath] = enriched_funcs
    
    # Enrich relationships with authorship
    enriched_relationships = []
    for rel in treesitter_kb.get('relationships', []):
        enriched_rel = {**rel}
        
        # Add authorship context if available
        if 'metadata' in rel and 'file' in rel['metadata']:
            norm_path = normalize_path(rel['metadata']['file'])
            ownership = git_ownership.get(norm_path, {})
            enriched_rel['metadata']['file_owner'] = ownership.get('primary_author', 'unknown')
        
        enriched_relationships.append(enriched_rel)
    
    # Build unified output
    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "repo": treesitter_kb.get('metadata', {}).get('repo', 'Honda Repository'),
            "analyzers": [
                "Tree-sitter Code Analyzer v1.0",
                "GitPython Git Metadata Extractor v2.0"
            ],
            "merge_version": "2.0"
        },
        "summary": {
            # Code analysis summary
            "total_functions": treesitter_kb.get('summary', {}).get('total_functions', 0),
            "total_classes": treesitter_kb.get('summary', {}).get('total_classes', 0),
            "total_calls": treesitter_kb.get('summary', {}).get('total_calls', 0),
            "total_relationships": treesitter_kb.get('summary', {}).get('total_relationships', 0),
            # Git summary
            "total_commits": git_kb.get('summary', {}).get('total_commits', 0),
            "total_authors": git_kb.get('summary', {}).get('total_authors', 0),
            "files_with_history": git_kb.get('summary', {}).get('files_with_history', 0),
            # Scenario summary
            "total_scenarios": git_kb.get('summary', {}).get('total_scenarios', 0),
            "total_labeled_examples": git_kb.get('summary', {}).get('total_labeled_examples', 0),
        },

        # Enriched code entities
        "functions_by_file": enriched_functions,
        "call_graph": treesitter_kb.get('call_graph', {}),
        "hsi_traceability": treesitter_kb.get('hsi_traceability', {}),
        "classes": treesitter_kb.get('classes', []),
        "relationships": enriched_relationships,

        # Git-specific insights
        "git_insights": {
            "change_hotspots": git_kb.get('change_hotspots', []),
            "recent_commits": git_kb.get('recent_commits', []),
            "file_ownership": git_kb.get('file_ownership', {}),
            "file_last_modified": git_kb.get('file_last_modified', {})
        },

        # Scenario-based data (from Data/docs/change_risk_scenarios.json)
        "scenario_data": {
            "authors": git_kb.get('scenario_authors', []),
            "commits": git_kb.get('scenario_commits', []),
            "author_ownership": git_kb.get('author_ownership', {}),
            "scenarios": git_kb.get('scenarios', []),
            "labeled_examples": git_kb.get('labeled_examples', []),
        }
    }


def print_merge_report(unified: Dict[str, Any]):
    """Print a summary report of the merged knowledge base."""
    
    print("\n" + "=" * 70)
    print("           UNIFIED KNOWLEDGE BASE MERGE REPORT")
    print("=" * 70)
    
    summary = unified.get('summary', {})
    
    print("\n[CODE ANALYSIS]")
    print(f"  Functions:     {summary.get('total_functions', 0)}")
    print(f"  Classes:       {summary.get('total_classes', 0)}")
    print(f"  Call edges:    {summary.get('total_calls', 0)}")
    print(f"  Relationships: {summary.get('total_relationships', 0)}")
    
    print("\n[GIT METADATA]")
    print(f"  Commits analyzed: {summary.get('total_commits', 0)}")
    print(f"  Authors found:    {summary.get('total_authors', 0)}")
    print(f"  Files tracked:    {summary.get('files_with_history', 0)}")
    
    print("\n[ENRICHMENT EXAMPLES]")
    for filepath, functions in list(unified.get('functions_by_file', {}).items())[:2]:
        print(f"\n  {filepath}:")
        for func in functions[:2]:
            git_ctx = func.get('git_context', {})
            print(f"    {func.get('name')}()")
            print(f"      Owner: {git_ctx.get('file_owner', 'unknown')}")
            print(f"      Last modified: {git_ctx.get('last_modified', 'unknown')}")
            print(f"      Modified by: {git_ctx.get('last_modified_by', 'unknown')}")
    
    hotspots = unified.get('git_insights', {}).get('change_hotspots', [])
    if hotspots:
        print("\n[CHANGE HOTSPOTS] (Files most frequently modified)")
        for hs in hotspots[:5]:
            print(f"  {hs.get('file')}: {hs.get('changes')} changes")

    scenario = unified.get('scenario_data', {})
    if scenario.get('authors'):
        print(f"\n[SCENARIO DATA]")
        print(f"  Authors:          {', '.join(scenario['authors'])}")
        print(f"  Scenarios:        {len(scenario.get('scenarios', []))}")
        print(f"  Commits:          {len(scenario.get('commits', []))}")
        print(f"  Labeled examples: {len(scenario.get('labeled_examples', []))}")
        labels = scenario.get('labeled_examples', [])
        fail_count = sum(1 for ex in labels if ex.get('label') == 1)
        pass_count = sum(1 for ex in labels if ex.get('label') == 0)
        print(f"    - Failures (label=1): {fail_count}")
        print(f"    - Passes   (label=0): {pass_count}")

    print("\n" + "=" * 70)


def main():
    """Main entry point for merging knowledge bases."""
    
    # Script is now at root level
    root_dir = Path(__file__).parent
    parsers_dir = root_dir / "parsers"
    
    # Load knowledge bases
    print("Loading tree-sitter knowledge base...")
    treesitter_kb = load_json(parsers_dir / "ast_knowledge_base.json")
    
    print("Loading git knowledge base...")
    git_kb = load_json(parsers_dir / "git_history_knowledge_base.json")
    
    if not treesitter_kb:
        print("ERROR: AST knowledge base not found.")
        print("  Run: python parsers/tree_sitter.py")
        return
    
    if not git_kb:
        print("ERROR: Git history knowledge base not found.")
        print("  Run: python parsers/git_python.py")
        return
    
    # Merge
    print("Merging knowledge bases...")
    unified = merge_knowledge_bases(treesitter_kb, git_kb)
    
    # Save unified output at root level
    output_file = root_dir / "unified_knowledge_base.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(unified, f, indent=2, default=str)
    
    print(f"\n[OUTPUT] Unified knowledge base saved to: {output_file}")
    
    # Print report
    print_merge_report(unified)


if __name__ == "__main__":
    main()
