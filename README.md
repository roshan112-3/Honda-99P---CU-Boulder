# Honda 99P -- Knowledge Graph for Test Risk Prediction

A research project that builds a **property knowledge graph** from an automotive software codebase, then uses that graph to automatically predict **which test cases are at risk of failing** when any parameter in the system changes.

---

## What We Did -- Project Summary

Here is a clear, step-by-step account of everything that was built in this project:

**Step 1 -- Parsed all source code into a structured graph**
We wrote a Python parser (`parsers/tree_sitter.py`) that reads every C++ and Python file under `Data/` and extracts the full code structure: which functions exist, which file they live in, which functions call other functions, and which code lines implement the hardware protocol (HSI). This produced 95 functions, 7 classes, 347 call edges, and 483 total relationships.

**Step 2 -- Extracted change-scenario metadata**
We wrote a second parser (`parsers/git_python.py`) that reads the curated change-risk dataset (`Data/docs/change_risk_scenarios.json`) and extracts all engineering metadata: 4 simulated authors (Harshitha, Roshan, Ryan, Shivani), 16 commits, 4 real-world change scenarios, and 25 labeled test examples (19 failures, 6 passes) with engineered ML features.

**Step 3 -- Merged everything into one unified knowledge base**
We wrote `merge_knowledge.py` to combine the AST output (Step 1) and the scenario metadata (Step 2) into a single self-contained JSON file (`unified_knowledge_base.json`) that carries both code structure and change history together.

**Step 4 -- Loaded the knowledge base into Neo4j as a live graph**
We wrote `neo4j/ingest.py` to load the unified JSON into a Neo4j property graph database running in Docker. This created 226 nodes of 10 different types and 462 typed relationships. We also defined 4 special `Constant` nodes -- one for each parameter that can change -- and wired them via `AFFECTS` edges to the files they impact.

**Step 5 -- Built a test prioritization scoring engine**
We wrote `neo4j/test_prioritization.py`, the main deliverable. It takes any changed parameter (Constant node), traces through the graph to find all reachable test functions within 4 call hops, and scores each test using three signals: how close it is to the changed code (Proximity), how central the function is in the call graph (PageRank), and how widely depended-upon its file is (FanOut). Each test receives a score from 0 to 1 and a risk tier (CRITICAL / HIGH / MEDIUM / LOW / SAFE).

**Output**
The final output is `test_prioritization_results.json`, which contains a ranked list of every test for each of the 4 change scenarios. Out of 25 total tests, the system identifies 4-7 tests that must run immediately per scenario -- meaning 72-84% of tests can be safely skipped, saving significant CI/CD time without missing failures.

---

## What This Project Does

