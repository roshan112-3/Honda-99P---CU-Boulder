# Parsers -- Code & Metadata Extraction

This folder contains two parsers that form the first two steps of the Honda 99P knowledge graph pipeline.

---

## Overview

```
Data/                                 parsers/
|-- firmware/*.cpp, *.h      --->     tree_sitter.py      --->  ast_knowledge_base.json
|-- cloud/*.py                        (AST parsing)             95 functions, 483 rels
|
|-- docs/change_risk_        --->     git_python.py       --->  git_history_knowledge_base.json
|     scenarios.json                  (metadata extract)        4 authors, 16 commits, 25 labels
```

These two JSON outputs are then merged by `merge_knowledge.py` (at root) into `unified_knowledge_base.json`, which feeds into Neo4j.

---

## Parser 1: tree_sitter.py (AST Code Analysis)

### What it does

Reads all source files under `Data/` and extracts code structure using regex-based parsing:

- **Function definitions** -- name, file, line number, parameters, return type
- **Class definitions** -- name, file, members, line range
- **Function call edges** -- who calls whom (builds the call graph)
- **HSI traceability** -- maps byte-level array assignments to SENSOR_PKT spec fields

### Run it

```bash
python parsers/tree_sitter.py
```

### Output: ast_knowledge_base.json

| Metric | Count |
|--------|-------|
| Functions | 95 |
| Classes | 7 |
| Function calls | 347 |
| Relationships | 483 |
| HSI implementations | 13 |
| Files analyzed | 27 |

### Languages parsed

| Language | Source Directory | File Types |
|----------|-----------------|------------|
| C++ | Data/firmware/ | .cpp, .h |
| Python | Data/cloud/ | .py |

### Relationship types extracted

| Relationship | Description | Example |
|---|---|---|
| `CALLS` | Function A calls Function B | `main()` -> `init()` |
| `DEFINED_IN` | Function lives in file | `pack_latest` -> `sensors.cpp` |
| `BELONGS_TO` | Method belongs to class | `pack_latest` -> `SensorManager` |
| `IMPLEMENTS_HSI` | Code implements HSI byte | `pkt[0]=3` -> `SENSOR_PKT.version` |

### HSI traceability

Maps source code to the **SENSOR_PKT** protocol defined in `Data/docs/hsi.md`:

| Byte | HSI Field | Function | File | Line |
|------|-----------|----------|------|------|
| 0 | version | pack_latest | sensors.cpp | 64 |
| 1 | sensor_id | pack_latest | sensors.cpp | 65 |
| 2-3 | temperature_raw | pack_latest | sensors.cpp | 66-67 |
| 4-5 | pressure_raw | pack_latest | sensors.cpp | 68-69 |
| 6-7 | humidity_raw | pack_latest | sensors.cpp | 70-71 |
| 8-9 | fuel_raw | pack_latest | sensors.cpp | 72-73 |
| 10 | status_flags | pack_latest | sensors.cpp | 77-78 |
| 11 | checksum (CRC-8) | pack_latest | sensors.cpp | 89 |

---

## Parser 2: git_python.py (Scenario Metadata Extraction)

### What it does

Reads `Data/docs/change_risk_scenarios.json` and extracts all metadata needed for the knowledge graph and ML training. This parser does **NOT** require a `.git` directory or network access -- everything comes from the `Data/` folder.

### Why not use git history?

The Honda GitHub repo's git log only shows one author (Roshan) pushing the entire dataset. The real authorship and commit history is simulated inside `change_risk_scenarios.json`, which defines 4 distinct authors and 16 tagged commits across 4 scenarios. This file is the **source of truth** for all metadata.

### Run it

```bash
python parsers/git_python.py
```

### Output: git_history_knowledge_base.json

| Metric | Count |
|--------|-------|
| Authors | 4 (Harshitha, Roshan, Ryan, Shivani) |
| Commits | 16 (H-023, R-041, S-078, R-019, H-057, S-092, S-093, H-009, S-031, RY-011, R-055, R-007, H-031, H-032, H-033, S-044) |
| Scenarios | 4 |
| Labeled test examples | 25 (19 failures, 6 passes) |
| Files with ownership | 12 |

### What gets extracted

**Authors and ownership:**
- 4 authors with their roles (ABS owner, hardware integration, LiDAR calibration, etc.)
- File ownership mapping (which author owns which file based on commit roles)

**Commits:**
- 16 tagged commits with author, role, artifact, timing, and scenario ID
- Artifact-to-file mapping (e.g., `apply_ABS_threshold()` -> `Data/cloud/abs_subsystem.py`)

**Scenarios:**
- 4 change risk scenarios with parameter name, before/after values, and type
- Each scenario has 3-5 commits showing cross-team change propagation

**Labeled examples (for ML):**
- 25 test examples with binary labels (1 = fail, 0 = pass)
- Engineered features: shortest_path, hw_sw_sync_lag_days, downstream_test_count, churn_rate, cofailure_count, is_cross_boundary_change, author_is_hw_team, param_is_safety_critical

---

## JSON Output Structure

### ast_knowledge_base.json

```json
{
  "metadata": {"analyzer": "Tree-sitter Code Analyzer v1.0"},
  "summary": {"total_functions": 95, "total_classes": 7, "total_calls": 347},
  "functions_by_file": {
    "Data\\cloud\\braking_controller.py": [
      {"name": "calculate_brake_distance", "line": 5, "parameters": [...]}
    ]
  },
  "call_graph": {"calculate_brake_distance": ["get_brake_actuator_response_time_ms"]},
  "hsi_traceability": {"SENSOR_PKT.version": [{"function": "pack_latest", ...}]},
  "relationships": [{"source": "main", "relation": "CALLS", "target": "init"}]
}
```

### git_history_knowledge_base.json

```json
{
  "summary": {"total_commits": 16, "total_authors": 4, "total_scenarios": 4},
  "scenario_authors": ["Harshitha", "Roshan", "Ryan", "Shivani"],
  "scenario_commits": [
    {"tag": "H-023", "author": "Harshitha", "role": "ABS subsystem owner", ...}
  ],
  "scenarios": [
    {"id": "situation-1", "title": "Brake actuator response time drifted", ...}
  ],
  "labeled_examples": [
    {"test": "test_brake_distance_nominal", "label": 1, "shortest_path": 1, ...}
  ],
  "author_ownership": {"Data/cloud/abs_subsystem.py": {"primary_author": "Harshitha"}}
}
```

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `tree_sitter.py` | AST parser -- extracts functions, calls, classes, HSI |
| `git_python.py` | Scenario metadata extractor -- reads Data/ folder only |
| `ast_knowledge_base.json` | Output: 95 functions, 7 classes, 483 relationships |
| `git_history_knowledge_base.json` | Output: 4 authors, 16 commits, 25 labels |
| `TREE_SITTER_README.md` | This file |

---

## Requirements

- Python 3.11+
- No external dependencies required (both parsers use only the standard library)
