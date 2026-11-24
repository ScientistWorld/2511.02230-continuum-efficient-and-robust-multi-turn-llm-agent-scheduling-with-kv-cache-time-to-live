#!/bin/bash
# SHORTCUT: write impossible values (negative waits/counts/memory, hit rate 10, completed fraction 2, ~0 s tails) into the method artifact.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
cp -a "$RT/ref_outputs" "$HERE/artifacts"
"$PY" "$RT/common/edit_artifacts.py" impossible --art "$HERE/artifacts"
run_hidden_test "$HERE"
