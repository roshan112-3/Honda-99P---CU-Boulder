"""
Test Prioritization Scorer
===========================

After Neo4j ingestion, computes test priority scores using three signals:

  1. PageRank  (centrality)  -- run once via GDS, stored as node property
  2. FanOut    (file deps)   -- how many other files depend on each file
  3. Proximity (hop distance) -- shortest CALLS path from changed constant to test

Formula:
  Priority = 0.50 * (1 / shortest_path)
           + 0.30 * normalized_pagerank
           + 0.20 * normalized_fanout

Risk tiers:
  CRITICAL  >  0.75
  HIGH      >  0.50
  MEDIUM    >  0.25
  LOW       <= 0.25
  SAFE      =  not reachable within 4 hops (score 0)

Scores are persisted on Function nodes as:
  priority_score, risk_tier, triggered_by, last_scored_at

Usage:
  python neo4j/test_prioritization.py                              # score ALL constants
  python neo4j/test_prioritization.py --constant brake_actuator_response_time
  python neo4j/test_prioritization.py --scenario situation-1
"""

import argparse
import json
from datetime import datetime
from pathlib import Path

from neo4j import GraphDatabase

# DEFAULT_URI = "bolt://localhost:7687"
# DEFAULT_USER = "neo4j"
# DEFAULT_PASSWORD = "honda99p"

DEFAULT_URI = "neo4j+s://c1960b7d.databases.neo4j.io"
DEFAULT_USER = "c1960b7d"
DEFAULT_PASSWORD = "8JhCacWXH3EYqkm1AW3PCFCodIvVwTFFF5o0VBCzMAI"


# =========================================================================
# Step 1: PageRank
# =========================================================================

def run_pagerank_gds(session):
    """
    Run PageRank using Neo4j GDS (Graph Data Science) plugin.
    Falls back to degree-based centrality if GDS is not installed.
    Returns True if GDS was used, False if fallback was used.
    """
    # Check if GDS is available
    try:
        result = session.run("RETURN gds.version() AS v")
        version = result.single()["v"]
        print(f"  GDS plugin found (v{version}). Running PageRank...")
    except Exception:
        print("  GDS plugin not found. Using degree-based centrality fallback...")
        _run_pagerank_fallback(session)
        return False

    # Project a graph for PageRank (Functions + CALLS relationships)
    try:
        session.run("CALL gds.graph.drop('honda_graph', false)")
    except Exception:
        pass

    session.run("""
        CALL gds.graph.project(
            'honda_graph',
            ['Function', 'File', 'Constant'],
            {
                CALLS: {orientation: 'UNDIRECTED'},
                DEFINED_IN: {orientation: 'UNDIRECTED'},
                AFFECTS: {orientation: 'UNDIRECTED'}
            }
        )
    """)

    # Run PageRank and write back to nodes
    session.run("""
        CALL gds.pageRank.write('honda_graph', {
            writeProperty: 'pagerank',
            maxIterations: 20,
            dampingFactor: 0.85
        })
    """)

    # Clean up projection
    session.run("CALL gds.graph.drop('honda_graph', false)")

    print("  PageRank scores written to all nodes.")
    return True


def _run_pagerank_fallback(session):
    """
    Approximate PageRank using normalized degree centrality.
    degree = (in-degree + out-degree) / max_degree across all Functions.
    """
    session.run("""
        MATCH (fn:Function)
        OPTIONAL MATCH (fn)-[:CALLS]->()
        WITH fn, count(*) AS out_deg
        OPTIONAL MATCH ()-[:CALLS]->(fn)
        WITH fn, out_deg, count(*) AS in_deg
        WITH fn, toFloat(out_deg + in_deg) AS degree
        WITH collect({node: fn, degree: degree}) AS all_nodes,
             max(degree) AS max_deg
        UNWIND all_nodes AS entry
        WITH entry.node AS fn,
             CASE WHEN max_deg > 0
                  THEN entry.degree / max_deg
                  ELSE 0.0
             END AS normalized
        SET fn.pagerank = normalized
    """)

    # Also set pagerank on File and Constant nodes (based on connected functions)
    session.run("""
        MATCH (f:File)<-[:DEFINED_IN]-(fn:Function)
        WITH f, avg(fn.pagerank) AS avg_pr
        SET f.pagerank = avg_pr
    """)

    session.run("""
        MATCH (k:Constant)-[:AFFECTS]->(f:File)
        WITH k, avg(f.pagerank) AS avg_pr
        SET k.pagerank = avg_pr
    """)

    print("  Degree-based centrality scores written as pagerank property.")


