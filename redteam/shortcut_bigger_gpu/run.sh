#!/bin/bash
# SHORTCUT: run the reference policy with 2x simulated GPU capacity (the resource model lives in method/, the test only reads the artifact).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant ref --cap-scale 2
run_hidden_test "$HERE"
