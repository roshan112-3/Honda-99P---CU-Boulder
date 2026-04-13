# Neo4j -- Knowledge Graph Database Layer

This folder contains everything needed to store the Honda 99P knowledge graph in Neo4j and run test prioritization scoring.

---

## Overview

```
unified_knowledge_base.json
        |
        v
+------------------+     +------------------+     +----------------------+
| schema.cypher    |     | ingest.py        |     | NEO4J GRAPH DB       |
| (constraints,    | --> | (loads 226 nodes, | --> | 226 nodes            |
|  indexes)        |     |  462 rels)        |     | 462 relationships    |
+------------------+     +------------------+     | 10 node types        |
                                                   | 14 relationship types|
                                                   +----------+-----------+
                                                              |
                                    +-------------------------+-------------------------+
                                    |                                                   |
                                    v                                                   v
                         +------------------+                                +---------------------+
                         | queries.py       |                                | test_prioritization  |
                         | (10 risk queries |                                |   .py                |
                         |  + CLI)          |                                | (PageRank + FanOut   |
                         +------------------+                                |  + Proximity scoring)|
                                                                             +---------------------+
```

---

## Files

| File | Purpose |
|------|---------|
| `schema.cypher` | Neo4j constraints and indexes (run once) |
| `ingest.py` | Loads `unified_knowledge_base.json` into Neo4j |
| `queries.py` | 10 risk prediction Cypher queries with CLI |
| `test_prioritization.py` | Test scoring engine (the main deliverable) |
| `README.md` | This file |

---

## Setup

### 1. Start Neo4j

```bash
docker run -d --name honda-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/honda99p \
  neo4j:5
```

### 2. Ingest the knowledge graph

```bash
python neo4j/ingest.py
```

This creates:
- **226 nodes**: 95 Functions, 43 Files, 25 TestLabels, 16 Commits, 16 ScenarioCommits, 12 HSIFields, 7 Classes, 4 Authors, 4 Scenarios, 4 Constants
- **462 relationships**: CALLS, DEFINED_IN, BELONGS_TO, IMPLEMENTS_HSI, OWNED_BY, CONTRIBUTED_TO, COMMITTED, AUTHORED_BY, PART_OF, MODIFIES, OBSERVED_IN, LABELS, CHANGED_IN, AFFECTS

### 3. Run test prioritization

```bash
python neo4j/test_prioritization.py
```

### 4. Open Neo4j Browser

```
URL:      http://localhost:7474
Username: neo4j
Password: honda99p
```

---

## schema.cypher

Defines constraints and indexes for the graph. Run automatically by `ingest.py`.

**Uniqueness constraints:**
- `File.path`
- `Function.uid`
- `Class (name, file)` composite
- `Commit.sha`
- `Author.name`
- `HSIField.name`
- `Scenario.id`
- `ScenarioCommit.tag`
- `Constant.name`

**Indexes for fast queries:**
- Function by file, language
- Class by file
- Commit by timestamp
- File by language
- TestLabel by test name, scenario_id
- Function by priority_score, risk_tier (for ranked retrieval)

---

## ingest.py

Reads `unified_knowledge_base.json` and creates all nodes and relationships in Neo4j using batched UNWIND queries (idempotent via MERGE).

**Key features:**
- Normalizes file paths (Windows backslash / Unix forward slash)
- Deduplicates authors from multiple sources
- Creates `Constant` nodes from scenario parameters and links them to affected files
- Prints verification counts after ingestion

**Usage:**

```bash
python neo4j/ingest.py                           # defaults (localhost:7687)
python neo4j/ingest.py --uri bolt://host:7687     # custom URI
python neo4j/ingest.py --password mypassword      # custom password
```

---

## queries.py

Provides 10 Cypher queries for risk analysis, wrapped in a `RiskAnalyzer` class.

| # | Query | Purpose |
|---|-------|---------|
| 1 | Function at Line | Find the function at a given file:line |
| 2 | Direct Callees | Functions this one calls (1 hop) |
| 3 | Direct Callers | Functions that call this one (1 hop) |
| 4 | Transitive Impact | All reachable via CALLS (up to 5 hops) |
| 5 | Reverse Transitive | All upstream callers (up to 5 hops) |
| 6 | Risk Blast Radius | Scored impact: `1/(1+hop) + change_freq * 0.1` |
| 7 | HSI Impact | Which SENSOR_PKT fields are affected |
| 8 | Class Impact | Which classes/methods are impacted |
| 9 | Author Notification | Who should review this change |
| 10 | Graph Stats | Node and relationship counts |