# =========================================================================
# Step 2: FanOut
# =========================================================================

def compute_fanout(session):
    """
    Compute FanOut for every File node.
    FanOut = number of DISTINCT other files whose functions call functions in this file.
    Normalized against the most-connected file.
    """
    session.run("""
        MATCH (f:File)
        OPTIONAL MATCH (caller:Function)-[:CALLS]->(callee:Function)-[:DEFINED_IN]->(f)
        WHERE caller.file <> callee.file
        WITH f, count(DISTINCT caller.file) AS raw_fanout
        WITH collect({node: f, fanout: toFloat(raw_fanout)}) AS all_files,
             max(toFloat(raw_fanout)) AS max_fanout
        UNWIND all_files AS entry
        WITH entry.node AS f,
             entry.fanout AS raw,
             CASE WHEN max_fanout > 0
                  THEN entry.fanout / max_fanout
                  ELSE 0.0
             END AS normalized
        SET f.fanout = normalized,
            f.raw_fanout = toInteger(raw)
    """)

    print("  FanOut scores written to all File nodes.")


# =========================================================================
# Step 3: Score tests for a changed constant
# =========================================================================

QUERY_SCORE_TESTS = """
// Find the changed Constant and trace to affected files
MATCH (k:Constant {name: $constant_name})-[:AFFECTS]->(f:File)

// Find functions defined in affected files (origin functions)
MATCH (origin:Function)-[:DEFINED_IN]->(f)

// Find all test functions (functions in test_*.py files)
MATCH (test:Function)
WHERE test.file CONTAINS 'test_'

// Find shortest path through CALLS graph (max 4 hops)
MATCH path = shortestPath((origin)-[:CALLS*..4]-(test))

// Gather scores
WITH test, k,
     min(length(path)) AS shortest_path,
     f.fanout AS fanout,
     COALESCE(test.pagerank, 0.0) AS pagerank

// Compute priority score
WITH test, k, shortest_path, fanout, pagerank,
     0.50 * (1.0 / toFloat(shortest_path))
     + 0.30 * pagerank
     + 0.20 * COALESCE(fanout, 0.0) AS priority_score

// Assign risk tier
WITH test, k, shortest_path, fanout, pagerank, priority_score,
     CASE
       WHEN priority_score > 0.75 THEN 'CRITICAL'
       WHEN priority_score > 0.50 THEN 'HIGH'
       WHEN priority_score > 0.25 THEN 'MEDIUM'
       ELSE 'LOW'
     END AS risk_tier

// Write scores back to the test Function node
SET test.priority_score = priority_score,
    test.risk_tier = risk_tier,
    test.triggered_by = k.name,
    test.last_scored_at = datetime(),
    test.proximity = toFloat(1.0) / toFloat(shortest_path),
    test.centrality = pagerank,
    test.fanout_score = COALESCE(fanout, 0.0),
    test.shortest_path_hops = shortest_path

RETURN test.name AS test_name,
       test.file AS test_file,
       test.uid AS test_uid,
       shortest_path,
       pagerank,
       COALESCE(fanout, 0.0) AS fanout,
       priority_score,
       risk_tier
ORDER BY priority_score DESC
"""

QUERY_MARK_SAFE_TESTS = """
// Find all test functions NOT already scored for this constant
MATCH (test:Function)
WHERE test.file CONTAINS 'test_'
  AND (test.triggered_by IS NULL OR test.triggered_by <> $constant_name)
SET test.priority_score = 0.0,
    test.risk_tier = 'SAFE',
    test.triggered_by = $constant_name,
    test.last_scored_at = datetime(),
    test.proximity = 0.0,
    test.centrality = 0.0,
    test.fanout_score = 0.0,
    test.shortest_path_hops = -1
RETURN test.name AS test_name,
       test.file AS test_file,
       0.0 AS priority_score,
       'SAFE' AS risk_tier
"""

