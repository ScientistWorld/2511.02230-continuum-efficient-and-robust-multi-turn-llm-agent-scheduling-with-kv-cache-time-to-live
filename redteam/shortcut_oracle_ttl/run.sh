#!/bin/bash
# SHORTCUT: TTL = the true duration of the *upcoming* tool call, read from the visible trace file (data/workloads/*.json carries tool_time_s for every future turn).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant oracle
run_hidden_test "$HERE"
