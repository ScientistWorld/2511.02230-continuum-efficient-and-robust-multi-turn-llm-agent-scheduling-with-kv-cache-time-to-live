#!/bin/bash
# Reference Continuum policy re-run through the gym simulator (fast bit-identical TTL search); must reproduce the reference test scores exactly.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant ref
run_hidden_test "$HERE"
