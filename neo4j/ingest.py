"""
Neo4j Knowledge Graph Ingestion
================================

Reads unified_knowledge_base.json and loads it into Neo4j as a
property graph optimized for test-failure risk prediction.

Node labels:
    File, Function, Class, Commit, Author, HSIField

Relationship types:
    DEFINED_IN, CALLS, BELONGS_TO, IMPLEMENTS_HSI,
    MODIFIED_BY, OWNED_BY, CONTRIBUTED_TO, COMMITTED

Usage:
    python neo4j/ingest.py                          # defaults
    python neo4j/ingest.py --uri bolt://host:7687   # custom URI
"""

import json
import argparse
from pathlib import Path
from datetime import datetime

from neo4j import GraphDatabase

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = "honda99p"
KB_PATH = Path(__file__).resolve().parent.parent / "unified_knowledge_base.json"

# Language detection helper
LANG_MAP = {
    ".cpp": "cpp", ".h": "cpp", ".c": "cpp",
    ".py": "python",
    ".sh": "shell",
    ".md": "markdown",
    ".txt": "text",
}


def detect_language(filepath: str) -> str:
    """Infer language from file extension."""
    ext = Path(filepath).suffix.lower()
    return LANG_MAP.get(ext, "unknown")


# ---------------------------------------------------------------------------
# Schema setup
# ---------------------------------------------------------------------------

def run_schema(tx):
    """Create constraints and indexes (idempotent)."""
    schema_file = Path(__file__).parent / "schema.cypher"
    if not schema_file.exists():
        print("  Warning: schema.cypher not found, skipping schema setup")
        return

    cypher = schema_file.read_text()
    # Split on semicolons, skip comments and blanks
    for stmt in cypher.split(";"):
        stmt = stmt.strip()
        if stmt and not stmt.startswith("//"):
            try:
                tx.run(stmt)
            except Exception as e:
                # Some constraints may already exist or not be supported in Community
                print(f"  Schema note: {e}")


# ---------------------------------------------------------------------------
# Node creation (MERGE = idempotent)
# ---------------------------------------------------------------------------

def create_file_nodes(tx, files):
    """Create File nodes."""
    tx.run("""
        UNWIND $files AS f
        MERGE (file:File {path: f.path})
        SET file.language = f.language,
            file.owner = f.owner,
            file.last_modified = f.last_modified,
            file.last_modified_by = f.last_modified_by,
            file.change_count = f.change_count
    """, files=files)


def create_function_nodes(tx, functions):
    """Create Function nodes."""
    tx.run("""
        UNWIND $functions AS fn
        MERGE (func:Function {uid: fn.uid})
        SET func.name = fn.name,
            func.full_name = fn.full_name,
            func.file = fn.file,
            func.line = fn.line,
            func.language = fn.language,
            func.return_type = fn.return_type,
            func.parameters = fn.parameters,
            func.owner = fn.owner,
            func.last_modified = fn.last_modified,
            func.last_modified_by = fn.last_modified_by,
            func.function_author = fn.function_author,
            func.total_file_changes = fn.total_file_changes
    """, functions=functions)


def create_class_nodes(tx, classes):
    """Create Class nodes."""
    tx.run("""
        UNWIND $classes AS c
        MERGE (cls:Class {name: c.name, file: c.file})
        SET cls.line_start = c.line_start,
            cls.line_end = c.line_end,
            cls.language = c.language
    """, classes=classes)


def create_commit_nodes(tx, commits):
    """Create Commit nodes."""
    tx.run("""
        UNWIND $commits AS cm
        MERGE (commit:Commit {sha: cm.sha})
        SET commit.author = cm.author,
            commit.timestamp = cm.timestamp,
            commit.message = cm.message,
            commit.files_changed = cm.files_changed
    """, commits=commits)


def create_author_nodes(tx, authors):
    """Create Author nodes."""
    tx.run("""
        UNWIND $authors AS a
        MERGE (author:Author {name: a.name})
    """, authors=authors)