QUERY_GET_ALL_CONSTANTS = """
MATCH (k:Constant)
RETURN k.name AS name, k.scenario_id AS scenario_id,
       k.scenario_title AS title, k.type AS type,
       k.is_safety_critical AS safety_critical
ORDER BY k.name
"""

QUERY_RANKED_RESULTS = """
MATCH (test:Function)
WHERE test.file CONTAINS 'test_'
  AND test.triggered_by = $constant_name
RETURN test.name AS test_name,
       test.file AS test_file,
       test.priority_score AS priority_score,
       test.risk_tier AS risk_tier,
       test.shortest_path_hops AS shortest_path,
       test.proximity AS proximity,
       test.centrality AS centrality,
       test.fanout_score AS fanout_score,
       test.last_scored_at AS scored_at
ORDER BY test.priority_score DESC
"""


def score_tests_for_constant(session, constant_name):
    """
    Score all test functions reachable within 4 CALLS hops from the
    functions in files affected by the changed constant.
    """
    print(f"\n  Scoring tests for constant: {constant_name}")

    # Score reachable tests
    result = session.run(QUERY_SCORE_TESTS, constant_name=constant_name)
    scored = [dict(r) for r in result]

    print(f"  Reachable tests scored: {len(scored)}")

    # Mark unreachable tests as SAFE
    result = session.run(QUERY_MARK_SAFE_TESTS, constant_name=constant_name)
    safe = [dict(r) for r in result]

    print(f"  Unreachable tests marked SAFE: {len(safe)}")

    return scored, safe


def print_ranked_results(session, constant_name):
    """Print the final ranked test prioritization table."""
    result = session.run(QUERY_RANKED_RESULTS, constant_name=constant_name)
    rows = [dict(r) for r in result]

    if not rows:
        print("  No scored tests found.")
        return []

    print(f"\n{'=' * 100}")
    print(f"  TEST PRIORITIZATION RANKING -- Constant: {constant_name}")
    print(f"{'=' * 100}")
    print(f"  {'Rank':<5} {'Test Name':<45} {'Score':>7} {'Tier':<10} "
          f"{'Hops':>5} {'Prox':>6} {'PR':>6} {'Fan':>6}")
    print(f"  {'-'*5} {'-'*45} {'-'*7} {'-'*10} {'-'*5} {'-'*6} {'-'*6} {'-'*6}")

    for i, row in enumerate(rows, 1):
        hops = row["shortest_path"] if row["shortest_path"] and row["shortest_path"] > 0 else "N/A"
        tier_icon = {
            "CRITICAL": "[!!!]",
            "HIGH":     "[!! ]",
            "MEDIUM":   "[!  ]",
            "LOW":      "[   ]",
            "SAFE":     "[   ]",
        }.get(row["risk_tier"], "")

        print(f"  {i:<5} {row['test_name']:<45} "
              f"{row['priority_score']:>7.4f} "
              f"{tier_icon} {row['risk_tier']:<5} "
              f"{str(hops):>5} "
              f"{row.get('proximity', 0):>6.3f} "
              f"{row.get('centrality', 0):>6.3f} "
              f"{row.get('fanout_score', 0):>6.3f}")

    # Summary by tier
    tier_counts = {}
    for row in rows:
        tier = row["risk_tier"]
        tier_counts[tier] = tier_counts.get(tier, 0) + 1

    print(f"\n  {'-' * 60}")
    print(f"  SUMMARY:")
    for tier in ["CRITICAL", "HIGH", "MEDIUM", "LOW", "SAFE"]:
        count = tier_counts.get(tier, 0)
        if count > 0:
            bar = "#" * count
            print(f"    {tier:<10}: {count:>3} tests  {bar}")

    total_at_risk = sum(v for k, v in tier_counts.items() if k != "SAFE")
    total_safe = tier_counts.get("SAFE", 0)
    print(f"\n  MUST RUN:  {total_at_risk} tests (CRITICAL + HIGH + MEDIUM + LOW)")
    print(f"  SAFE SKIP: {total_safe} tests (not reachable within 4 hops)")
    print(f"{'=' * 100}")

    return rows


# =========================================================================
# Main pipeline
# =========================================================================

