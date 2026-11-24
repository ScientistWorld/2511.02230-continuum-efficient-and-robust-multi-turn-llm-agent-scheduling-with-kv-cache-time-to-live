#!/bin/bash
# Ablation: never leave the cold-start TTL T_default=ln(benefit); no tool-history CDF.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant coldstart_only
run_hidden_test "$HERE"
