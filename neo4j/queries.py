"""
Neo4j Risk Prediction Queries
==============================

Cypher queries for traversing the knowledge graph to predict which
tests / functions are at risk when a specific line of code changes.

These queries power the "impact analysis" step:
    Code change -> affected functions -> transitive callees/callers
    -> risk-scored output ready for vectorization + ML + RAG.

Usage:
    python neo4j/queries.py --file Data/firmware/sensors.cpp --line 50
    python neo4j/queries.py --function "SensorManager::pack_latest"
"""

import argparse
import json
from pathlib import Path

from neo4j import GraphDatabase

DEFAULT_URI = "bolt://localhost:7687"
DEFAULT_USER = "neo4j"
DEFAULT_PASSWORD = "honda99p"


# ---------------------------------------------------------------------------
# Query 1: Find function at a given line in a file
# ---------------------------------------------------------------------------

QUERY_FUNCTION_AT_LINE = """
MATCH (fn:Function)
WHERE fn.file = $file_path
  AND fn.line <= $line_number
RETURN fn
ORDER BY fn.line DESC
LIMIT 1
"""

# ---------------------------------------------------------------------------
# Query 2: Direct impact — what does this function call? (1 hop)
# ---------------------------------------------------------------------------

QUERY_DIRECT_CALLEES = """
MATCH (fn:Function {uid: $func_uid})-[:CALLS]->(callee:Function)
RETURN DISTINCT callee.uid AS uid,
       callee.full_name AS name,
       callee.file AS file,
       callee.line AS line
"""

# ---------------------------------------------------------------------------
# Query 3: Direct impact — what calls this function? (1 hop reverse)
# ---------------------------------------------------------------------------

QUERY_DIRECT_CALLERS = """
MATCH (caller:Function)-[:CALLS]->(fn:Function {uid: $func_uid})
RETURN DISTINCT caller.uid AS uid,
       caller.full_name AS name,
       caller.file AS file,
       caller.line AS line
"""

# ---------------------------------------------------------------------------
# Query 4: Transitive impact — all reachable functions (variable depth)
# ---------------------------------------------------------------------------

QUERY_TRANSITIVE_IMPACT = """
MATCH path = (fn:Function {uid: $func_uid})-[:CALLS*1..5]->(reached:Function)
WITH reached, min(length(path)) AS distance
RETURN DISTINCT reached.uid AS uid,
       reached.full_name AS name,
       reached.file AS file,
       reached.line AS line,
       distance
ORDER BY distance, reached.file
"""

# ---------------------------------------------------------------------------
# Query 5: Reverse transitive — all functions that eventually call this one
# ---------------------------------------------------------------------------

QUERY_REVERSE_TRANSITIVE = """
MATCH path = (upstream:Function)-[:CALLS*1..5]->(fn:Function {uid: $func_uid})
WITH upstream, min(length(path)) AS distance
RETURN DISTINCT upstream.uid AS uid,
       upstream.full_name AS name,
       upstream.file AS file,
       upstream.line AS line,
       distance
ORDER BY distance, upstream.file
"""

# ---------------------------------------------------------------------------
# Query 6: Full risk blast radius — both directions + file ownership
# ---------------------------------------------------------------------------