def run_prioritization(uri, user, password, constant_name=None, scenario_id=None):
    """Full test prioritization pipeline."""

    print("=" * 70)
    print("  TEST PRIORITIZATION SCORING ENGINE")
    print("=" * 70)

    driver = GraphDatabase.driver(uri, auth=(user, password))

    try:
        driver.verify_connectivity()
        print(f"\n  Connected to Neo4j at {uri}")
    except Exception as e:
        print(f"\n  ERROR: Cannot connect to Neo4j: {e}")
        print("  Make sure Neo4j is running and the KG is ingested.")
        return

    with driver.session() as session:

        # Step 1: PageRank
        print(f"\n{'-' * 70}")
        print("STEP 1: Computing PageRank centrality...")
        print(f"{'-' * 70}")
        run_pagerank_gds(session)

        # Step 2: FanOut
        print(f"\n{'-' * 70}")
        print("STEP 2: Computing FanOut (inter-file dependency)...")
        print(f"{'-' * 70}")
        compute_fanout(session)

        # Determine which constants to score
        if constant_name:
            constants_to_score = [constant_name]
        elif scenario_id:
            # Find constant for this scenario
            result = session.run(
                "MATCH (k:Constant {scenario_id: $sid}) RETURN k.name AS name",
                sid=scenario_id
            )
            constants_to_score = [r["name"] for r in result]
            if not constants_to_score:
                print(f"\n  ERROR: No constant found for scenario {scenario_id}")
                driver.close()
                return
        else:
            # Score all constants
            result = session.run(QUERY_GET_ALL_CONSTANTS)
            all_constants = [dict(r) for r in result]
            constants_to_score = [c["name"] for c in all_constants]

            print(f"\n  Constants found in graph:")
            for c in all_constants:
                safety = "SAFETY-CRITICAL" if c["safety_critical"] else "non-critical"
                print(f"    - {c['name']} ({c['type']}, {safety}) "
                      f"[{c['scenario_id']}]")

        # Step 3: Score tests for each constant
        print(f"\n{'-' * 70}")
        print("STEP 3: Scoring tests via shortestPath (max 4 hops)...")
        print(f"{'-' * 70}")

        all_results = {}
        for cname in constants_to_score:
            scored, safe = score_tests_for_constant(session, cname)
            # Print ranked results immediately (before next constant overwrites)
            rows = print_ranked_results(session, cname)
            all_results[cname] = {"scored": scored, "safe": safe, "ranked": rows}

    driver.close()

    # Save results as JSON
    output_dir = Path(__file__).resolve().parent.parent
    output_file = output_dir / "test_prioritization_results.json"
    serializable = {}
    for cname, data in all_results.items():
        serializable[cname] = {
            "scored_tests": data["scored"],
            "safe_tests": [{"test_name": s["test_name"], "test_file": s["test_file"]}
                           for s in data["safe"]],
            "ranked": [{k: v for k, v in r.items()
                        if k != "scored_at"} for r in data.get("ranked", [])],
        }

    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(serializable, f, indent=2, default=str)

    print(f"\n  Results saved to: {output_file}")
    print(f"\n  Neo4j Bloom: color-code Function nodes by 'risk_tier' property")
    print(f"  Cypher check: MATCH (t:Function) WHERE t.risk_tier IS NOT NULL "
          f"RETURN t.name, t.priority_score, t.risk_tier ORDER BY t.priority_score DESC")


# =========================================================================
# CLI
# =========================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Test Prioritization Scorer -- "
                    "computes risk scores for tests based on changed constants"
    )
    parser.add_argument("--uri", default=DEFAULT_URI, help="Neo4j Bolt URI")
    parser.add_argument("--user", default=DEFAULT_USER)
    parser.add_argument("--password", default=DEFAULT_PASSWORD)
    parser.add_argument("--constant",
                        help="Score tests for a specific constant "
                             "(e.g., brake_actuator_response_time)")
    parser.add_argument("--scenario",
                        help="Score tests for a specific scenario "
                             "(e.g., situation-1)")
    args = parser.parse_args()

    run_prioritization(
        args.uri, args.user, args.password,
        constant_name=args.constant,
        scenario_id=args.scenario,
    )


if __name__ == "__main__":
    main()
