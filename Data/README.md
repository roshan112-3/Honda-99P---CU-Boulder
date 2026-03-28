# Honda (simulation) - Automotive CI/CD dataset

This repository is a realistic, production-style automotive software project used as a dataset to exercise CI/CD pipelines and code-analysis tooling.

- Languages: C++ (firmware), Python (cloud ingestion)
- Directories: `firmware/`, `cloud/`, `docs/`, `scripts/`
- Contains a Hardware-Software Interface (HSI) specification in `docs/hsi.md` and a staged git history that shows evolving hardware specs and matching software updates.
- Includes staged multi-author safety-regression scenarios in `cloud/` plus structured labels and engineered features in `docs/change_risk_scenarios.json`.
- Dataset authors are intentionally distributed across four simulated contributors: `Roshan`, `Shivani`, `Harshitha`, and `Ryan`.

HSI versions in this simulated repo:
 - v1.0 initial baseline
 - v1.1 add humidity field
 - v2.1 checksum -> CRC-8
 - v1.2 add fuel_level (v3 packet)
 - v1.3 fault injection hooks

Note: This repo is intentionally synthetic but realistic for use as a dataset for tree-sitter, git analysis, and knowledge-graph construction.
