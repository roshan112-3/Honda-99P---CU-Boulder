# Honda 99P — Knowledge Graph for Test Risk Prediction

A research project that builds **knowledge graphs** from code repositories to predict which test cases are at risk of failing when source code is modified.

## Overview

This project turns unstructured codebases into structured graphs by:

- **Tree-sitter** — Parsing source code into Abstract Syntax Trees (ASTs) to extract functions, classes, and call relationships
- **GitPython** — Extracting git metadata (commits, timestamps, diffs, blame) to understand change history and co-evolution of code

Nodes and edges derived from the AST and git history can then be used to model dependencies between code units and tests, enabling failure-risk prediction.

## Repository Structure

```
├── Data/                 # Sample codebase (automotive firmware + cloud ingestion)
│   ├── firmware/         # C++ (sensors, CAN bus, interrupts)
│   ├── cloud/            # Python ingestion service
│   ├── scripts/          # Test and demo scripts
│   └── docs/             # HSI specification
├── parsers/              # Extraction tools
│   └── git_parser.py     # GitPython-based commit/diff/blame parser
├── requirements.txt
└── README.md
```

## Getting Started

1. **Install dependencies**

   ```bash
   pip install -r requirements.txt
   ```

2. **Run the git parser**

   ```bash
   python parsers/git_parser.py
   ```

   This prints a summary of commits, diffs, and blame for the `Data/` repository.

3. **Use the parser in your own code**

   ```python
   from parsers.git_parser import GitParser, commit_to_dict, file_change_to_dict

   parser = GitParser("Data")
   for commit in parser.iter_commits(max_count=10):
       changes = parser.get_commit_diff(commit.sha)
       # ... build your graph
   ```

## Dataset

The `Data/` folder contains a simulated automotive software project (firmware in C++, cloud ingestion in Python) with a staged git history. It is designed for experimenting with tree-sitter, git analysis, and knowledge graph construction. See `Data/README.md` for details on the dataset.

## License

See [LICENSE](LICENSE) if available.