def create_hsi_nodes(tx, hsi_fields):
    """Create HSIField nodes."""
    tx.run("""
        UNWIND $hsi_fields AS h
        MERGE (hsi:HSIField {name: h.name})
        SET hsi.byte_index = h.byte_index
    """, hsi_fields=hsi_fields)


# ---------------------------------------------------------------------------
# Relationship creation
# ---------------------------------------------------------------------------

def create_defined_in_rels(tx, rels):
    """Function -[:DEFINED_IN]-> File"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (fn:Function {uid: r.func_uid})
        MATCH (f:File {path: r.file_path})
        MERGE (fn)-[rel:DEFINED_IN]->(f)
        SET rel.line = r.line
    """, rels=rels)


def create_calls_rels(tx, rels):
    """Function -[:CALLS]-> Function"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (caller:Function {uid: r.caller_uid})
        MATCH (callee:Function {uid: r.callee_uid})
        MERGE (caller)-[rel:CALLS]->(callee)
        SET rel.file = r.file,
            rel.line = r.line
    """, rels=rels)


def create_belongs_to_rels(tx, rels):
    """Function -[:BELONGS_TO]-> Class"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (fn:Function {uid: r.func_uid})
        MATCH (cls:Class {name: r.class_name, file: r.class_file})
        MERGE (fn)-[:BELONGS_TO]->(cls)
    """, rels=rels)


def create_implements_hsi_rels(tx, rels):
    """Function -[:IMPLEMENTS_HSI]-> HSIField"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (fn:Function {uid: r.func_uid})
        MATCH (hsi:HSIField {name: r.hsi_field})
        MERGE (fn)-[rel:IMPLEMENTS_HSI]->(hsi)
        SET rel.file = r.file,
            rel.line = r.line,
            rel.value = r.value
    """, rels=rels)


def create_ownership_rels(tx, rels):
    """File -[:OWNED_BY]-> Author"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (f:File {path: r.file_path})
        MATCH (a:Author {name: r.author_name})
        MERGE (f)-[rel:OWNED_BY]->(a)
        SET rel.commit_count = r.commit_count
    """, rels=rels)


def create_contributed_rels(tx, rels):
    """Author -[:CONTRIBUTED_TO]-> File"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (a:Author {name: r.author_name})
        MATCH (f:File {path: r.file_path})
        MERGE (a)-[rel:CONTRIBUTED_TO]->(f)
        SET rel.commit_count = r.commit_count
    """, rels=rels)


def create_committed_rels(tx, rels):
    """Commit -[:MODIFIED]-> File"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (cm:Commit {sha: r.commit_sha})
        MATCH (f:File {path: r.file_path})
        MERGE (cm)-[:MODIFIED]->(f)
    """, rels=rels)


def create_author_committed_rels(tx, rels):
    """Author -[:COMMITTED]-> Commit"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (a:Author {name: r.author_name})
        MATCH (cm:Commit {sha: r.commit_sha})
        MERGE (a)-[:COMMITTED]->(cm)
    """, rels=rels)


# ---------------------------------------------------------------------------
# Scenario node/relationship creation
# ---------------------------------------------------------------------------

def create_scenario_nodes(tx, scenarios):
    """Create Scenario nodes."""
    tx.run("""
        UNWIND $scenarios AS s
        MERGE (sc:Scenario {id: s.id})
        SET sc.title = s.title,
            sc.param_name = s.param_name,
            sc.param_before = s.param_before,
            sc.param_after = s.param_after,
            sc.param_type = s.param_type,
            sc.param_is_safety_critical = s.param_is_safety_critical
    """, scenarios=scenarios)


def create_scenario_commit_nodes(tx, commits):
    """Create ScenarioCommit nodes."""
    tx.run("""
        UNWIND $commits AS c
        MERGE (sc:ScenarioCommit {tag: c.tag})
        SET sc.author = c.author,
            sc.role = c.role,
            sc.artifact = c.artifact,
            sc.timing = c.timing,
            sc.scenario_id = c.scenario_id,
            sc.file = c.file
    """, commits=commits)


