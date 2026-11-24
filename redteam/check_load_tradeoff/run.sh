#!/bin/bash
# Diagnostic sweep over arrival rate (see sweep.py); not a hidden-test run.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
PY=$(command -v python3 || command -v python)
"$PY" "$HERE/sweep.py" | tee "$HERE/sweep_table.md"