QUERY_RISK_BLAST_RADIUS = """
// Collect downstream (called by changed function)
MATCH (fn:Function {uid: $func_uid})-[:CALLS*0..5]->(downstream:Function)
WITH fn, collect(DISTINCT downstream) AS down_list

// Collect upstream (callers of changed function)
OPTIONAL MATCH (upstream:Function)-[:CALLS*1..5]->(fn)
WITH fn, down_list, collect(DISTINCT upstream) AS up_list

// Combine both directions, exclude the origin function itself
WITH fn, down_list + up_list AS combined
UNWIND combined AS affected
WITH DISTINCT fn, affected
WHERE affected <> fn

// Get file and ownership info
OPTIONAL MATCH (affected)-[:DEFINED_IN]->(f:File)
OPTIONAL MATCH (f)-[:OWNED_BY]->(owner:Author)

// Compute hop distance via variable-length path (avoid shortestPath same-node error)
OPTIONAL MATCH p = (fn)-[:CALLS*1..10]-(affected)
WITH affected, f, owner,
     COALESCE(min(length(p)), 99) AS hop_distance,
     COALESCE(f.change_count, 0) AS change_freq

RETURN affected.uid AS function_uid,
       affected.full_name AS function_name,
       f.path AS file,
       owner.name AS file_owner,
       hop_distance,
       change_freq,
       toFloat(1.0) / toFloat(1.0 + hop_distance) + toFloat(change_freq) * 0.1 AS risk_score
ORDER BY risk_score DESC
"""

# ---------------------------------------------------------------------------
# Query 7: HSI traceability for affected functions
# ---------------------------------------------------------------------------

QUERY_HSI_IMPACT = """
MATCH (fn:Function {uid: $func_uid})-[:CALLS*0..3]->(reached:Function)
MATCH (reached)-[:IMPLEMENTS_HSI]->(hsi:HSIField)
RETURN DISTINCT hsi.name AS hsi_field,
       hsi.byte_index AS byte_index,
       reached.full_name AS implementing_function,
       reached.file AS file
ORDER BY hsi.byte_index
"""

# ---------------------------------------------------------------------------
# Query 8: Class-level impact — if function changes, what class is affected?
# ---------------------------------------------------------------------------

QUERY_CLASS_IMPACT = """
MATCH (fn:Function {uid: $func_uid})-[:CALLS*0..3]->(reached:Function)
MATCH (reached)-[:BELONGS_TO]->(cls:Class)
RETURN DISTINCT cls.name AS class_name,
       cls.file AS file,
       collect(DISTINCT reached.full_name) AS affected_methods
ORDER BY cls.name
"""

# ---------------------------------------------------------------------------
# Query 9: Author notification — who should review this change?
# ---------------------------------------------------------------------------

QUERY_AFFECTED_AUTHORS = """
MATCH (fn:Function {uid: $func_uid})-[:CALLS*0..5]->(reached:Function)
MATCH (reached)-[:DEFINED_IN]->(f:File)
MATCH (author:Author)-[:CONTRIBUTED_TO]->(f)
WITH author.name AS author, 
     count(DISTINCT reached) AS functions_affected,
     collect(DISTINCT f.path) AS files_affected
RETURN author, functions_affected, files_affected
ORDER BY functions_affected DESC
"""

# ---------------------------------------------------------------------------
# Query 10: Graph summary stats
# ---------------------------------------------------------------------------

QUERY_GRAPH_STATS = """
MATCH (n)
WITH labels(n)[0] AS label, count(*) AS count
RETURN label, count ORDER BY count DESC
UNION ALL
MATCH ()-[r]->()
WITH type(r) AS label, count(*) AS count
RETURN label, count ORDER BY count DESC
"""


# ---------------------------------------------------------------------------
# Runner
# ---------------------------------------------------------------------------

