#!/bin/bash
# BETTER candidate: warm-start the per-tool history with tool durations from a separate, different-seed trace (paper Sec. 4.2: statistics collected before serving avoid cold start).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant warm_history
run_hidden_test "$HERE"
