#!/bin/bash
# BRUTE FORCE the paper argues against: pin every tool call for the maximum tool time (45 s), relying on deadlock unpins to make room.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant pin_max
run_hidden_test "$HERE"