**Usage:**

```bash
# Full risk report for a file + line
python neo4j/queries.py --file "Data/firmware/sensors.cpp" --line 60

# Full risk report for a function UID
python neo4j/queries.py --function "Data\\cloud\\braking_controller.py::calculate_brake_distance"

# Graph stats
python neo4j/queries.py --stats
```

---

## test_prioritization.py

The main deliverable. Computes test priority scores using three signals and persists them on Neo4j nodes.

### How it works

**Step 1: PageRank (centrality)**
- Uses Neo4j GDS plugin if available (PageRank algorithm)
- Falls back to degree-based centrality if GDS is not installed
- Writes `pagerank` property to every Function node

**Step 2: FanOut (inter-file dependency)**
- For each File, counts how many other files' functions call into it
- Normalizes against the most-connected file (0.0 to 1.0)
- Writes `fanout` and `raw_fanout` properties to File nodes

**Step 3: Scoring (per changed constant)**
- Traces from `Constant` node through `AFFECTS -> File <- DEFINED_IN - Function`
- Uses `shortestPath()` to find all test functions within 4 CALLS hops
- Computes priority score:

```
Priority = 0.60 * (1 / shortest_path_hops)    -- Proximity (60%)
         + 0.20 * normalized_pagerank           -- Centrality (20%)
         + 0.20 * normalized_fanout             -- FanOut (20%)
```

**Step 4: Write scores to Neo4j**

Each test Function node gets these properties:
- `priority_score` -- numeric score (0.0 to 1.0)
- `risk_tier` -- CRITICAL / HIGH / MEDIUM / LOW / SAFE
- `triggered_by` -- name of the changed constant
- `last_scored_at` -- datetime of scoring
- `proximity` -- proximity component
- `centrality` -- PageRank component
- `fanout_score` -- FanOut component
- `shortest_path_hops` -- hop count (-1 if unreachable)

**Risk tier thresholds:**

| Tier | Score Range | Action |
|------|-------------|--------|
| CRITICAL | > 0.70 | Must run immediately |
| HIGH | > 0.50 | Run in first batch |
| MEDIUM | > 0.28 | Run in second batch |
| LOW | <= 0.28 | Can defer |
| SAFE | 0.0 (unreachable) | Safe to skip |

### Usage

```bash
# Score all 4 constants (all scenarios)
python neo4j/test_prioritization.py

# Score a specific constant
python neo4j/test_prioritization.py --constant brake_actuator_response_time

# Score by scenario ID
python neo4j/test_prioritization.py --scenario situation-1
```

### Output

Results are saved to `test_prioritization_results.json` at the project root and persisted as properties on Neo4j Function nodes.

### Visualize in Neo4j Bloom

Color-code test nodes by `risk_tier`:

```cypher
MATCH (t:Function)
WHERE t.risk_tier IS NOT NULL
RETURN t.name, t.priority_score, t.risk_tier
ORDER BY t.priority_score DESC
```

---

## Useful Cypher Queries

```cypher
-- All scored tests ranked by priority
MATCH (t:Function) WHERE t.risk_tier IS NOT NULL
RETURN t.name AS test, t.priority_score AS score, t.risk_tier AS tier,
       t.shortest_path_hops AS hops, t.triggered_by AS constant
ORDER BY t.priority_score DESC

-- Blast radius for a specific constant
MATCH (k:Constant {name: "brake_actuator_response_time"})-[:AFFECTS]->(f:File)
      <-[:DEFINED_IN]-(fn:Function)
RETURN k.name, f.path, fn.name

-- Scenario with its commits and authors
MATCH (s:Scenario {id: "situation-1"})<-[:PART_OF]-(sc:ScenarioCommit)-[:AUTHORED_BY]->(a:Author)
RETURN s.title, sc.tag, sc.artifact, a.name

-- Full graph overview
MATCH (n) WITH labels(n)[0] AS label, count(*) AS cnt
RETURN label, cnt ORDER BY cnt DESC
```