def create_test_label_nodes(tx, labels):
    """Create TestLabel nodes (labeled test examples for ML)."""
    tx.run("""
        UNWIND $labels AS l
        MERGE (tl:TestLabel {id: l.id})
        SET tl.test = l.test,
            tl.label = l.label,
            tl.shortest_path = l.shortest_path,
            tl.hw_sw_sync_lag_days = l.hw_sw_sync_lag_days,
            tl.downstream_test_count = l.downstream_test_count,
            tl.churn_rate = l.churn_rate,
            tl.cofailure_count = l.cofailure_count,
            tl.is_cross_boundary_change = l.is_cross_boundary_change,
            tl.author_is_hw_team = l.author_is_hw_team,
            tl.param_is_safety_critical = l.param_is_safety_critical,
            tl.scenario_id = l.scenario_id,
            tl.parameter_name = l.parameter_name
    """, labels=labels)


def create_sc_commit_author_rels(tx, rels):
    """ScenarioCommit -[:AUTHORED_BY]-> Author"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (sc:ScenarioCommit {tag: r.tag})
        MATCH (a:Author {name: r.author_name})
        MERGE (sc)-[:AUTHORED_BY]->(a)
    """, rels=rels)


def create_sc_commit_scenario_rels(tx, rels):
    """ScenarioCommit -[:PART_OF]-> Scenario"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (sc:ScenarioCommit {tag: r.tag})
        MATCH (s:Scenario {id: r.scenario_id})
        MERGE (sc)-[:PART_OF]->(s)
    """, rels=rels)


def create_sc_commit_file_rels(tx, rels):
    """ScenarioCommit -[:MODIFIES]-> File"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (sc:ScenarioCommit {tag: r.tag})
        MATCH (f:File {path: r.file_path})
        MERGE (sc)-[:MODIFIES]->(f)
    """, rels=rels)


def create_test_label_scenario_rels(tx, rels):
    """TestLabel -[:OBSERVED_IN]-> Scenario"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (tl:TestLabel {id: r.test_label_id})
        MATCH (s:Scenario {id: r.scenario_id})
        MERGE (tl)-[:OBSERVED_IN]->(s)
    """, rels=rels)


def create_test_label_function_rels(tx, rels):
    """TestLabel -[:LABELS]-> Function"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (tl:TestLabel {id: r.test_label_id})
        MATCH (fn:Function {uid: r.func_uid})
        MERGE (tl)-[:LABELS]->(fn)
    """, rels=rels)


# ---------------------------------------------------------------------------
# Constant node creation (scenario parameters = changed constants)
# ---------------------------------------------------------------------------

def create_constant_nodes(tx, constants):
    """Create Constant nodes from scenario parameters."""
    tx.run("""
        UNWIND $constants AS k
        MERGE (c:Constant {name: k.name})
        SET c.before_value = k.before_value,
            c.after_value = k.after_value,
            c.type = k.type,
            c.is_safety_critical = k.is_safety_critical,
            c.scenario_id = k.scenario_id,
            c.scenario_title = k.scenario_title
    """, constants=constants)


def create_constant_scenario_rels(tx, rels):
    """Constant -[:CHANGED_IN]-> Scenario"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (k:Constant {name: r.constant_name})
        MATCH (s:Scenario {id: r.scenario_id})
        MERGE (k)-[:CHANGED_IN]->(s)
    """, rels=rels)


def create_constant_file_rels(tx, rels):
    """Constant -[:AFFECTS]-> File (files modified in the scenario)"""
    tx.run("""
        UNWIND $rels AS r
        MATCH (k:Constant {name: r.constant_name})
        MATCH (f:File {path: r.file_path})
        MERGE (k)-[:AFFECTS]->(f)
    """, rels=rels)


# ---------------------------------------------------------------------------
# Data preparation from unified KB
# ---------------------------------------------------------------------------

