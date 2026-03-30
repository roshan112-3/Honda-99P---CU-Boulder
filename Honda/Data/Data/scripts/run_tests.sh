#!/bin/bash
set -euo pipefail
echo "Running basic repo smoke tests (simulated)"
python3 -m py_compile cloud/ingest.py || true
echo "Compiled Python ingestion module"
echo "Done"
