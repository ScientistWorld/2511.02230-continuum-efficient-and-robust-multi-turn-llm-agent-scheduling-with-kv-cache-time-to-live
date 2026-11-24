#!/bin/bash
# WEAKER: no method at all -- the method entry is the vLLM end-of-turn-eviction baseline (fails the task).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant vllm_as_method
run_hidden_test "$HERE"
