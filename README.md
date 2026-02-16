# Honda 99P — Knowledge Graph for Test Risk Prediction

A research project that builds **knowledge graphs** from code repositories to predict which test cases are at risk of failing when source code is modified.

## Overview

This project turns unstructured codebases into structured graphs by:

- **Tree-sitter** — Parsing source code into Abstract Syntax Trees (ASTs) to extract functions, classes, and call relationships
- **GitPython** — Extracting git metadata (commits, timestamps, diffs, blame) to understand change history and code ownership

The unified knowledge base enriches code entities with version control context, enabling:
- **Ownership tracking** — Who wrote and maintains each function
- **Change hotspot detection** — Which files change most frequently
- **HSI traceability** — Linking code to Hardware-Software Interface specifications
- **Failure risk prediction** — Identifying high-risk code changes

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                          Honda 99P Knowledge Pipeline                        │
└─────────────────────────────────────────────────────────────────────────────┘

┌─────────────────┐     ┌─────────────────┐     ┌─────────────────────────────┐
│   SOURCE CODE   │     │   GIT HISTORY   │     │     HSI SPECIFICATION      │
│                 │     │                 │     │                             │
│  firmware/*.cpp │     │  .git/objects   │     │  docs/hsi.md                │
│  firmware/*.h   │     │  commits        │     │  SENSOR_PKT v1-v3           │
│  cloud/*.py     │     │  diffs          │     │  CRC-8, XOR encryption      │
└────────┬────────┘     └────────┬────────┘     └──────────────┬──────────────┘
         │                       │                             │
         ▼                       ▼                             │
┌─────────────────┐     ┌─────────────────┐                    │
│   TREE-SITTER   │     │    GITPYTHON    │                    │
│    ANALYZER     │     │     PARSER      │                    │
│                 │     │                 │                    │
│  analyze.py     │     │  git_parser.py  │                    │
│                 │     │                 │                    │
│  Extracts:      │     │  Extracts:      │                    │
│  - Functions    │     │  - Commits      │                    │
│  - Call graph   │     │  - Authors      │                    │
│  - Classes      │     │  - Blame        │                    │
│  - HSI mapping ◄┼─────┼─────────────────┼────────────────────┘
└────────┬────────┘     └────────┬────────┘
         │                       │
         ▼                       ▼
┌─────────────────┐     ┌─────────────────┐
│ knowledge_base  │     │git_knowledge_   │
│    .json        │     │   base.json     │
│                 │     │                 │
│ 39 functions    │     │ 23 commits      │
│ 233 call edges  │     │ 3 authors       │
│ 313 relations   │     │ 36 files        │
└────────┬────────┘     └────────┬────────┘
         │                       │
         └───────────┬───────────┘
                     ▼
          ┌─────────────────────┐
          │   MERGE KNOWLEDGE   │
          │                     │
          │  merge_knowledge.py │
          │                     │
          │  Enriches code      │
          │  entities with git  │
          │  metadata           │
          └──────────┬──────────┘
                     │
                     ▼
          ┌─────────────────────┐
          │  UNIFIED KNOWLEDGE  │
          │       BASE          │
          │                     │
          │  unified_knowledge_ │
          │     base.json       │
          │                     │
          │  ┌───────────────┐  │
          │  │ Function      │  │
          │  │ + owner       │  │
          │  │ + last_mod    │  │
          │  │ + call_graph  │  │
          │  │ + hsi_links   │  │
          │  └───────────────┘  │
          └─────────────────────┘
```

---

## Repository Structure

```
Honda/
├── firmware/                    # C++ embedded firmware
│   ├── sensors.cpp/h            # Sensor reading, SENSOR_PKT creation
│   ├── canbus.cpp/h             # CAN bus communication
│   ├── gps.cpp/h                # GPS module interface
│   ├── interrupts.cpp/h         # Interrupt handling
│   └── main.cpp                 # Main entry point
│
├── cloud/                       # Python cloud ingestion
│   ├── ingest.py                # Telemetry validation & routing
│   └── utils.py                 # CRC, encryption utilities
│
├── docs/
│   └── hsi.md                   # Hardware-Software Interface spec (v1.0-1.3)
│
├── parsers/                     # Git metadata extraction
│   ├── git_parser.py            # GitPython-based parser
│   └── git_knowledge_base.json  # Git metadata output
│
├── tools/                       # Code analysis tools
│   ├── analyze.py               # Tree-sitter code analyzer
│   ├── knowledge_base.json      # Tree-sitter output
│   └── TREE_SITTER_README.md    # Tree-sitter tool documentation
│
├── merge_knowledge.py           # Merges tree-sitter + git outputs
├── unified_knowledge_base.json  # Final merged knowledge base
│
├── scripts/
│   ├── run_demo.sh              # Demo script
│   └── run_tests.sh             # Test runner
│
├── requirements.txt             # Project dependencies
├── LICENSE
└── README.md                    # This file
```

---

## Getting Started

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Run Tree-sitter code analysis

```bash
python tools/analyze.py
```

Outputs:
- `tools/knowledge_base.json` — Functions, call graph, HSI traceability

### 3. Run GitPython metadata extraction

```bash
python parsers/git_parser.py
```

Outputs:
- `parsers/git_knowledge_base.json` — Commits, authors, blame, hotspots

### 4. Merge into unified knowledge base

```bash
python merge_knowledge.py
```

Outputs:
- `unified_knowledge_base.json` — Enriched code entities with git context

---

## Output Structure

### Unified Knowledge Base Schema

```json
{
  "metadata": {
    "generated_at": "2026-02-15T...",
    "analyzers": ["Tree-sitter v1.0", "GitPython v1.0"]
  },
  "summary": {
    "total_functions": 39,
    "total_commits": 23,
    "total_authors": 3
  },
  "functions_by_file": {
    "firmware/sensors.cpp": [
      {
        "name": "SensorHub::build_packet",
        "line": 45,
        "git_context": {
          "file_owner": "OpenCode",
          "last_modified": "2026-02-13T16:53:12",
          "last_modified_by": "OpenCode",
          "contributors": ["OpenCode", "Roshan"]
        }
      }
    ]
  },
  "call_graph": { "SensorHub::read_all": ["read_temperature", "read_humidity"] },
  "hsi_traceability": { "SENSOR_PKT.version": [...] },
  "git_insights": {
    "change_hotspots": [{"file": "docs/hsi.md", "changes": 12}],
    "recent_commits": [...]
  }
}
```

---

## Key Information Extracted from Git

For knowledge base enrichment, the following git metadata is most valuable:

| Metadata | Purpose |
|----------|---------|
| **Author** | Code ownership — who to ask about this code |
| **Timestamp** | Recency — when was this last touched |
| **Commit Message** | Intent — why was this change made |
| **Blame** | Line-level authorship — who wrote each line |
| **Change Frequency** | Hotspots — frequently modified = higher risk |
| **Co-change Patterns** | Dependencies — files that change together |

---

## HSI Traceability

The codebase implements the **SENSOR_PKT** protocol defined in [docs/hsi.md](docs/hsi.md):

| Byte | Field | Implementation |
|------|-------|----------------|
| 0 | version | `pkt[0] = HSI_VERSION` |
| 1 | sensor_id | `pkt[1] = id` |
| 2-3 | temperature_raw | `pkt[2..3] = temp` |
| 4-5 | pressure_raw | `pkt[4..5] = pressure` |
| 6-7 | humidity_raw | `pkt[6..7] = humidity` |
| 8-9 | fuel_raw | `pkt[8..9] = fuel` |
| 10 | status_flags | `pkt[10] = flags` |
| 11 | checksum | `pkt[11] = crc8(pkt[0..10])` |

---

## Use Cases

### 1. Risk Prediction

Given a code change, predict which tests might fail:
```python
# Load unified knowledge base
with open("tools/unified_knowledge_base.json") as f:
    kb = json.load(f)

# Find functions in changed file
changed_file = "firmware/sensors.cpp"
affected_functions = kb["functions_by_file"].get(changed_file, [])

# Check call graph for downstream impact
for func in affected_functions:
    callers = find_callers(kb["call_graph"], func["name"])
    # → These callers' tests may be affected
```

### 2. Code Review Routing

Route code reviews to the right person:
```python
# Find owner of changed file
ownership = kb["git_insights"]["file_ownership"]
owner = ownership[changed_file]["primary_author"]
# → Assign review to owner
```

### 3. Technical Debt Detection

Find code hotspots that may need refactoring:
```python
hotspots = kb["git_insights"]["change_hotspots"]
for hs in hotspots[:5]:
    print(f"{hs['file']}: {hs['changes']} changes → candidate for refactoring")
```

---

## License

See [LICENSE](LICENSE) if available.
