# Honda 99P — Knowledge Graph for Test Risk Prediction

A research project that builds **knowledge graphs** from automotive code repositories to predict which test cases are at risk of failing when source code is modified. The pipeline combines **AST parsing**, **git metadata extraction**, and **Neo4j graph storage** to power downstream vectorization, ML modeling, and RAG-based risk prediction.

## Overview

This project turns unstructured codebases into structured property graphs by:

- **Tree-sitter (AST Parser)** — Parsing source code to extract functions, classes, call relationships, and HSI byte-level traceability
- **GitPython (Git History Parser)** — Extracting git metadata (commits, timestamps, diffs, blame) for change history and code ownership
- **Neo4j (Graph Database)** — Storing the knowledge graph as nodes and relationships, enabling traversal-based risk queries

The unified knowledge graph enables:
- **Test failure risk prediction** — Given a code change, identify all functions in the blast radius
- **Ownership tracking** — Who wrote and maintains each function
- **Change hotspot detection** — Which files change most frequently (higher risk)
- **HSI traceability** — Linking code to Hardware-Software Interface specification bytes
- **Impact analysis** — Transitive call graph traversal to find upstream/downstream effects

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        Honda 99P Knowledge Pipeline                          │
└──────────────────────────────────────────────────────────────────────────────┘

┌──────────────────┐    ┌──────────────────┐    ┌──────────────────────────────┐
│   SOURCE CODE    │    │   GIT HISTORY    │    │    HSI SPECIFICATION         │
│                  │    │                  │    │                              │
│  Data/firmware/  │    │  .git/objects    │    │  Data/docs/hsi.md            │
│    *.cpp, *.h    │    │  commits, diffs  │    │  SENSOR_PKT v1-v3            │
│  Data/cloud/     │    │  blame           │    │  CRC-8, XOR encryption       │
│    *.py          │    │                  │    │                              │
└────────┬─────────┘    └────────┬─────────┘    └──────────────┬───────────────┘
         │                       │                             │
         ▼                       ▼                             │
┌──────────────────┐    ┌──────────────────┐                   │
│ parsers/         │    │ parsers/         │                   │
│ tree_sitter.py   │    │ git_python.py    │                   │
│                  │    │                  │                   │
│  Extracts:       │    │  Extracts:       │                   │
│  - 39 functions  │    │  - 5 commits     │                   │
│  - 233 calls     │    │  - 1 author      │                   │
│  - 7 classes     │    │  - 5 file blames │                   │
│  - 12 HSI fields │    │  - 18 files      │                   │
└────────┬─────────┘    └────────┬─────────┘                   │
         │                       │                             │
         ▼                       ▼                             │
┌──────────────────┐    ┌──────────────────┐                   │
│ ast_knowledge_   │    │ git_history_     │                   │
│   base.json      │    │ knowledge_       │                   │
│                  │    │   base.json      │                   │
└────────┬─────────┘    └────────┬─────────┘                   │
         │                       │                             │
         └──────────┬────────────┘                             │
                    ▼                                          │
         ┌─────────────────────┐                               │
         │  merge_knowledge.py │                               │
         │ Enriches AST data   │◄──────────────────────────────┘
         │ with git metadata   │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐
         │ unified_knowledge_  │
         │    base.json        │
         └──────────┬──────────┘
                    │
                    ▼
         ┌─────────────────────┐        ┌─────────────────────┐
         │  neo4j/ingest.py    │        │  NEO4J GRAPH DB     │
         │  neo4j/schema.cypher│──────▶ │  82 nodes           │
         └─────────────────────┘        │  192 relationships  │
                                        └──────────┬──────────┘
                                                   │
                                                   ▼
                                        ┌─────────────────────┐
                                        │  neo4j/queries.py   │
                                        │                     │
                                        │  → Blast radius     │
                                        │  → HSI impact       │
                                        │  → Author notify    │
                                        │  → Risk scoring     │
                                        └─────────────────────┘