def prepare_data(kb: dict) -> dict:
    """
    Transform unified_knowledge_base.json into Neo4j-ready batch parameters.
    Returns dict of lists ready for Cypher UNWIND.
    """
    data = {
        "files": [],
        "functions": [],
        "classes": [],
        "commits": [],
        "authors": [],
        "hsi_fields": [],
        "defined_in": [],
        "calls": [],
        "belongs_to": [],
        "implements_hsi": [],
        "ownership": [],
        "contributed": [],
        "committed": [],
        "author_committed": [],
    }

    author_names = set()
    file_paths = set()
    # Maps for resolving callees to their UIDs
    func_name_to_uid = {}   # full_name -> uid
    func_short_to_uid = {}  # short name -> uid (fallback)

    # ------------------------------------------------------------------
    # 1. Extract functions and files from functions_by_file
    # ------------------------------------------------------------------
    for filepath, functions in kb.get("functions_by_file", {}).items():
        lang = detect_language(filepath)
        git_ctx_sample = functions[0].get("git_context", {}) if functions else {}

        # File node
        if filepath not in file_paths:
            file_paths.add(filepath)
            data["files"].append({
                "path": filepath,
                "language": lang,
                "owner": git_ctx_sample.get("file_owner"),
                "last_modified": git_ctx_sample.get("last_modified"),
                "last_modified_by": git_ctx_sample.get("last_modified_by"),
                "change_count": git_ctx_sample.get("total_file_changes", 0),
            })

        # Collect contributors as authors
        for contributor in git_ctx_sample.get("contributors", []):
            author_names.add(contributor)

        # Function nodes
        for func in functions:
            git_ctx = func.get("git_context", {})
            full_name = func["name"]
            uid = f"{filepath}::{full_name}"
            params = func.get("parameters", [])
            param_str = ", ".join(params) if isinstance(params, list) else str(params)

            data["functions"].append({
                "uid": uid,
                "name": full_name.split("::")[-1] if "::" in full_name else full_name,
                "full_name": full_name,
                "file": filepath,
                "line": func.get("line", 0),
                "language": lang,
                "return_type": func.get("return_type"),
                "parameters": param_str,
                "owner": git_ctx.get("file_owner"),
                "last_modified": git_ctx.get("last_modified"),
                "last_modified_by": git_ctx.get("last_modified_by"),
                "function_author": git_ctx.get("function_author"),
                "total_file_changes": git_ctx.get("total_file_changes", 0),
            })

            # DEFINED_IN relationship
            data["defined_in"].append({
                "func_uid": uid,
                "file_path": filepath,
                "line": func.get("line", 0),
            })

            # Track for call resolution
            func_name_to_uid[full_name] = uid
            short = full_name.split("::")[-1] if "::" in full_name else full_name
            func_short_to_uid[short] = uid  # last wins, but good enough

    # ------------------------------------------------------------------
    # 2. Classes
    # ------------------------------------------------------------------
    class_file_map = {}  # class_name -> file (for BELONGS_TO matching)
    for cls in kb.get("classes", []):
        data["classes"].append({
            "name": cls["name"],
            "file": cls["file"],
            "line_start": cls.get("line_start", 0),
            "line_end": cls.get("line_end", 0),
            "language": cls.get("language", "unknown"),
        })
        class_file_map[cls["name"]] = cls["file"]

        # Also register file
        if cls["file"] not in file_paths:
            file_paths.add(cls["file"])
            data["files"].append({
                "path": cls["file"],
                "language": detect_language(cls["file"]),
                "owner": None, "last_modified": None,
                "last_modified_by": None, "change_count": 0,
            })

    # ------------------------------------------------------------------
    # 3. Relationships from the relationships array
    # ------------------------------------------------------------------
    for rel in kb.get("relationships", []):
        rel_type = rel["relation"]
        source = rel["source"]
        target = rel["target"]
        meta = rel.get("metadata", {})

        if rel_type == "CALLS":
            caller_uid = func_name_to_uid.get(source) or func_short_to_uid.get(source)
            callee_uid = func_name_to_uid.get(target) or func_short_to_uid.get(target)
            if caller_uid and callee_uid:
                data["calls"].append({
                    "caller_uid": caller_uid,
                    "callee_uid": callee_uid,
                    "file": meta.get("file", ""),
                    "line": meta.get("line", 0),
                })

        elif rel_type == "BELONGS_TO":
            func_uid = func_name_to_uid.get(source) or func_short_to_uid.get(source)
            class_file = class_file_map.get(target)
            if func_uid and class_file:
                data["belongs_to"].append({
                    "func_uid": func_uid,
                    "class_name": target,
                    "class_file": class_file,
                })

        elif rel_type == "IMPLEMENTS_HSI":
            func_uid = func_name_to_uid.get(source) or func_short_to_uid.get(source)
            if func_uid:
                data["implements_hsi"].append({
                    "func_uid": func_uid,
                    "hsi_field": target,
                    "file": meta.get("file", ""),
                    "line": meta.get("line", 0),
                    "value": meta.get("value", ""),
                })

    # ------------------------------------------------------------------
    # 4. HSI fields
    # ------------------------------------------------------------------
    hsi_byte_map = {
        "version": 0, "sensor_id": 1,
        "temperature_raw_high": 2, "temperature_raw_low": 3,
        "pressure_raw_high": 4, "pressure_raw_low": 5,
        "humidity_raw_high": 6, "humidity_raw_low": 7,
        "fuel_raw_high": 8, "fuel_raw_low": 9,
        "status_flags": 10, "checksum": 11,
    }
    for field_name in kb.get("hsi_traceability", {}).keys():
        short_name = field_name.split(".")[-1] if "." in field_name else field_name
        data["hsi_fields"].append({
            "name": field_name,
            "byte_index": hsi_byte_map.get(short_name, -1),
        })

    # ------------------------------------------------------------------
    # 5. Git insights: commits, authors, ownership, modifications
    # ------------------------------------------------------------------
    git_insights = kb.get("git_insights", {})

    # Commits
    for cm in git_insights.get("recent_commits", []):
        data["commits"].append({
            "sha": cm["sha"],
            "author": cm.get("author", "unknown"),
            "timestamp": cm.get("timestamp_iso", ""),
            "message": cm.get("message", ""),
            "files_changed": cm.get("files_changed", 0),
        })
        author_names.add(cm.get("author", "unknown"))

        # Author -[:COMMITTED]-> Commit
        data["author_committed"].append({
            "author_name": cm.get("author", "unknown"),
            "commit_sha": cm["sha"],
        })

    # File ownership
    for filepath, info in git_insights.get("file_ownership", {}).items():
        # Ensure file node exists
        if filepath not in file_paths:
            file_paths.add(filepath)
            data["files"].append({
                "path": filepath,
                "language": detect_language(filepath),
                "owner": info.get("primary_author"),
                "last_modified": None,
                "last_modified_by": None,
                "change_count": info.get("commit_count", 0),
            })

        # OWNED_BY
        primary = info.get("primary_author")
        if primary:
            author_names.add(primary)
            data["ownership"].append({
                "file_path": filepath,
                "author_name": primary,
                "commit_count": info.get("commit_count", 0),
            })

        # CONTRIBUTED_TO for all contributors
        for contrib, count in info.get("all_contributors", {}).items():
            author_names.add(contrib)
            data["contributed"].append({
                "author_name": contrib,
                "file_path": filepath,
                "commit_count": count,
            })

    # File last modified -> Commit MODIFIED File
    for filepath, info in git_insights.get("file_last_modified", {}).items():
        # We don't have exact commit SHA for last modified, skip if not available
        pass

    # ------------------------------------------------------------------
    # 6. Authors (from git + scenarios)
    # ------------------------------------------------------------------
    for name in author_names:
        data["authors"].append({"name": name})

    # Also add scenario authors
    scenario_data = kb.get("scenario_data", {})
    for author_name in scenario_data.get("authors", []):
        author_names.add(author_name)
        data["authors"].append({"name": author_name})
    # Deduplicate authors
    seen = set()
    deduped = []
    for a in data["authors"]:
        if a["name"] not in seen:
            seen.add(a["name"])
            deduped.append(a)
    data["authors"] = deduped

    # ------------------------------------------------------------------
    # 7. Scenario data (from Data/docs/change_risk_scenarios.json)
    # ------------------------------------------------------------------
    data["scenarios"] = []
    data["scenario_commits_list"] = []
    data["labeled_examples"] = []
    data["sc_commit_to_author"] = []
    data["sc_commit_to_scenario"] = []
    data["sc_commit_to_file"] = []
    data["test_label_to_scenario"] = []
    data["test_label_to_function"] = []
    data["constants"] = []
    data["constant_to_scenario"] = []
    data["constant_to_file"] = []

    for scenario in scenario_data.get("scenarios", []):
        param = scenario.get("parameter", {})
        data["scenarios"].append({
            "id": scenario["id"],
            "title": scenario["title"],
            "param_name": param.get("name"),
            "param_before": str(param.get("before", "")),
            "param_after": str(param.get("after", "")),
            "param_type": param.get("type"),
            "param_is_safety_critical": param.get("param_is_safety_critical", 0),
        })

        # Create Constant node from scenario parameter
        if param.get("name"):
            data["constants"].append({
                "name": param["name"],
                "before_value": str(param.get("before", "")),
                "after_value": str(param.get("after", "")),
                "type": param.get("type", "unknown"),
                "is_safety_critical": param.get("param_is_safety_critical", 0),
                "scenario_id": scenario["id"],
                "scenario_title": scenario["title"],
            })
            data["constant_to_scenario"].append({
                "constant_name": param["name"],
                "scenario_id": scenario["id"],
            })

    # Normalize scenario file paths to match File nodes (backslash on Windows)
    def _norm_scenario_path(p):
        """Convert forward slashes to OS-native path separators."""
        if p:
            return str(Path(p))
        return p

    for sc in scenario_data.get("commits", []):
        sc_file = _norm_scenario_path(sc.get("file"))
        data["scenario_commits_list"].append({
            "tag": sc["tag"],
            "author": sc["author"],
            "role": sc["role"],
            "artifact": sc["artifact"],
            "timing": sc.get("timing", ""),
            "scenario_id": sc["scenario_id"],
            "file": sc_file,
        })
        # ScenarioCommit -> Author
        data["sc_commit_to_author"].append({
            "tag": sc["tag"],
            "author_name": sc["author"],
        })
        # ScenarioCommit -> Scenario
        data["sc_commit_to_scenario"].append({
            "tag": sc["tag"],
            "scenario_id": sc["scenario_id"],
        })
        # ScenarioCommit -> File (if file mapping exists)
        if sc_file:
            data["sc_commit_to_file"].append({
                "tag": sc["tag"],
                "file_path": sc_file,
            })

    # Build Constant -> File relationships from scenario commits
    # Group commits by scenario to link each constant to its affected files
    scenario_to_param = {}
    for scenario in scenario_data.get("scenarios", []):
        param = scenario.get("parameter", {})
        if param.get("name"):
            scenario_to_param[scenario["id"]] = param["name"]

    seen_const_file = set()
    for sc in scenario_data.get("commits", []):
        constant_name = scenario_to_param.get(sc.get("scenario_id"))
        sc_file = _norm_scenario_path(sc.get("file"))
        if constant_name and sc_file:
            key = (constant_name, sc_file)
            if key not in seen_const_file:
                seen_const_file.add(key)
                data["constant_to_file"].append({
                    "constant_name": constant_name,
                    "file_path": sc_file,
                })

    for i, ex in enumerate(scenario_data.get("labeled_examples", [])):
        ex_id = f"{ex['scenario_id']}::{ex['test']}"
        data["labeled_examples"].append({
            "id": ex_id,
            "test": ex["test"],
            "label": ex.get("label", 0),
            "shortest_path": ex.get("shortest_path"),
            "hw_sw_sync_lag_days": ex.get("hw_sw_sync_lag_days", 0),
            "downstream_test_count": ex.get("downstream_test_count", 0),
            "churn_rate": ex.get("churn_rate", 0),
            "cofailure_count": ex.get("cofailure_count", 0),
            "is_cross_boundary_change": ex.get("is_cross_boundary_change", 0),
            "author_is_hw_team": ex.get("author_is_hw_team", 0),
            "param_is_safety_critical": ex.get("param_is_safety_critical", 0),
            "scenario_id": ex["scenario_id"],
            "parameter_name": ex.get("parameter_name"),
        })
        # TestLabel -> Scenario
        data["test_label_to_scenario"].append({
            "test_label_id": ex_id,
            "scenario_id": ex["scenario_id"],
        })
        # TestLabel -> Function (match test function name)
        # Find the function uid for this test
        test_func_uid = None
        for fn in data["functions"]:
            if fn["name"] == ex["test"]:
                test_func_uid = fn["uid"]
                break
        if test_func_uid:
            data["test_label_to_function"].append({
                "test_label_id": ex_id,
                "func_uid": test_func_uid,
            })

    return data