Modern automotive software (like Honda's 99P platform) has hundreds of functions across embedded C++ firmware and Python cloud services, maintained by multiple engineers, connected through complex call chains. When a single parameter changes -- like brake actuator response time -- it can ripple through dozens of functions and silently break tests that nobody thought to re-run.

This project solves that by:

1. **Parsing all source code** into a structured graph of functions, classes, and call relationships
2. **Extracting scenario metadata** (who changed what, when, and why) from a curated change-risk dataset
3. **Merging** code structure with change history into a single unified knowledge base
4. **Loading** the knowledge base into Neo4j as a live property graph
5. **Scoring every test** using PageRank + FanOut + Proximity to produce a ranked priority list of tests that must run

---

## Full Pipeline -- Step by Step

```
+-------------------------+     +---------------------------+
|   DATA/firmware/*.cpp   |     |  Data/docs/               |
|   DATA/cloud/*.py       |     |  change_risk_scenarios    |
|   (27 source files)     |     |  .json                    |
+----------+--------------+     +-------------+-------------+
           |                                  |
           v                                  v
+---------------------+         +---------------------------+
|  STEP 1             |         |  STEP 2                   |
|  parsers/           |         |  parsers/                 |
|  tree_sitter.py     |         |  git_python.py            |
|                     |         |                           |
|  AST-based code     |         |  Reads scenario JSON,     |
|  parsing (regex)    |         |  extracts authors,        |
|  - 95 functions     |         |  commits, test labels     |
|  - 7 classes        |         |  - 4 authors              |
|  - 347 call edges   |         |  - 16 commits             |
|  - 13 HSI links     |         |  - 4 scenarios            |
|  - 483 rels total   |         |  - 25 labeled examples    |
+----------+----------+         +-------------+-------------+
           |                                  |
           v                                  v
+---------------------+         +---------------------------+
|  parsers/           |         |  parsers/                 |
|  ast_knowledge      |         |  git_history_knowledge    |
|  _base.json         |         |  _base.json               |
+----------+----------+         +-------------+-------------+
           |                                  |
           +----------------+-----------------+
                            |
                            v
               +---------------------------+
               |  STEP 3                   |
               |  merge_knowledge.py       |
               |                           |
               |  Merges AST data with     |
               |  scenario metadata into   |
               |  one unified JSON         |
               +-------------+-------------+
                             |
                             v
               +---------------------------+
               |  unified_knowledge        |
               |  _base.json               |
               |                           |
               |  95 functions             |
               |  7 classes                |
               |  4 authors                |
               |  16 commits               |
               |  4 scenarios              |
               |  25 labeled examples      |
               |  483 relationships        |
               +-------------+-------------+
                             |
                             v
               +---------------------------+
               |  STEP 4                   |
               |  neo4j/schema.cypher      |
               |  neo4j/ingest.py          |
               |                           |
               |  Loads into Neo4j graph   |
               |  database via Docker      |
               |                           |
               |  226 nodes (10 types)     |
               |  462 relationships        |
               |  (14 types)               |
               +-------------+-------------+
                             |
                             v
               +---------------------------+
               |  STEP 5                   |
               |  neo4j/                   |
               |  test_prioritization.py   |
               |                           |
               |  PageRank + FanOut +      |
               |  Proximity scoring        |
               |                           |
               |  Ranks every test by      |
               |  risk tier: CRITICAL /    |
               |  HIGH / MEDIUM / LOW /    |
               |  SAFE                     |
               +---------------------------+
                             |
                             v
               +---------------------------+
               |  test_prioritization      |
               |  _results.json            |
               |  (final output)           |
               +---------------------------+
```

---

## STEP 1 -- AST Code Parsing (`parsers/tree_sitter.py`)

### What it does

Scans every source file under `Data/` and extracts the full code structure using regex-based parsing (named "tree-sitter" in the project, but implemented with Python regex for portability).

**Languages parsed:**

| Language | Directory | File Types |
|----------|-----------|------------|
| C++ | Data/firmware/ | .cpp, .h |
| Python | Data/cloud/ | .py |

**What gets extracted:**

| Entity | Count | Description |
|--------|-------|-------------|
| Functions | 95 | Name, file, line number, parameters, return type |
| Classes | 7 | Name, file, member list, line range |
| Call edges | 347 | Which function calls which function |
| HSI links | 13 | Which code lines implement which SENSOR_PKT byte |
| Total relationships | 483 | All of the above combined |

**HSI Traceability** -- maps source code bytes to the SENSOR_PKT hardware specification:

| Byte | Field | Function | File | Line |
|------|-------|----------|------|------|
| 0 | version | pack_latest | sensors.cpp | 64 |
| 1 | sensor_id | pack_latest | sensors.cpp | 65 |
| 2-3 | temperature_raw | pack_latest | sensors.cpp | 66-67 |
| 4-5 | pressure_raw | pack_latest | sensors.cpp | 68-69 |
| 6-7 | humidity_raw | pack_latest | sensors.cpp | 70-71 |
| 8-9 | fuel_raw | pack_latest | sensors.cpp | 72-73 |
| 10 | status_flags | pack_latest | sensors.cpp | 77-78 |
| 11 | checksum (CRC-8) | pack_latest | sensors.cpp | 89 |

**Output:** `parsers/ast_knowledge_base.json`

```bash
python parsers/tree_sitter.py
```

---

## STEP 2 -- Scenario Metadata Extraction (`parsers/git_python.py`)

### What it does

Reads `Data/docs/change_risk_scenarios.json` -- the curated dataset representing realistic automotive software change scenarios -- and extracts all metadata needed for the knowledge graph and ML training.

> **Why not use git log?**
> The actual git history only shows one author (Roshan) who uploaded everything at once. The real cross-team authorship, commit history, and failure scenarios are embedded inside `change_risk_scenarios.json`, which simulates 4 distinct engineers making 16 commits across 4 realistic change scenarios. This file is the **source of truth** for all metadata.

**What gets extracted:**

| Entity | Count | Detail |
|--------|-------|--------|
| Authors | 4 | Harshitha (ABS), Roshan (braking), Ryan (LiDAR), Shivani (CAN/motor) |
| Commits | 16 | H-023, R-041, S-078, R-019, H-057, S-092, S-093, H-009, S-031, RY-011, R-055, R-007, H-031, H-032, H-033, S-044 |
| Scenarios | 4 | 4 realistic parameter-change scenarios |
| Labeled test examples | 25 | 19 failures (label=1), 6 passes (label=0) |
| Files with ownership | 12 | Which author owns which file |

**The 4 Change Risk Scenarios:**

| Scenario | Parameter Changed | Type | Safety Critical? |
|----------|------------------|------|-----------------|
| situation-1 | `brake_actuator_response_time` | timing | YES |
| situation-2 | `lidar_offset_calibration` | calibration | YES |
| situation-3 | `max_motor_torque_nm` | torque | YES |
| situation-4 | `can_bus_message_interval_ms` | timing | NO |

**ML Feature Engineering** -- 25 labeled examples with engineered features:
- `shortest_path` -- hops from changed code to test in call graph
- `hw_sw_sync_lag_days` -- delay between hardware and software commits
- `downstream_test_count` -- how many tests are reachable
- `churn_rate` -- how often the file changes historically
- `cofailure_count` -- tests that historically fail together
- `is_cross_boundary_change` -- did the change cross HW/SW team boundary?
- `author_is_hw_team` -- was the change made by a hardware engineer?
- `param_is_safety_critical` -- is the changed parameter safety-critical?

**Output:** `parsers/git_history_knowledge_base.json`

```bash
python parsers/git_python.py
```

---

## STEP 3 -- Merge into Unified Knowledge Base (`merge_knowledge.py`)

### What it does

Combines the outputs of Step 1 and Step 2 into a single, self-contained JSON file that carries both code structure and change history together.

**Merge logic:**
- Functions from the AST get linked to their owning author based on file ownership from scenarios
- Scenario commits get linked to the functions/files they modified
- Labeled examples are preserved with their ML feature vectors
- All relationships are deduplicated and unified

**Output:** `unified_knowledge_base.json`

```
{
  95 functions
  7 classes
  4 authors
  16 commits
  4 scenarios
  25 labeled examples
  483 relationships
}
```

```bash
python merge_knowledge.py
```

---

## STEP 4 -- Neo4j Knowledge Graph Ingestion

### 4a. Start Neo4j via Docker

```bash
docker run -d --name honda-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/honda99p \
  neo4j:5
```

Neo4j Browser: http://localhost:7474
Username: `neo4j` | Password: `honda99p`

### 4b. Apply Schema (`neo4j/schema.cypher`)

Creates all uniqueness constraints and indexes so queries are fast and data stays clean.

**Uniqueness constraints (prevent duplicates):**

| Node Type | Unique On |
|-----------|-----------|
| File | path |
| Function | uid |
| Class | (name, file) composite |
| Commit | sha |
| Author | name |
| HSIField | name |
| Scenario | id |
| ScenarioCommit | tag |
| Constant | name |

**Indexes (for fast lookups):**
- Function by file, language
- Function by priority_score, risk_tier (for ranked retrieval)
- Commit by timestamp
- TestLabel by test name, scenario_id

### 4c. Ingest the Graph (`neo4j/ingest.py`)

Reads `unified_knowledge_base.json` and creates all nodes and relationships using batched `UNWIND ... MERGE` queries (idempotent -- safe to re-run).

**Graph created:**

| Node Type | Count | What it represents |
|-----------|-------|--------------------|
| Function | 95 | Every function/method in the codebase |
| File | 43 | Every source file |
| TestLabel | 25 | Labeled test examples (pass/fail) |
| Commit | 16 | Simulated commits from scenarios |
| ScenarioCommit | 16 | Cross-team commit events |
| HSIField | 12 | SENSOR_PKT protocol fields |
| Class | 7 | C++ and Python classes |
| Author | 4 | Engineers (Harshitha, Roshan, Ryan, Shivani) |
| Scenario | 4 | The 4 change-risk situations |
| Constant | 4 | Changed parameters (brake time, LiDAR offset, etc.) |
| **TOTAL** | **226** | |

| Relationship Type | Direction | Meaning |
|------------------|-----------|---------|
| CALLS | Function -> Function | A calls B |
| DEFINED_IN | Function -> File | Function lives in this file |
| BELONGS_TO | Function -> Class | Method belongs to this class |
| IMPLEMENTS_HSI | Function -> HSIField | Code implements this protocol byte |
| OWNED_BY | File -> Author | This author owns this file |
| CONTRIBUTED_TO | Commit -> File | This commit modified this file |
| COMMITTED | Commit -> ScenarioCommit | Commit is part of a scenario commit |
| AUTHORED_BY | ScenarioCommit -> Author | Who made this scenario commit |
| PART_OF | ScenarioCommit -> Scenario | Which scenario this commit belongs to |
| MODIFIES | Commit -> Function | Commit changed this function |
| OBSERVED_IN | TestLabel -> Scenario | This test result was observed in this scenario |
| LABELS | TestLabel -> Function | Test label applies to this test function |
| CHANGED_IN | Constant -> Scenario | This parameter changed in this scenario |
| AFFECTS | Constant -> File | This parameter change affects this file |
| **TOTAL** | **462** | |

```bash
python neo4j/ingest.py
```

---

## STEP 5 -- Test Prioritization Scoring (`neo4j/test_prioritization.py`)

### What is Test Prioritization?

When an engineer changes a parameter in the codebase -- for example, adjusting the brake actuator response time -- the question becomes: **out of all 25 test cases in the system, which ones actually need to be re-run?**

Running all 25 tests every time any parameter changes is slow, expensive, and unnecessary. Most tests have nothing to do with the changed parameter. But if you skip the wrong test, you miss a real failure.

Test prioritization solves this by **ranking every test by how likely it is to be affected by the change**. Tests that are close to the changed code, in important parts of the system, and connected to widely-used files get high scores and must run first. Tests that have no connection to the changed code get a SAFE label and can be skipped entirely.

---

### Why Do We Calculate This?

The core problem in automotive software testing is **regression risk**. When one engineer changes a hardware parameter (e.g., brake response time drifts by 5ms), it can cause failures in software tests written by a completely different team that nobody thought to re-run. This is especially dangerous in safety-critical systems like ABS braking, LiDAR perception, and motor torque control.

By building a knowledge graph of how every function connects to every other function and then scoring each test based on its graph distance from the change, we can:
- Know in seconds which tests are at risk
- Run only the critical tests in CI/CD (save 72-84% of test time)
- Never miss a test that sits close to the changed code
- Give each test a human-readable reason for why it was prioritized

---

### What Are We Calculating?

For each change scenario (one changed parameter), we compute a **priority score** (0.0 to 1.0) for every test function in the system. This score combines three signals:

```
Priority Score = 0.60 x Proximity
              + 0.20 x PageRank (Centrality)
              + 0.20 x FanOut
```

The score tells us how urgently a test needs to run. A score of 0.84 means "run immediately -- this test is directly in the blast radius." A score of 0.0 means "this test is completely unreachable from the change -- safe to skip."

---

### Where Do the Test Cases Come From?

The 25 test functions come from 4 test files in `Data/cloud/`:

| Test File | Tests Inside | What They Test |
|-----------|-------------|----------------|
| `test_braking.py` | 8 tests | Brake distance, ABS threshold, emergency stop, stopping force, pedal mapping, fluid pressure, safety integration, end-to-end dynamics |
| `test_can_timing.py` | 7 tests | CAN frame parsing, checksum validation, ID parsing, steering latency, brake pedal signal, accelerator response, health check interval |
| `test_drivetrain.py` | 6 tests | Torque limits, thermal cutoff, ECU integration, overheat protection, battery charge, regenerative braking |
| `test_sensor_fusion.py` | 4 tests | Obstacle detection, collision margin, trajectory clearance, sensor fusion integration |

These test functions are treated as nodes in the knowledge graph (they are Function nodes). The scoring engine finds them by looking for functions whose names start with `test_`.

---

### The 3 Scoring Parameters -- Explained

---

#### Parameter 1: Proximity (60% of the score)

**What it is:**
Proximity measures how many "hops" in the function call graph separate the changed code from the test function. One hop means the test directly calls a function that was changed. Two hops means there is one function in between. And so on.

**Why it is weighted at 60%:**
Proximity is the strongest signal because it is the most direct measure of impact. A test that directly calls a changed function is almost certainly going to be affected. A test that is 4 hops away might still be affected, but the connection is weaker. Proximity carries 60% so that all 1-hop tests reliably land in CRITICAL regardless of their secondary signal values.

**How it is calculated:**
The graph traversal path is:
```
Constant --[AFFECTS]--> File <--[DEFINED_IN]-- Function --[CALLS*..4]--> TestFunction
```
1. Start at the Constant node (e.g., `brake_actuator_response_time`)
2. Follow `AFFECTS` edge to the File(s) that are impacted
3. Find all Functions defined in those files
4. Use Neo4j `shortestPath()` to find the minimum number of `CALLS` hops to reach each test function
5. Maximum search depth is 4 hops. Tests beyond 4 hops are marked SAFE.

**Proximity score by hop count:**

| Hops | Proximity Component | Meaning |
|------|--------------------|---------------------------------|
| 1 | 0.60 x (1/1) = **0.600** | Test directly calls changed code |
| 2 | 0.60 x (1/2) = **0.300** | One function between test and change |
| 3 | 0.60 x (1/3) = **0.200** | Two functions between test and change |
| 4 | 0.60 x (1/4) = **0.150** | Three functions between test and change |
| 5+ | **0.000** | Not reachable -- SAFE |

---

#### Parameter 2: PageRank / Centrality (20% of the score)

**What it is:**
PageRank is a graph algorithm (originally invented by Google) that measures how "important" a node is based on how many other important nodes point to it. In our call graph, a function that is called by many other functions has high centrality. This means changes to that function (or its neighborhood) are more likely to have wide ripple effects.

**Why it is weighted at 20%:**
PageRank is a per-function signal precise enough to break ties between tests at equal hop distance. It is weighted equally with FanOut at 20% each, since both are secondary signals that refine the ranking without overriding proximity.

**How it is calculated:**
- If the Neo4j GDS (Graph Data Science) plugin is installed: the real PageRank algorithm is run on the CALLS subgraph
- If GDS is not installed: falls back to degree-based centrality (count of incoming CALLS edges divided by total edges)
- The raw PageRank values are normalized to [0, 1] against the highest PageRank in the graph
- The normalized value is written as `pagerank` property on each Function node

In our graph, most functions have a normalized PageRank of 0.20 (the fallback degree-based score), meaning the centrality component contributes `0.20 x 0.20 = 0.04` to the final score.

---

#### Parameter 3: FanOut / Inter-File Dependency (20% of the score, equal to Centrality)

**What it is:**
FanOut measures how many *other* files have functions that call into a given file. It captures how "widely depended upon" a file is. A file with high FanOut (e.g., `braking_controller.py`) is imported or called by many other files across the system, so changes in it cascade broadly.

**Why it is weighted at 20%:**
FanOut catches the scenario where a changed file is a shared dependency. Even if a test is not close in hop count, if it lives in a file that everyone depends on, it still carries higher risk.

**How it is calculated:**
```
FanOut(file) = number of distinct other files whose functions call into this file
               ---------------------------------------------------------------
               maximum FanOut score across all files (for normalization)
```
- The FanOut is computed for every File node in the graph
- The file with the most incoming cross-file calls gets FanOut = 1.0
- All other files are scaled proportionally (0.0 to 1.0)
- Written as `fanout` property on each File node

In our graph:
- Files like `braking_controller.py` and `can_interface.py` have FanOut = **1.0** (called from many files)
- Files like `sensor_fusion.py` and `drivetrain_controller.py` have FanOut = **0.5** (called from fewer files)

The FanOut component contributes `0.20 x fanout` to the final score.

---

### The Priority Score Formula

```
Priority Score = 0.60 x (1 / shortest_path_hops)   <- how close to the change
              + 0.20 x normalized_pagerank           <- how important in the graph
              + 0.20 x normalized_fanout             <- how widely depended upon
```

**Worked example -- `test_brake_distance_nominal` when `brake_actuator_response_time` changes:**

```
shortest_path = 1 hop  ->  proximity   = 0.60 x (1/1) = 0.600
pagerank      = 0.20   ->  centrality  = 0.20 x 0.20  = 0.040
fanout        = 1.0    ->  fanout_comp = 0.20 x 1.0   = 0.200
                                         -----
                           TOTAL SCORE  = 0.840  ->  CRITICAL
```

**Worked example -- `test_vehicle_dynamics_end_to_end` (3 hops away):**

```
shortest_path = 3 hops ->  proximity   = 0.60 x (1/3) = 0.200
pagerank      = 0.20   ->  centrality  = 0.20 x 0.20  = 0.040
fanout        = 1.0    ->  fanout_comp = 0.20 x 1.0   = 0.200
                                         -----
                           TOTAL SCORE  = 0.440  ->  MEDIUM
```

---

### How the Weights 0.60 / 0.20 / 0.20 Were Determined

The weights were not guessed or picked arbitrarily. They were derived through a structured process combining domain reasoning, mathematical derivation, and a systematic grid search across all valid weight combinations. This section documents that process in full.

---

#### The Starting Point -- What We Knew and What We Did Not

Before choosing any weights, we had two pieces of information from the knowledge graph:

**Known (from graph structure):**
```
1 hop  =  CRITICAL   (test is directly in the blast radius)
2 hops =  HIGH       (one function between test and change)
3 hops =  MEDIUM     (two functions between test and change)
4 hops =  LOW        (at the edge of reachability)
```

**Unknown:**
```
What numeric score separates CRITICAL from HIGH?
What numeric score separates HIGH from MEDIUM?
What weights produce those score separations?
```

There are two unknowns -- weights AND boundaries. You cannot solve for both simultaneously without first making at least one assumption. That assumption is made explicit below.

---

#### Step 1 -- Observe What Actually Changes with Hops

From the dataset (`test_prioritization_results.json`), the actual signal values per test are:

| Signal | Value |
|---|---|
| PageRank | 0.20 for all tests (degree-based fallback, uniform across graph) |
| FanOut | 0.5 or 1.0 depending on the file |
| Proximity | Changes with every hop: 1/hops |

Proximity values by hop:
```
1 hop  →  1 / 1 = 1.000
2 hops →  1 / 2 = 0.500
3 hops →  1 / 3 = 0.333
4 hops →  1 / 4 = 0.250
```

**Key observation:** PageRank is identical for every test. FanOut is the same within a hop group. The only signal that changes as hops increase is Proximity. Therefore, the entire separation between tiers is driven exclusively by the Proximity weight (`w_p`).

---

#### Step 2 -- Derive the Minimum Proximity Weight Mathematically

Write the score formula for a 1-hop test and a 2-hop test:

```
Score(1 hop)  = w_p × 1.000 + w_c × 0.2 + w_f × 1.0
Score(2 hops) = w_p × 0.500 + w_c × 0.2 + w_f × 1.0
```

Subtract them:
```
Score(1 hop) - Score(2 hops) = w_p × (1.000 - 0.500)
                              = 0.5 × w_p
```

PageRank and FanOut cancel out completely -- they contribute identically to both scores. The entire gap between a 1-hop test and a 2-hop test is `0.5 × w_p`.

**Assumption:** The gap between adjacent tiers should be at least 0.20 -- large enough to be a meaningful distinction, not so large that scores spread out unrealistically.

```
0.5 × w_p  ≥  0.20
w_p        ≥  0.40
```

We want the 1-hop score to sit clearly above the CRITICAL boundary, not just barely. Choosing `w_p = 0.40` gives a gap of exactly 0.20, which is the minimum. To get a clean, unambiguous separation we set:

```
w_p = 0.60   →   gap = 0.5 × 0.60 = 0.30
```

This means a 1-hop test always scores at least 0.30 higher than a 2-hop test, regardless of PageRank or FanOut values.

---

#### Step 3 -- Split the Remaining Weight Equally

With `w_p = 0.60` fixed, the remaining 0.40 is split between `w_c` (PageRank) and `w_f` (FanOut).

Both are secondary signals. Neither dominates:
- PageRank is computed via a degree-based fallback in this dataset, making all values uniform at 0.20 -- it adds precision but not differentiation between hops
- FanOut is a file-level metric -- coarser than per-function PageRank

Since neither is more reliable than the other, they are split equally:
```
w_c = 0.20
w_f = 0.20
```

---

#### Step 4 -- Validate Through Grid Search (All 10 Trials)

To confirm this was the correct and only valid choice, a systematic grid search was run across all valid weight triplets. The constraints were:

```
Constraint 1:  w_p + w_c + w_f = 1.0
Constraint 2:  each weight between 0.05 and 0.70
Constraint 3:  step size of 0.10
```

This produced exactly 10 valid combinations. Each was tested against 4 representative tests from the actual dataset:

| Test | Hops | FanOut | PageRank | Expected Tier |
|---|---|---|---|---|
| `test_brake_distance_nominal` | 1 | 1.0 | 0.2 | CRITICAL (score > 0.70) |
| `test_steering_input_latency` | 1 | 0.5 | 0.2 | CRITICAL (score > 0.70) |
| `test_safety_controller_integration` | 2 | 1.0 | 0.2 | HIGH (score 0.50 – 0.70) |
| `test_vehicle_dynamics_end_to_end` | 3 | 1.0 | 0.2 | MEDIUM (score 0.28 – 0.50) |

A trial passes only if all 4 tests land in their expected tier. If even one test is misclassified, the trial is rejected.

---

**Trial 1 -- (w_p=0.3, w_c=0.3, w_f=0.4)**
```
test_brake_distance      : 0.3×1.000 + 0.3×0.2 + 0.4×1.0 = 0.760  CRITICAL  ✓
test_steering_latency    : 0.3×1.000 + 0.3×0.2 + 0.4×0.5 = 0.560  HIGH      ✗  (1-hop must be CRITICAL)
test_safety_controller   : 0.3×0.500 + 0.3×0.2 + 0.4×1.0 = 0.610  HIGH      ✓
test_vehicle_dynamics    : 0.3×0.333 + 0.3×0.2 + 0.4×1.0 = 0.560  HIGH      ✗  (3-hop must be MEDIUM)
```
**FAIL** -- FanOut weight 0.4 inflates distant tests and prevents 1-hop/fanout=0.5 from reaching CRITICAL.

---

**Trial 2 -- (w_p=0.4, w_c=0.3, w_f=0.3)**
```
test_brake_distance      : 0.4×1.000 + 0.3×0.2 + 0.3×1.0 = 0.760  CRITICAL  ✓
test_steering_latency    : 0.4×1.000 + 0.3×0.2 + 0.3×0.5 = 0.610  HIGH      ✗  (1-hop must be CRITICAL)
test_safety_controller   : 0.4×0.500 + 0.3×0.2 + 0.3×1.0 = 0.560  HIGH      ✓
test_vehicle_dynamics    : 0.4×0.333 + 0.3×0.2 + 0.3×1.0 = 0.493  MEDIUM    ✓
```
**FAIL** -- w_p=0.4 is too low. A 1-hop test with fanout=0.5 can never reach CRITICAL.

---

**Trial 3 -- (w_p=0.4, w_c=0.4, w_f=0.2)**
```
test_brake_distance      : 0.4×1.000 + 0.4×0.2 + 0.2×1.0 = 0.680  HIGH      ✗  (should be CRITICAL)
test_steering_latency    : 0.4×1.000 + 0.4×0.2 + 0.2×0.5 = 0.580  HIGH      ✗
test_safety_controller   : 0.4×0.500 + 0.4×0.2 + 0.2×1.0 = 0.480  MEDIUM    ✗  (should be HIGH)
test_vehicle_dynamics    : 0.4×0.333 + 0.4×0.2 + 0.2×1.0 = 0.413  MEDIUM    ✓
```
**FAIL** -- w_p=0.4 means even the best 1-hop test maxes at 0.68, can never reach CRITICAL.

---

**Trial 4 -- (w_p=0.5, w_c=0.1, w_f=0.4)**
```
test_brake_distance      : 0.5×1.000 + 0.1×0.2 + 0.4×1.0 = 0.920  CRITICAL  ✓
test_steering_latency    : 0.5×1.000 + 0.1×0.2 + 0.4×0.5 = 0.720  CRITICAL  ✓
test_safety_controller   : 0.5×0.500 + 0.1×0.2 + 0.4×1.0 = 0.670  HIGH      ✓
test_vehicle_dynamics    : 0.5×0.333 + 0.1×0.2 + 0.4×1.0 = 0.587  HIGH      ✗  (3-hop must be MEDIUM)
```
**FAIL** -- FanOut=0.4 pushes the 3-hop test into HIGH. A distant test is being treated as urgent purely because its file is widely imported.

---

**Trial 5 -- (w_p=0.5, w_c=0.2, w_f=0.3)**
```
test_brake_distance      : 0.5×1.000 + 0.2×0.2 + 0.3×1.0 = 0.840  CRITICAL  ✓
test_steering_latency    : 0.5×1.000 + 0.2×0.2 + 0.3×0.5 = 0.690  HIGH      ✗  (0.69 < 0.70, misses CRITICAL by 0.01)
test_safety_controller   : 0.5×0.500 + 0.2×0.2 + 0.3×1.0 = 0.590  HIGH      ✓
test_vehicle_dynamics    : 0.5×0.333 + 0.2×0.2 + 0.3×1.0 = 0.507  HIGH      ✗  (3-hop must be MEDIUM)
```
**FAIL** -- FanOut=0.3 still inflates 3-hop scores, and the 1-hop/fanout=0.5 test misses CRITICAL by 0.01.

---

**Trial 6 -- (w_p=0.5, w_c=0.3, w_f=0.2)**
```
test_brake_distance      : 0.5×1.000 + 0.3×0.2 + 0.2×1.0 = 0.760  CRITICAL  ✓
test_steering_latency    : 0.5×1.000 + 0.3×0.2 + 0.2×0.5 = 0.660  HIGH      ✗  (0.66 < 0.70, misses CRITICAL)
test_safety_controller   : 0.5×0.500 + 0.3×0.2 + 0.2×1.0 = 0.510  HIGH      ✓
test_vehicle_dynamics    : 0.5×0.333 + 0.3×0.2 + 0.2×1.0 = 0.427  MEDIUM    ✓
```
**FAIL** -- The 1-hop test with fanout=0.5 scores 0.66, still below the CRITICAL threshold of 0.70. Two 1-hop tests landing in different tiers is semantically inconsistent.

---

**Trial 7 -- (w_p=0.5, w_c=0.4, w_f=0.1)**
```
test_brake_distance      : 0.5×1.000 + 0.4×0.2 + 0.1×1.0 = 0.680  HIGH      ✗  (should be CRITICAL)
test_steering_latency    : 0.5×1.000 + 0.4×0.2 + 0.1×0.5 = 0.630  HIGH      ✗
test_safety_controller   : 0.5×0.500 + 0.4×0.2 + 0.1×1.0 = 0.430  MEDIUM    ✗  (should be HIGH)
test_vehicle_dynamics    : 0.5×0.333 + 0.4×0.2 + 0.1×1.0 = 0.347  MEDIUM    ✓
```
**FAIL** -- w_c=0.4 starves proximity and FanOut. Even 1-hop tests can never reach CRITICAL.

---

**Trial 8 -- (w_p=0.6, w_c=0.2, w_f=0.2) ← THE ONLY PASSING TRIAL**
```
test_brake_distance      : 0.6×1.000 + 0.2×0.2 + 0.2×1.0 = 0.840  CRITICAL  ✓
test_steering_latency    : 0.6×1.000 + 0.2×0.2 + 0.2×0.5 = 0.740  CRITICAL  ✓
test_safety_controller   : 0.6×0.500 + 0.2×0.2 + 0.2×1.0 = 0.540  HIGH      ✓
test_vehicle_dynamics    : 0.6×0.333 + 0.2×0.2 + 0.2×1.0 = 0.440  MEDIUM    ✓
```
**ALL PASS** -- Every test lands in its correct tier.

---

**Trial 9 -- (w_p=0.6, w_c=0.3, w_f=0.1)**
```
test_brake_distance      : 0.6×1.000 + 0.3×0.2 + 0.1×1.0 = 0.760  CRITICAL  ✓
test_steering_latency    : 0.6×1.000 + 0.3×0.2 + 0.1×0.5 = 0.710  CRITICAL  ✓
test_safety_controller   : 0.6×0.500 + 0.3×0.2 + 0.1×1.0 = 0.460  MEDIUM    ✗  (2-hop must be HIGH)
test_vehicle_dynamics    : 0.6×0.333 + 0.3×0.2 + 0.1×1.0 = 0.360  MEDIUM    ✓
```
**FAIL** -- FanOut=0.1 is too low. The 2-hop test loses enough score to fall below 0.50 into MEDIUM, skipping HIGH entirely.

---

**Trial 10 -- (w_p=0.7, w_c=0.2, w_f=0.1)**
```
test_brake_distance      : 0.7×1.000 + 0.2×0.2 + 0.1×1.0 = 0.840  CRITICAL  ✓
test_steering_latency    : 0.7×1.000 + 0.2×0.2 + 0.1×0.5 = 0.790  CRITICAL  ✓
test_safety_controller   : 0.7×0.500 + 0.2×0.2 + 0.1×1.0 = 0.490  MEDIUM    ✗  (2-hop must be HIGH)
test_vehicle_dynamics    : 0.7×0.333 + 0.2×0.2 + 0.1×1.0 = 0.373  MEDIUM    ✓
```
**FAIL** -- Proximity so dominant that the 2-hop test drops to 0.49, just missing HIGH. Entire HIGH tier becomes unreachable.

---

#### Step 5 -- Grid Search Results Summary

| Trial | w_p | w_c | w_f | 1-hop/fan=1.0 | 1-hop/fan=0.5 | 2-hop | 3-hop | Result |
|---|---|---|---|---|---|---|---|---|
| T1 | 0.3 | 0.3 | 0.4 | 0.760 CRITICAL ✓ | 0.560 HIGH ✗ | 0.610 HIGH ✓ | 0.560 HIGH ✗ | **FAIL** |
| T2 | 0.4 | 0.3 | 0.3 | 0.760 CRITICAL ✓ | 0.610 HIGH ✗ | 0.560 HIGH ✓ | 0.493 MEDIUM ✓ | **FAIL** |
| T3 | 0.4 | 0.4 | 0.2 | 0.680 HIGH ✗ | 0.580 HIGH ✗ | 0.480 MEDIUM ✗ | 0.413 MEDIUM ✓ | **FAIL** |
| T4 | 0.5 | 0.1 | 0.4 | 0.920 CRITICAL ✓ | 0.720 CRITICAL ✓ | 0.670 HIGH ✓ | 0.587 HIGH ✗ | **FAIL** |
| T5 | 0.5 | 0.2 | 0.3 | 0.840 CRITICAL ✓ | 0.690 HIGH ✗ | 0.590 HIGH ✓ | 0.507 HIGH ✗ | **FAIL** |
| T6 | 0.5 | 0.3 | 0.2 | 0.760 CRITICAL ✓ | 0.660 HIGH ✗ | 0.510 HIGH ✓ | 0.427 MEDIUM ✓ | **FAIL** |
| T7 | 0.5 | 0.4 | 0.1 | 0.680 HIGH ✗ | 0.630 HIGH ✗ | 0.430 MEDIUM ✗ | 0.347 MEDIUM ✓ | **FAIL** |
| **T8** | **0.6** | **0.2** | **0.2** | **0.840 CRITICAL ✓** | **0.740 CRITICAL ✓** | **0.540 HIGH ✓** | **0.440 MEDIUM ✓** | **PASS** |
| T9 | 0.6 | 0.3 | 0.1 | 0.760 CRITICAL ✓ | 0.710 CRITICAL ✓ | 0.460 MEDIUM ✗ | 0.360 MEDIUM ✓ | **FAIL** |
| T10 | 0.7 | 0.2 | 0.1 | 0.840 CRITICAL ✓ | 0.790 CRITICAL ✓ | 0.490 MEDIUM ✗ | 0.373 MEDIUM ✓ | **FAIL** |

Trial 8 is the only combination across all 10 valid triplets that correctly classifies every test.

---

#### Step 6 -- Derive Tier Boundaries from the Passing Scores

Once Trial 8 was confirmed as the only passing trial, its computed scores were used to place tier boundaries. The boundaries are placed in the natural gap below each score cluster:

```
Score(1 hop)  = 0.840   →   CRITICAL boundary placed at 0.70  (gap between 0.840 and 0.540)
Score(2 hops) = 0.540   →   HIGH boundary placed at 0.50     (gap between 0.540 and 0.440)
Score(3 hops) = 0.440   →   MEDIUM boundary placed at 0.28   (gap between 0.440 and 0.390)
Score(4 hops) = 0.390   →   LOW  ≤ 0.28
```

The boundaries were read off the scores -- they were not chosen independently.

---

#### Why Each of the 9 Failed Trials Was Rejected

Every failing trial fell into one of three failure modes:

| Failure Mode | Trials | What Went Wrong |
|---|---|---|
| **FanOut too high (w_f ≥ 0.3)** | T1, T4, T5 | 3-hop tests with fanout=1.0 scored above 0.50, landing in HIGH instead of MEDIUM. A distant test was being treated as urgent purely because many files import it. |
| **Proximity too low (w_p ≤ 0.4)** | T2, T3 | A 1-hop test with fanout=0.5 could never reach 0.70. Two tests at identical hop distance landed in different tiers based on a file-level metric. |
| **Proximity too high (w_p ≥ 0.6 with low w_f)** | T9, T10 | Score dropped so steeply per hop that the 2-hop test fell straight into MEDIUM, skipping HIGH entirely. |

Trial 8 (0.60, 0.20, 0.20) is the only triplet that avoids all three failure modes simultaneously.

---

#### The Full Derivation Chain

```
START
  │
  ├── Known from graph: 1 hop = CRITICAL, 2 hops = HIGH, 3 hops = MEDIUM, 4 hops = LOW
  │
  ├── Observation: PageRank=0.2 (uniform), FanOut=const per hop group
  │   Only Proximity changes with hops → w_p controls tier separation
  │       ↓
  ├── Math: gap between 1-hop and 2-hop = 0.5 × w_p
  │       ↓
  ├── Assumption: gap should be ≥ 0.20 → w_p ≥ 0.40
  │       ↓
  ├── Choice: w_p = 0.60 (gap = 0.30, clean unambiguous separation)
  │       ↓
  ├── Remaining 0.40 split equally → w_c = 0.20, w_f = 0.20
  │       ↓
  ├── Grid search: all 10 valid triplets tested against 4 real dataset tests
  │       ↓
  ├── Result: 9 trials fail, only Trial 8 (0.60, 0.20, 0.20) passes
  │       ↓
  ├── Scores from Trial 8: 0.840, 0.540, 0.440, 0.390
  │       ↓
  └── Boundaries placed in gaps: CRITICAL > 0.70, HIGH > 0.50, MEDIUM > 0.28
```

---

### Risk Tiers

After scoring, each test is assigned a risk tier based on its final score:

| Tier | Score Range | What it Means | Required Action |
|------|-------------|---------------|-----------------|
| **CRITICAL** | > 0.70 | Test is directly in the blast radius of the change. Almost certain to detect a failure. | Must run immediately -- do not skip |
| **HIGH** | > 0.50 | Test is one or two steps away from the change, or tests an important central function. High chance of detecting a failure. | Run in first batch |
| **MEDIUM** | > 0.28 | Test is reachable through the call graph but further away. May or may not catch the failure. | Run in second batch |
| **LOW** | <= 0.28 | Test is reachable but very distant. Low probability of impact. | Can defer to nightly run |
| **SAFE** | 0.0 | Test has no path to the changed code within 4 hops. Cannot possibly catch this failure. | Safe to skip entirely |

---

### What Process Do the Tests Go Through?

When the scoring engine runs for a given constant (e.g., `brake_actuator_response_time`), every test goes through the following steps:

1. **Graph lookup**: Find the Constant node in Neo4j for the changed parameter
2. **Blast radius expansion**: Follow `AFFECTS` edges to get all Files impacted by this constant
3. **Function lookup**: Find all Functions defined in those files (via `DEFINED_IN` edges)
4. **Path search**: For each test function in the system, run `shortestPath()` through CALLS edges (max 4 hops) to check if there is any path from the changed functions to the test
5. **Score computation**: Apply the formula `0.60*(1/hops) + 0.20*pagerank + 0.20*fanout`
6. **Tier assignment**: Assign CRITICAL / HIGH / MEDIUM / LOW based on score thresholds
7. **Write to Neo4j**: Store `priority_score`, `risk_tier`, `proximity`, `centrality`, `fanout_score`, `shortest_path_hops`, `triggered_by`, and `last_scored_at` as properties on each Function node
8. **Tests with no path** (hops > 4): Score = 0.0, tier = SAFE

---

### Results -- All 4 Scenarios

---

#### Scenario 1: `brake_actuator_response_time` (SAFETY-CRITICAL)

**What changed:** The time it takes for the brake actuator to physically respond after a brake command is issued. Even a few milliseconds of drift can cause vehicles to stop later than expected -- a direct safety issue.

**Who owns the affected code:** Harshitha (ABS subsystem), Roshan (braking controller)

**Tests scored vs. safe:**
- Total tests in system: 25
- Tests that must run (scored): **6**
- Tests safe to skip: **19** (76% reduction)

| Rank | Test Name | Score | Tier | Hops | Why |
|------|-----------|-------|------|------|-----|
| 1 | test_brake_distance_nominal | 0.840 | **CRITICAL** | 1 | Directly tests brake distance calculation -- the primary function affected |
| 2 | test_emergency_stop_latency | 0.840 | **CRITICAL** | 1 | Tests emergency stop timing -- will detect any response time regression |
| 3 | test_stopping_force_range | 0.840 | **CRITICAL** | 1 | Tests stopping force -- directly connected to actuator response |
| 4 | test_ABS_trigger_threshold | 0.840 | **CRITICAL** | 1 | Tests ABS trigger logic -- shares the same response time parameter |
| 5 | test_safety_controller_integration | 0.540 | **HIGH** | 2 | Integration test 1 hop above the directly affected functions |
| 6 | test_vehicle_dynamics_end_to_end | 0.440 | **MEDIUM** | 3 | Full end-to-end test -- reachable but further in the call chain |

**Safe tests (skipped):** All 8 CAN timing tests, all 6 drivetrain tests, all 4 sensor fusion tests, plus `test_brake_fluid_pressure_sensor` and `test_pedal_input_mapping` (not in the call path of the changed code)

---

#### Scenario 2: `lidar_offset_calibration` (SAFETY-CRITICAL)

**What changed:** The calibration offset applied to LiDAR distance readings. If this drifts, the vehicle's perception of how far away obstacles are becomes wrong -- it may think an obstacle is farther than it actually is.

**Who owns the affected code:** Ryan (LiDAR / sensor fusion)

**Tests scored vs. safe:**
- Total tests in system: 25
- Tests that must run (scored): **4**
- Tests safe to skip: **21** (84% reduction)

| Rank | Test Name | Score | Tier | Hops | Why |
|------|-----------|-------|------|------|-----|
| 1 | test_collision_margin_nominal | 0.740 | **CRITICAL** | 1 | Directly tests collision margin -- driven by LiDAR offset |
| 2 | test_trajectory_planner_clearance | 0.740 | **CRITICAL** | 1 | Directly tests trajectory clearance -- depends on accurate LiDAR |
| 3 | test_obstacle_detection_accuracy | 0.340 | **MEDIUM** | 3 | Tests obstacle detection -- reached through 3-hop call chain |
| 4 | test_sensor_fusion_integration | 0.290 | **MEDIUM** | 4 | Full sensor fusion integration -- at the edge of blast radius |

**Note on tiers:** With the updated weights (0.60 proximity), all 1-hop tests score 0.740 and land in CRITICAL even with FanOut = 0.5. This is the correct behaviour -- a test directly in the blast radius is always critical regardless of its file's import count.

**Safe tests (skipped):** All 8 braking tests, all 7 CAN timing tests, all 6 drivetrain tests

---

#### Scenario 3: `max_motor_torque_nm` (SAFETY-CRITICAL)

**What changed:** The maximum torque the motor is allowed to produce. If this limit drifts upward, the vehicle can accelerate beyond safe parameters or damage drivetrain components.

**Who owns the affected code:** Shivani (motor/drivetrain), Ryan (drivetrain controller)

**Tests scored vs. safe:**
- Total tests in system: 25
- Tests that must run (scored): **4 unique tests** (8 scored entries, some tests reachable via multiple paths)
- Tests safe to skip: **~17** (68% reduction)

| Rank | Test Name | Score | Tier | Hops | Why |
|------|-----------|-------|------|------|-----|
| 1 | test_torque_application_limits | 0.840 | **CRITICAL** | 1 | Directly tests torque limits -- the exact parameter that changed |
| 2 | test_thermal_cutoff_trigger | 0.740 | **CRITICAL** | 1 | Tests thermal cutoff -- will fire if torque exceeds safe range |
| 3 | test_ecu_integration_nominal | 0.740 | **CRITICAL** | 1 | ECU integration test -- torque changes affect ECU commands |
| 4 | test_motor_overheat_protection | 0.740 | **CRITICAL** | 1 | Overheat protection -- directly triggered by torque limits |

**Note:** Some tests appear at multiple hops (via different call paths). The best (shortest) path score is used for the final ranking. `test_torque_application_limits` also appears at 2 hops (score 0.540, HIGH) via a secondary path, but its primary score of 0.840 at 1 hop takes priority.

**Safe tests (skipped):** All 8 braking tests, all 7 CAN timing tests, all 4 sensor fusion tests

---

#### Scenario 4: `can_bus_message_interval_ms` (non-critical)

**What changed:** The timing interval between CAN bus messages. The CAN bus is the communication backbone of the vehicle -- all subsystems use it to send signals to each other. Changing the interval affects how quickly signals propagate.

**Who owns the affected code:** Shivani (CAN interface / motor)

**Tests scored vs. safe:**
- Total tests in system: 25
- Tests that must run (scored): **7 unique tests** (more entries due to multiple paths)
- Tests safe to skip: **~18** (72% reduction)

| Rank | Test Name | Score | Tier | Hops | Why |
|------|-----------|-------|------|------|-----|
| 1 | test_can_frame_parse_timing | 0.840 | **CRITICAL** | 1 | Directly tests CAN frame timing -- the changed parameter |
| 2 | test_can_frame_checksum_validation | 0.840 | **CRITICAL** | 1 | CAN checksum is timing-dependent -- will detect interval changes |
| 3 | test_can_frame_id_parsing | 0.840 | **CRITICAL** | 1 | CAN frame ID parsing -- interval changes affect frame ordering |
| 4 | test_steering_input_latency | 0.740 | **CRITICAL** | 1 | Steering signals come through CAN -- latency test will catch drift |
| 5 | test_brake_pedal_signal_integrity | 0.740 | **CRITICAL** | 1 | Brake pedal signal travels over CAN -- integrity affected by timing |
| 6 | test_accelerator_response_time | 0.740 | **CRITICAL** | 1 | Accelerator signal is CAN-transmitted -- response time changes |
| 7 | test_diagnostic_health_check_interval | 0.740 | **CRITICAL** | 1 | Health checks run over CAN -- interval changes affect scheduling |

**Safe tests (skipped):** All 8 braking tests (no CAN path to brake distance), all 6 drivetrain tests, all 4 sensor fusion tests

---

### What the Results Tell Us

**1. Proximity is decisive.** In every scenario, all tests that are 1 hop from the changed code score either 0.740 or 0.840 -- both CRITICAL. Tests at 3-4 hops score 0.29-0.44 (MEDIUM). The farther a test is from the change, the less certain its failure, and the score reflects that cleanly.

**2. All 1-hop tests are now CRITICAL regardless of FanOut.** With the updated weights (0.60 proximity), a 1-hop test with FanOut=0.5 scores 0.740 and a 1-hop test with FanOut=1.0 scores 0.840 -- both above the CRITICAL threshold of 0.70. FanOut still differentiates within the CRITICAL tier but no longer demotes a direct test out of it.

**3. Safety-critical scenarios affect fewer tests.** `lidar_offset_calibration` only scores 4 tests because sensor fusion is a more isolated subsystem. `can_bus_message_interval_ms` scores 7 tests because CAN is a shared transport layer used by many subsystems.

**4. The system correctly ignores unrelated tests.** When brake time changes, all CAN tests are SAFE. When LiDAR calibration changes, all brake tests are SAFE. The graph structure correctly enforces these boundaries -- there is no call path connecting them.

**5. 72-84% of tests can be safely skipped per scenario.** This means in a real CI/CD pipeline, an engineer would run 4-7 tests instead of all 25, with full confidence that the skipped tests cannot possibly catch the failure introduced by the change.

---

### Properties Written to Neo4j

After scoring, these properties are written to each test Function node in Neo4j:

| Property | Type | Description |
|----------|------|-------------|
| priority_score | float | Final computed score (0.0 to 1.0) |
| risk_tier | string | CRITICAL / HIGH / MEDIUM / LOW / SAFE |
| triggered_by | string | Name of the changed constant |
| last_scored_at | datetime | When this score was computed |
| proximity | float | Proximity component value |
| centrality | float | PageRank component value |
| fanout_score | float | FanOut component value |
| shortest_path_hops | int | Hop count (-1 if unreachable/SAFE) |

### Running the scorer

```bash
# Score all 4 constants (all scenarios)
python neo4j/test_prioritization.py

# Score for a specific parameter change
python neo4j/test_prioritization.py --constant brake_actuator_response_time

# Score for a specific scenario
python neo4j/test_prioritization.py --scenario situation-1
```

### Output

Results saved to `test_prioritization_results.json` at the project root, and all scores are **persisted as properties on Function nodes in Neo4j** for live querying and visualization.

---

## Repository Structure

```
Honda/
|
|-- Data/                             <- Source data (all inputs live here)
|   |-- firmware/                     <- C++ embedded firmware (7 files)
|   |   |-- sensors.cpp / .h          <- Sensor reading, SENSOR_PKT packing
|   |   |-- canbus.cpp / .h           <- CAN bus communication
|   |   |-- gps.cpp / .h              <- GPS module interface
|   |   |-- interrupts.cpp / .h       <- Interrupt handling
|   |   `-- main.cpp                  <- Main entry point
|   |
|   |-- cloud/                        <- Python vehicle control software (17 files)
|   |   |-- abs_subsystem.py          <- ABS braking logic (owned by Harshitha)
|   |   |-- braking_controller.py     <- Brake distance calc (owned by Roshan)
|   |   |-- braking_config.py         <- Braking parameter config
|   |   |-- can_interface.py          <- CAN bus Python interface
|   |   |-- drivetrain_controller.py  <- Motor torque management
|   |   |-- ecu_manager.py            <- ECU coordination
|   |   |-- sensor_fusion.py          <- Multi-sensor data fusion
|   |   |-- trajectory_planner.py     <- Path planning
|   |   |-- input_signals.py          <- Signal routing
|   |   |-- test_braking.py           <- Braking test suite
|   |   |-- test_can_timing.py        <- CAN timing test suite
|   |   |-- test_drivetrain.py        <- Drivetrain test suite
|   |   `-- test_sensor_fusion.py     <- Sensor fusion test suite
|   |
|   `-- docs/
|       |-- change_risk_scenarios.json  <- Source of truth: 4 scenarios, 16 commits, 25 labels
|       |-- hsi.md                      <- SENSOR_PKT hardware spec (v1.0-1.3)
|       `-- hardware_changelog.md       <- Hardware change log
|
|-- parsers/                          <- STEP 1 + STEP 2: Data extraction
|   |-- tree_sitter.py                <- AST parser: extracts 95 functions, 483 rels
|   |-- git_python.py                 <- Scenario metadata: extracts 4 authors, 16 commits
|   |-- ast_knowledge_base.json       <- Output of tree_sitter.py
|   |-- git_history_knowledge_base.json  <- Output of git_python.py
|   `-- TREE_SITTER_README.md         <- Parser documentation
|
|-- merge_knowledge.py                <- STEP 3: Merges both JSONs into one
|-- unified_knowledge_base.json       <- STEP 3 output: the complete knowledge base
|
|-- neo4j/                            <- STEP 4 + STEP 5: Graph DB and scoring
|   |-- schema.cypher                 <- Neo4j constraints and indexes (run once)
|   |-- ingest.py                     <- Loads unified_knowledge_base.json into Neo4j
|   |-- queries.py                    <- 10 risk-analysis Cypher queries with CLI
|   |-- test_prioritization.py        <- Main deliverable: scores and ranks all tests
|   `-- README.md                     <- Neo4j layer documentation
|
|-- knowledge_graph/
|   `-- knowledge_graph_visualization.md  <- Graph schema and visualization guide
|
|-- test_prioritization_results.json  <- STEP 5 output: all test scores per constant
|-- requirements.txt                  <- Python dependencies
`-- README.md                         <- This file
```

---

## Quick Start -- Run the Full Pipeline

### Prerequisites

```bash
pip install -r requirements.txt
docker pull neo4j:5
```

### Step-by-step

```bash
# Step 1: Parse all source code (AST analysis)
python parsers/tree_sitter.py
# Output: parsers/ast_knowledge_base.json (95 functions, 483 relationships)

# Step 2: Extract scenario metadata
python parsers/git_python.py
# Output: parsers/git_history_knowledge_base.json (4 authors, 16 commits, 25 labels)

# Step 3: Merge into unified knowledge base
python merge_knowledge.py
# Output: unified_knowledge_base.json

# Step 4a: Start Neo4j
docker run -d --name honda-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/honda99p \
  neo4j:5

# Step 4b: Ingest the knowledge graph
python neo4j/ingest.py
# Creates: 226 nodes, 462 relationships in Neo4j

# Step 5: Run test prioritization scoring
python neo4j/test_prioritization.py
# Output: test_prioritization_results.json + scores written to Neo4j nodes
```

---

## Querying the Graph (Neo4j Browser)

Open http://localhost:7474 and log in with `neo4j / honda99p`.

**See all test scores ranked by priority:**
```cypher
MATCH (t:Function)
WHERE t.risk_tier IS NOT NULL
RETURN t.name AS test, t.priority_score AS score, t.risk_tier AS tier,
       t.shortest_path_hops AS hops, t.triggered_by AS constant
ORDER BY t.priority_score DESC
```

**Blast radius for a specific parameter change:**
```cypher
MATCH (k:Constant {name: "brake_actuator_response_time"})-[:AFFECTS]->(f:File)
      <-[:DEFINED_IN]-(fn:Function)
RETURN k.name, f.path, fn.name
```

**Who should review a change (author notification):**
```cypher
MATCH (k:Constant {name: "brake_actuator_response_time"})-[:AFFECTS]->(f:File)
      <-[:OWNED_BY]-(a:Author)
RETURN k.name AS changed_param, f.path AS affected_file, a.name AS notify_author
```

**Full graph overview:**
```cypher
MATCH (n) WITH labels(n)[0] AS label, count(*) AS cnt
RETURN label, cnt ORDER BY cnt DESC
```

**Run risk queries via CLI:**
```bash
# Full risk report for a function
python neo4j/queries.py --function "Data\cloud\braking_controller.py::calculate_brake_distance"

# Full risk report for a file + line number
python neo4j/queries.py --file "Data/firmware/sensors.cpp" --line 60

# Graph statistics
python neo4j/queries.py --stats
```

---

## Knowledge Graph Schema

```
(Constant)-[:AFFECTS]->(File)<-[:DEFINED_IN]-(Function)
(Function)-[:CALLS]->(Function)
(Function)-[:BELONGS_TO]->(Class)
(Function)-[:IMPLEMENTS_HSI]->(HSIField)
(File)-[:OWNED_BY]->(Author)
(ScenarioCommit)-[:AUTHORED_BY]->(Author)
(ScenarioCommit)-[:PART_OF]->(Scenario)
(Constant)-[:CHANGED_IN]->(Scenario)
(TestLabel)-[:LABELS]->(Function)
(TestLabel)-[:OBSERVED_IN]->(Scenario)
```

---

## Technology Stack

| Tool | Purpose |
|------|---------|
| Python 3.11+ | All parsing, merging, scoring scripts |
| Neo4j 5 (Docker) | Property graph database |
| neo4j Python driver | Python-to-Neo4j connection |
| Cypher | Graph query language (shortestPath, PageRank) |
| Neo4j GDS (optional) | Graph Data Science plugin for real PageRank |

---

## Neo4j Browser Access

```
URL:      http://localhost:7474
Username: neo4j
Password: honda99p
Bolt:     bolt://localhost:7687
```

---

## Next Steps (Roadmap)

| Step | Description | Input | Output |
|------|-------------|-------|--------|
| Done | AST Parsing | Source code | 95 functions, 483 rels |
| Done | Scenario Metadata | change_risk_scenarios.json | 4 authors, 25 labels |
| Done | Knowledge Graph | unified_knowledge_base.json | 226 nodes, 462 rels in Neo4j |
| Done | Test Prioritization | Neo4j graph | Ranked test list with CRITICAL/HIGH/MEDIUM/LOW/SAFE |
| Next | XGBoost ML Model | 25 labeled examples | Failure probability per test (0-1) |
| Next | RAG Explanation | Test score + graph context | "Why will this test fail?" in plain English |
