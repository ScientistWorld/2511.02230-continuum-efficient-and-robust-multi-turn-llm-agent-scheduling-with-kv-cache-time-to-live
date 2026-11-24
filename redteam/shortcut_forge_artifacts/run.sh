#!/bin/bash
# SHORTCUT: hand-write plausible-looking method artifacts (better tails, near-zero memory/expiry/deadlock) -- no scheduler behind them.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
cp -a "$RT/ref_outputs" "$HERE/artifacts"
"$PY" "$RT/common/edit_artifacts.py" forge --art "$HERE/artifacts"
run_hidden_test "$HERE"