class RiskAnalyzer:
    """Runs risk prediction queries against Neo4j."""

    def __init__(self, uri: str, user: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))

    def close(self):
        self.driver.close()

    def _run_query(self, query: str, **params) -> list[dict]:
        with self.driver.session() as session:
            result = session.run(query, **params)
            return [dict(record) for record in result]

    def find_function_at_line(self, file_path: str, line: int) -> dict | None:
        """Find the function that contains a given line."""
        results = self._run_query(QUERY_FUNCTION_AT_LINE, file_path=file_path, line_number=line)
        if results:
            node = results[0]["fn"]
            return dict(node)
        return None

    def get_direct_callees(self, func_uid: str) -> list[dict]:
        return self._run_query(QUERY_DIRECT_CALLEES, func_uid=func_uid)

    def get_direct_callers(self, func_uid: str) -> list[dict]:
        return self._run_query(QUERY_DIRECT_CALLERS, func_uid=func_uid)

    def get_transitive_impact(self, func_uid: str) -> list[dict]:
        return self._run_query(QUERY_TRANSITIVE_IMPACT, func_uid=func_uid)

    def get_reverse_transitive(self, func_uid: str) -> list[dict]:
        return self._run_query(QUERY_REVERSE_TRANSITIVE, func_uid=func_uid)

    def get_risk_blast_radius(self, func_uid: str) -> list[dict]:
        return self._run_query(QUERY_RISK_BLAST_RADIUS, func_uid=func_uid)

    def get_hsi_impact(self, func_uid: str) -> list[dict]:
        return self._run_query(QUERY_HSI_IMPACT, func_uid=func_uid)

    def get_class_impact(self, func_uid: str) -> list[dict]:
        return self._run_query(QUERY_CLASS_IMPACT, func_uid=func_uid)

    def get_affected_authors(self, func_uid: str) -> list[dict]:
        return self._run_query(QUERY_AFFECTED_AUTHORS, func_uid=func_uid)

    def get_graph_stats(self) -> list[dict]:
        return self._run_query(QUERY_GRAPH_STATS)

    def full_risk_report(self, file_path: str = None, line: int = None, func_uid: str = None):
        """
        Generate a complete risk report for a code change.
        
        Specify either (file_path + line) or func_uid.
        """
        print("=" * 70)
        print("  TEST FAILURE RISK PREDICTION REPORT")
        print("=" * 70)

        # Resolve function
        if func_uid is None and file_path and line:
            func = self.find_function_at_line(file_path, line)
            if not func:
                print(f"\n  ERROR: No function found at {file_path}:{line}")
                return
            func_uid = func["uid"]
            print(f"\n  Changed: {func.get('full_name', func_uid)}")
            print(f"  File:    {file_path}")
            print(f"  Line:    {line}")
        elif func_uid:
            print(f"\n  Changed function: {func_uid}")
        else:
            print("\n  ERROR: Specify --file + --line OR --function")
            return

        # Direct callees
        print(f"\n{'─' * 70}")
        print("DIRECT CALLEES (functions this calls)")
        print(f"{'─' * 70}")
        callees = self.get_direct_callees(func_uid)
        if callees:
            for c in callees:
                print(f"  → {c['name']:40s} @ {c['file']}:{c['line']}")
        else:
            print("  (none)")

        # Direct callers
        print(f"\n{'─' * 70}")
        print("DIRECT CALLERS (functions that call this)")
        print(f"{'─' * 70}")
        callers = self.get_direct_callers(func_uid)
        if callers:
            for c in callers:
                print(f"  ← {c['name']:40s} @ {c['file']}:{c['line']}")
        else:
            print("  (none)")

        # Transitive impact
        print(f"\n{'─' * 70}")
        print("TRANSITIVE DOWNSTREAM (all reachable via calls, up to 5 hops)")
        print(f"{'─' * 70}")
        downstream = self.get_transitive_impact(func_uid)
        if downstream:
            for d in downstream:
                print(f"  [hop {d['distance']}] {d['name']:40s} @ {d['file']}")
        else:
            print("  (none)")

        # Reverse transitive
        print(f"\n{'─' * 70}")
        print("TRANSITIVE UPSTREAM (all functions that eventually call this)")
        print(f"{'─' * 70}")
        upstream = self.get_reverse_transitive(func_uid)
        if upstream:
            for u in upstream:
                print(f"  [hop {u['distance']}] {u['name']:40s} @ {u['file']}")
        else:
            print("  (none)")

        # HSI impact
        print(f"\n{'─' * 70}")
        print("HSI SPECIFICATION IMPACT")
        print(f"{'─' * 70}")
        hsi = self.get_hsi_impact(func_uid)
        if hsi:
            for h in hsi:
                print(f"  Byte {h['byte_index']:2d}: {h['hsi_field']:35s} via {h['implementing_function']}")
        else:
            print("  (no HSI fields affected)")

        # Class impact
        print(f"\n{'─' * 70}")
        print("CLASS IMPACT")
        print(f"{'─' * 70}")
        classes = self.get_class_impact(func_uid)
        if classes:
            for c in classes:
                print(f"  {c['class_name']:20s} @ {c['file']}")
                for m in c["affected_methods"]:
                    print(f"    ├── {m}")
        else:
            print("  (no classes affected)")

        # Risk blast radius
        print(f"\n{'─' * 70}")
        print("RISK-SCORED BLAST RADIUS (for ML feature input)")
        print(f"{'─' * 70}")
        blast = self.get_risk_blast_radius(func_uid)
        if blast:
            print(f"  {'Function':<45s} {'File':<35s} {'Hops':>4s} {'Risk':>6s}")
            print(f"  {'─'*45} {'─'*35} {'─'*4} {'─'*6}")
            for b in blast[:20]:
                name = b.get("function_name") or b.get("function_uid", "?")
                file = b.get("file") or "?"
                print(f"  {name:<45s} {file:<35s} {b['hop_distance']:>4d} {b['risk_score']:>6.2f}")
        else:
            print("  (no blast radius computed)")

        # Affected authors
        print(f"\n{'─' * 70}")
        print("AUTHORS TO NOTIFY")
        print(f"{'─' * 70}")
        authors = self.get_affected_authors(func_uid)
        if authors:
            for a in authors:
                print(f"  {a['author']:30s} ({a['functions_affected']} functions in {len(a['files_affected'])} files)")
        else:
            print("  (no authors found)")

        # Summary
        print(f"\n{'=' * 70}")
        total_affected = len(set(
            [c["uid"] for c in callees] +
            [c["uid"] for c in callers] +
            [d["uid"] for d in downstream] +
            [u["uid"] for u in upstream]
        ))
        print(f"  TOTAL FUNCTIONS IN BLAST RADIUS: {total_affected}")
        print(f"  TOTAL FILES AFFECTED:            {len(set(d.get('file','') for d in downstream + upstream + callees + callers))}")
        print(f"  HSI FIELDS AT RISK:              {len(hsi)}")
        print(f"  CLASSES IMPACTED:                {len(classes)}")
        print("=" * 70)

        return {
            "function_uid": func_uid,
            "direct_callees": callees,
            "direct_callers": callers,
            "downstream": downstream,
            "upstream": upstream,
            "hsi_impact": hsi,
            "class_impact": classes,
            "blast_radius": blast,
            "affected_authors": authors,
        }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Risk prediction query runner")
    parser.add_argument("--uri", default=DEFAULT_URI)
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)

    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--function", help="Function UID (e.g., 'Data/firmware/sensors.cpp::SensorManager::pack_latest')")
    group.add_argument("--file", help="File path (use with --line)")

    parser.add_argument("--line", type=int, help="Line number in file")
    parser.add_argument("--stats", action="store_true", help="Print graph stats and exit")
    parser.add_argument("--json", help="Save report as JSON to this path")

    args = parser.parse_args()

    analyzer = RiskAnalyzer(args.uri, args.user, args.password)

    try:
        if args.stats:
            stats = analyzer.get_graph_stats()
            print("\nGraph Statistics:")
            for s in stats:
                print(f"  {s['label']:20s}: {s['count']}")
            return

        report = analyzer.full_risk_report(
            file_path=args.file,
            line=args.line,
            func_uid=args.function,
        )

        if args.json and report:
            with open(args.json, "w") as f:
                json.dump(report, f, indent=2, default=str)
            print(f"\n  Report saved to: {args.json}")

    finally:
        analyzer.close()


if __name__ == "__main__":
    main()
