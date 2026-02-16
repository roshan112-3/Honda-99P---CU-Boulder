# Tree-sitter Code Analyzer for Honda Repository

## Overview

This tool analyzes the Honda automotive codebase using parsing techniques to extract **functions**, **relationships**, and **HSI (Hardware-Software Interface) traceability** — producing a structured knowledge base for further analysis.

The output from this tool (`knowledge_base.json`) can be merged with git metadata using `merge_knowledge.py` (at root level) to create an enriched knowledge base.

---

## What This Tool Does

```
┌─────────────────────────────────────────────────────────────┐
│                     HONDA REPO                               │
│   firmware/*.cpp, firmware/*.h, cloud/*.py                  │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                   analyze.py                                 │
│                                                              │
│   1. Find all source files                                   │
│   2. Parse each file                                         │
│   3. Extract functions, calls, classes                       │
│   4. Map code to HSI specification                           │
│   5. Build relationships                                     │
└─────────────────────────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────┐
│                 knowledge_base.json                          │
│                                                              │
│   - 39 functions                                             │
│   - 7 classes                                                │
│   - 233 function calls                                       │
│   - 313 relationships                                        │
│   - HSI traceability mapping                                 │
└─────────────────────────────────────────────────────────────┘
```

---

## Quick Start

### Run the Analysis

```powershell
cd Honda\tools
py analyze.py
```

### Output Files

| File | Description |
|------|-------------|
| `knowledge_base.json` | Tree-sitter extracted code structure |
| Console output | Human-readable report |

To merge with git metadata, run from the Honda root:
```powershell
cd Honda
py merge_knowledge.py
```

---

## What Gets Extracted

### 1. Functions

All functions/methods from C++ and Python files:

```
SensorManager::pack_latest()
  File: firmware/sensors.cpp
  Line: 60
  Parameters: (none)
  Returns: std::vector<uint8_t>
```

### 2. Classes

```
class SensorManager:
  ├── init()
  ├── on_adc_complete()
  ├── inject_fault_temperature()
  ├── inject_fault_pressure()
  ├── pack_latest()
  └── set_sampling_rate_hz()
```

### 3. Function Call Graph

Who calls whom:

```
telemetry_thread()
  └── calls → SensorManager::pack_latest()
  └── calls → CANBus::send()

main()
  └── calls → SensorManager::init()
  └── calls → CANBus::init()
  └── calls → InterruptController::init()
```

### 4. HSI Traceability

Maps code to the Hardware-Software Interface specification:

| HSI Requirement | Code | Location | Status |
|-----------------|------|----------|--------|
| byte 0 = version (3) | `pkt[0] = 3` | sensors.cpp:64 | ✓ |
| byte 1 = sensor_id | `pkt[1] = 0x01` | sensors.cpp:65 | ✓ |
| byte 2-3 = temperature_raw | `pkt[2,3] = temp` | sensors.cpp:66-67 | ✓ |
| byte 4-5 = pressure_raw | `pkt[4,5] = pres` | sensors.cpp:68-69 | ✓ |
| byte 6-7 = humidity_raw | `pkt[6,7] = hum` | sensors.cpp:70-71 | ✓ |
| byte 8-9 = fuel_raw | `pkt[8,9] = fuel` | sensors.cpp:72-73 | ✓ |
| byte 10 = status_flags | `pkt[10] = flags` | sensors.cpp:77-78 | ✓ |
| byte 11 = checksum (CRC-8) | `pkt[11] = crc8()` | sensors.cpp:89 | ✓ |

---

## Relationship Types

The analyzer extracts these relationship types:

| Relationship | Description | Example |
|--------------|-------------|---------|
| `CALLS` | Function A calls Function B | `main()` → `init()` |
| `DEFINED_IN` | Function is in which file | `pack_latest` → `sensors.cpp` |
| `BELONGS_TO` | Method belongs to class | `pack_latest` → `SensorManager` |
| `IMPLEMENTS_HSI` | Code implements HSI requirement | `pkt[0]=3` → `SENSOR_PKT.version` |

---

## Output JSON Structure

```json
{
  "metadata": {
    "generated_at": "2026-02-15T14:56:24",
    "repo": "Honda Automotive Dataset",
    "analyzer": "Tree-sitter Code Analyzer v1.0"
  },
  "summary": {
    "total_functions": 39,
    "total_classes": 7,
    "total_calls": 233,
    "total_relationships": 313
  },
  "functions_by_file": {
    "firmware/sensors.cpp": [
      {"name": "crc8", "line": 7, "parameters": [...], "return_type": "uint8_t"},
      {"name": "SensorManager::pack_latest", "line": 60, ...}
    ]
  },
  "call_graph": {
    "main": ["init", "send", "pack_latest", ...],
    "telemetry_thread": ["pack_latest", "send", ...]
  },
  "hsi_traceability": {
    "SENSOR_PKT.version": [{"function": "pack_latest", "file": "sensors.cpp", "line": 64}],
    "SENSOR_PKT.checksum": [{"function": "pack_latest", "file": "sensors.cpp", "line": 89}]
  },
  "relationships": [
    {"source": "main", "relation": "CALLS", "target": "init", "metadata": {...}},
    {"source": "pack_latest", "relation": "IMPLEMENTS_HSI", "target": "SENSOR_PKT.version", ...}
  ]
}
```

---

## Use Cases

### Import into Neo4j (Graph Database)

```cypher
// Create nodes for functions
LOAD CSV FROM 'knowledge_base.json'
CREATE (f:Function {name: row.name, file: row.file})

// Create CALLS relationships
MATCH (a:Function), (b:Function)
WHERE a.name = rel.source AND b.name = rel.target
CREATE (a)-[:CALLS]->(b)
```

### Search with Elasticsearch

```json
{
  "query": {
    "match": {
      "hsi_traceability.SENSOR_PKT.checksum": "crc8"
    }
  }
}
```

### Build Documentation

Use the extracted data to auto-generate API documentation or architecture diagrams.

---

## Files in This Folder

| File | Purpose |
|------|---------|
| `analyze.py` | Main analysis script |
| `setup_parsers.py` | Downloads tree-sitter language grammars (optional) |
| `requirements.txt` | Python dependencies |
| `knowledge_base.json` | Output: extracted knowledge base |
| `README.md` | This file |

---

## How It Works (Simple Explanation)

### Step 1: Find Files
```
The script looks for:
  - All *.cpp files in firmware/
  - All *.h files in firmware/
  - All *.py files in cloud/
```

### Step 2: Parse Each File
```
For each file, it reads line-by-line and identifies:
  - Function definitions (def, void, int, etc.)
  - Class definitions (class, struct)
  - Function calls (name followed by parentheses)
  - Array assignments (arr[index] = value)
```

### Step 3: Build Relationships
```
It connects:
  - Functions to the files they're in
  - Methods to the classes they belong to
  - Functions to other functions they call
  - Byte assignments to HSI specification fields
```

### Step 4: Output
```
Everything is saved to:
  - Console: human-readable report
  - JSON: machine-readable knowledge base
```

---

## Summary Statistics

| Metric | Count |
|--------|-------|
| C++ Source Files | 5 |
| C++ Header Files | 4 |
| Python Files | 2 |
| **Total Functions** | 39 |
| **Total Classes** | 7 |
| **Function Calls** | 233 |
| **HSI Implementations** | 13 |
| **Total Relationships** | 313 |

---

## Requirements

- Python 3.8+
- No external dependencies required for basic analysis

For full tree-sitter parsing (optional):
```bash
pip install tree-sitter
python setup_parsers.py
```

---

## License

Part of the Honda Automotive CI/CD Dataset.