# ---------------------------------------------------------------------------
# Main ingestion
# ---------------------------------------------------------------------------

def ingest(uri: str, user: str, password: str, kb_path: Path):
    """Run the full ingestion pipeline."""
    print("=" * 70)
    print("  NEO4J KNOWLEDGE GRAPH INGESTION")
    print("=" * 70)

    # Load KB
    print(f"\n[1/4] Loading knowledge base from {kb_path.name}...")
    with open(kb_path, "r", encoding="utf-8") as f:
        kb = json.load(f)

    # Prepare data
    print("[2/4] Preparing graph data...")
    data = prepare_data(kb)

    print(f"  Nodes to create:")
    print(f"    Files:           {len(data['files'])}")
    print(f"    Functions:       {len(data['functions'])}")
    print(f"    Classes:         {len(data['classes'])}")
    print(f"    Commits:         {len(data['commits'])}")
    print(f"    Authors:         {len(data['authors'])}")
    print(f"    HSI Fields:      {len(data['hsi_fields'])}")
    print(f"    Scenarios:       {len(data['scenarios'])}")
    print(f"    ScenarioCommits: {len(data['scenario_commits_list'])}")
    print(f"    TestLabels:      {len(data['labeled_examples'])}")
    print(f"  Relationships to create:")
    print(f"    DEFINED_IN:     {len(data['defined_in'])}")
    print(f"    CALLS:          {len(data['calls'])}")
    print(f"    BELONGS_TO:     {len(data['belongs_to'])}")
    print(f"    IMPLEMENTS_HSI: {len(data['implements_hsi'])}")
    print(f"    OWNED_BY:       {len(data['ownership'])}")
    print(f"    CONTRIBUTED_TO: {len(data['contributed'])}")
    print(f"    COMMITTED:      {len(data['author_committed'])}")
    print(f"    AUTHORED_BY:    {len(data['sc_commit_to_author'])}")
    print(f"    PART_OF:        {len(data['sc_commit_to_scenario'])}")
    print(f"    MODIFIES:       {len(data['sc_commit_to_file'])}")
    print(f"    OBSERVED_IN:    {len(data['test_label_to_scenario'])}")
    print(f"    LABELS:         {len(data['test_label_to_function'])}")
    print(f"    Constants:      {len(data['constants'])}")
    print(f"    CHANGED_IN:     {len(data['constant_to_scenario'])}")
    print(f"    AFFECTS:        {len(data['constant_to_file'])}")

    # Connect to Neo4j
    print(f"\n[3/4] Connecting to Neo4j at {uri}...")
    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        driver.verify_connectivity()
        print("  Connected successfully!")
    except Exception as e:
        print(f"  ERROR: Cannot connect to Neo4j: {e}")
        print("  Make sure Neo4j is running.")
        return

    # Ingest
    print("\n[4/4] Ingesting into Neo4j...")

    with driver.session() as session:
        # Schema
        print("  Setting up schema (constraints & indexes)...")
        try:
            session.execute_write(run_schema)
        except Exception as e:
            print(f"  Schema warning (non-fatal): {e}")

        # Nodes
        print("  Creating File nodes...")
        session.execute_write(create_file_nodes, data["files"])

        print("  Creating Function nodes...")
        session.execute_write(create_function_nodes, data["functions"])

        print("  Creating Class nodes...")
        session.execute_write(create_class_nodes, data["classes"])

        print("  Creating Commit nodes...")
        session.execute_write(create_commit_nodes, data["commits"])

        print("  Creating Author nodes...")
        session.execute_write(create_author_nodes, data["authors"])

        print("  Creating HSIField nodes...")
        session.execute_write(create_hsi_nodes, data["hsi_fields"])

        # Relationships
        print("  Creating DEFINED_IN relationships...")
        session.execute_write(create_defined_in_rels, data["defined_in"])

        print("  Creating CALLS relationships...")
        session.execute_write(create_calls_rels, data["calls"])

        print("  Creating BELONGS_TO relationships...")
        session.execute_write(create_belongs_to_rels, data["belongs_to"])

        print("  Creating IMPLEMENTS_HSI relationships...")
        session.execute_write(create_implements_hsi_rels, data["implements_hsi"])

        print("  Creating OWNED_BY relationships...")
        session.execute_write(create_ownership_rels, data["ownership"])

        print("  Creating CONTRIBUTED_TO relationships...")
        session.execute_write(create_contributed_rels, data["contributed"])

        print("  Creating COMMITTED relationships...")
        session.execute_write(create_author_committed_rels, data["author_committed"])

        # Scenario nodes
        if data["scenarios"]:
            print("  Creating Scenario nodes...")
            session.execute_write(create_scenario_nodes, data["scenarios"])

            print("  Creating ScenarioCommit nodes...")
            session.execute_write(create_scenario_commit_nodes, data["scenario_commits_list"])

            print("  Creating TestLabel nodes...")
            session.execute_write(create_test_label_nodes, data["labeled_examples"])

            print("  Creating AUTHORED_BY relationships...")
            session.execute_write(create_sc_commit_author_rels, data["sc_commit_to_author"])

            print("  Creating PART_OF relationships...")
            session.execute_write(create_sc_commit_scenario_rels, data["sc_commit_to_scenario"])

            print("  Creating MODIFIES relationships...")
            session.execute_write(create_sc_commit_file_rels, data["sc_commit_to_file"])

            print("  Creating OBSERVED_IN relationships...")
            session.execute_write(create_test_label_scenario_rels, data["test_label_to_scenario"])

            print("  Creating LABELS relationships...")
            session.execute_write(create_test_label_function_rels, data["test_label_to_function"])

        # Constant nodes
        if data["constants"]:
            print("  Creating Constant nodes...")
            session.execute_write(create_constant_nodes, data["constants"])

            print("  Creating CHANGED_IN relationships...")
            session.execute_write(create_constant_scenario_rels, data["constant_to_scenario"])

            print("  Creating AFFECTS relationships...")
            session.execute_write(create_constant_file_rels, data["constant_to_file"])

    # Verify
    print("\n" + "-" * 70)
    print("VERIFICATION")
    print("-" * 70)

    with driver.session() as session:
        result = session.run("""
            MATCH (n)
            WITH labels(n)[0] AS label, count(*) AS cnt
            RETURN label, cnt ORDER BY cnt DESC
        """)
        print("\n  Node counts:")
        for record in result:
            print(f"    {record['label']:15s}: {record['cnt']}")

        result = session.run("""
            MATCH ()-[r]->()
            WITH type(r) AS rel_type, count(*) AS cnt
            RETURN rel_type, cnt ORDER BY cnt DESC
        """)
        print("\n  Relationship counts:")
        for record in result:
            print(f"    {record['rel_type']:20s}: {record['cnt']}")

    driver.close()

    print("\n" + "=" * 70)
    print("  INGESTION COMPLETE")
    print("=" * 70)
    print(f"\n  Neo4j Browser: http://localhost:7474")
    print(f"  Try: MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 50")
    print()


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Ingest knowledge graph into Neo4j")
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER, help="Neo4j username")
    parser.add_argument("--password", default=DEFAULT_PASSWORD, help="Neo4j password")
    parser.add_argument("--kb", default=str(KB_PATH), help="Path to unified_knowledge_base.json")
    args = parser.parse_args()

    ingest(args.uri, args.user, args.password, Path(args.kb))


if __name__ == "__main__":
    main()
