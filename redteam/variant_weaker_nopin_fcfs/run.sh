#!/bin/bash
# WEAKER: key idea removed -- program-level FCFS priority kept, but TTL is always 0 (never retain state across a tool call).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant nopin_fcfs
run_hidden_test "$HERE"
