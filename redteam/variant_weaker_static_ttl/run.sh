#!/bin/bash
# WEAKER (paper ablation, Fig. 15): fixed 0.25 s TTL for every tool call instead of the cost-model TTL.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant static -- --static-ttl 0.25
run_hidden_test "$HERE"