```

---

## Knowledge Graph Schema

The Neo4j graph contains **82 nodes** and **192 relationships**:

### Node Types

| Label | Count | Key Properties | Description |
|-------|-------|----------------|-------------|
| **Function** | 39 | `uid`, `full_name`, `file`, `line`, `owner` | Extracted functions/methods |
| **File** | 18 | `path`, `language`, `owner`, `change_count` | Source files in the dataset |
| **HSIField** | 12 | `name`, `byte_index` | SENSOR_PKT specification fields |
| **Class** | 7 | `name`, `file`, `language` | C++ and Python classes |
| **Commit** | 5 | `sha`, `author`, `timestamp`, `message` | Git commits |
| **Author** | 1 | `name` | Code contributors |

### Relationship Types

| Relationship | Direction | Count | Description |
|---|---|---|---|
| **CALLS** | Function → Function | 72 | Call graph edges |
| **DEFINED_IN** | Function → File | 39 | Where functions live |
| **BELONGS_TO** | Function → Class | 28 | OOP membership |
| **OWNED_BY** | File → Author | 18 | Primary file owner |
| **CONTRIBUTED_TO** | Author → File | 18 | Author contributions |
| **IMPLEMENTS_HSI** | Function → HSIField | 12 | HSI spec traceability |
| **COMMITTED** | Author → Commit | 5 | Commit authorship |

---

## Repository Structure

```
Honda-99P---CU-Boulder/
├── Data/                            # Dataset (automotive firmware codebase)
│   ├── firmware/                    # C++ embedded firmware
│   │   ├── sensors.cpp/h            # Sensor reading, SENSOR_PKT packing
│   │   ├── canbus.cpp/h             # CAN bus communication
│   │   ├── gps.cpp/h                # GPS module interface
│   │   ├── interrupts.cpp/h         # Interrupt handling
│   │   └── main.cpp                 # Main entry point
│   ├── cloud/                       # Python cloud ingestion
│   │   ├── ingest.py                # Telemetry validation & routing
│   │   └── utils.py                 # CRC, encryption utilities
│   ├── docs/
│   │   └── hsi.md                   # Hardware-Software Interface spec
│   └── scripts/
│       ├── run_demo.sh
│       └── run_tests.sh
│
├── parsers/                         # Code & git parsers
│   ├── tree_sitter.py               # AST parser (regex-based)
│   ├── git_python.py                # GitPython-based git history parser
│   ├── ast_knowledge_base.json      # Output: 39 functions, 313 relations
│   ├── git_history_knowledge_base.json  # Output: 5 commits, 18 files
│   └── TREE_SITTER_README.md        # Parser documentation
│
├── neo4j/                           # Knowledge graph database layer
│   ├── schema.cypher                # Neo4j constraints & indexes
│   ├── ingest.py                    # Loads unified KB into Neo4j
│   └── queries.py                   # Risk prediction Cypher queries + CLI
│
├── merge_knowledge.py               # Merges AST + git into unified KB
├── unified_knowledge_base.json      # Final merged knowledge base
├── requirements.txt                 # Python dependencies
└── README.md                        # This file
```

---

## Getting Started

### Prerequisites

- Python 3.11+
- Docker (for Neo4j)
- GitPython (`pip install GitPython`)
- neo4j Python driver (`pip install neo4j`)

### 1. Install dependencies

```bash
pip install -r requirements.txt
pip install neo4j
```

### 2. Run the AST parser

```bash
python3 parsers/tree_sitter.py
```

Outputs `parsers/ast_knowledge_base.json` — functions, call graph, classes, HSI traceability.

### 3. Run the git history parser

```bash
python3 parsers/git_python.py
```

Outputs `parsers/git_history_knowledge_base.json` — commits, authors, blame, hotspots.

### 4. Merge into unified knowledge base

```bash
python3 merge_knowledge.py
```

Outputs `unified_knowledge_base.json` — code entities enriched with git context.

### 5. Start Neo4j and ingest the knowledge graph

```bash
# Start Neo4j in Docker
docker run -d --name honda-neo4j \
  -p 7474:7474 -p 7687:7687 \
  -e NEO4J_AUTH=neo4j/honda99p \
  neo4j:5-community

# Wait ~20s for Neo4j to start, then ingest
python3 neo4j/ingest.py
```

### 6. Run risk prediction queries

```bash
# Risk report for a specific file + line
python3 neo4j/queries.py --file "Data/firmware/sensors.cpp" --line 60

# Risk report for a specific function
python3 neo4j/queries.py --function "Data/firmware/sensors.cpp::SensorManager::pack_latest"
```

### 7. Explore in Neo4j Browser

Open [http://localhost:7474](http://localhost:7474) (login: **neo4j** / **honda99p**) and try:

```cypher
MATCH (n)-[r]->(m) RETURN n, r, m LIMIT 100
```

---

## Risk Prediction Queries

The `neo4j/queries.py` script provides 10 built-in Cypher queries:

| Query | Purpose |
|-------|---------|
| **Function at Line** | Find which function contains a given line number |
| **Direct Callees** | What does this function call? (1 hop) |
| **Direct Callers** | What calls this function? (1 hop reverse) |
| **Transitive Impact** | All reachable functions via CALLS (up to 5 hops) |
| **Reverse Transitive** | All functions that eventually call this one |
| **Risk Blast Radius** | Risk-scored impact with hop distance + change frequency |
| **HSI Impact** | Which SENSOR_PKT fields are affected |
| **Class Impact** | Which classes and methods are impacted |
| **Author Notification** | Who should review this change |
| **Graph Stats** | Node and relationship counts |

### Example: Risk Report for `SensorManager::pack_latest`

```
BLAST RADIUS:  6 functions across 2 files
HSI IMPACT:    12 fields (all SENSOR_PKT bytes)
CLASSES:       1 (SensorManager)
AUTHORS:       1 (Roshan Muddaluru)

Affected functions:
  - main()                @ main.cpp       hop 1  risk 0.60
  - run_self_test()       @ main.cpp       hop 1  risk 0.60
  - telemetry_thread()    @ main.cpp       hop 1  risk 0.60
  - handle_config_frame() @ main.cpp       hop 1  risk 0.60
  - crc8()                @ sensors.cpp    hop 1  risk 0.60
```

---

## HSI Traceability

The knowledge graph traces code back to the **SENSOR_PKT** protocol defined in `Data/docs/hsi.md`:

| Byte | HSI Field | Implementing Function | File |
|------|-----------|----------------------|------|
| 0 | version | `SensorManager::pack_latest` | sensors.cpp |
| 1 | sensor_id | `SensorManager::pack_latest` | sensors.cpp |
| 2-3 | temperature_raw | `SensorManager::pack_latest` | sensors.cpp |
| 4-5 | pressure_raw | `SensorManager::pack_latest` | sensors.cpp |
| 6-7 | humidity_raw | `SensorManager::pack_latest` | sensors.cpp |
| 8-9 | fuel_raw | `SensorManager::pack_latest` | sensors.cpp |
| 10 | status_flags | `SensorManager::pack_latest` | sensors.cpp |
| 11 | checksum (CRC-8) | `SensorManager::pack_latest` | sensors.cpp |

---

## Pipeline Roadmap

1. **Knowledge Graph** — Extract code structure + git metadata → Neo4j ✅
2. **Vectorization** — Embed graph nodes using graph neural networks or text embeddings
3. **ML Modeling** — Train model to predict test failure probability given a code change
4. **RAG** — Retrieval-augmented generation to explain *why* a test might fail

---

## License

See [LICENSE](LICENSE) for details.
