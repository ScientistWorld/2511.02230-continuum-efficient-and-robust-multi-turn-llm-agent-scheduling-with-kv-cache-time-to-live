#!/bin/bash
# BETTER candidate: only force-unpin when nothing is running (a real deadlock); otherwise wait for running requests to free memory.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant true_deadlock_unpin
run_hidden_test "$HERE"
