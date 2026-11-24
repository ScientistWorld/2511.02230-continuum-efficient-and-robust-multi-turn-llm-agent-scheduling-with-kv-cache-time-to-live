#!/bin/bash
# SHORTCUT (degenerate): admission control never admits the 10% longest programs; completion-time percentiles are computed over completed programs only.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant starve -- --starve-frac 0.1
run_hidden_test "$HERE"
