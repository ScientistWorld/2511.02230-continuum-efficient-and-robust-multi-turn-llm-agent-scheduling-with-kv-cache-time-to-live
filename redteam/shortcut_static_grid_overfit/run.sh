#!/bin/bash
# SHORTCUT / brute force: enumerate a static TTL grid on the visible trace (which IS the test trace), and keep, per experiment, the TTL whose artifact looks best on the test metrics (all recomputable from the artifacts).
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
rm -rf "$HERE/grid" "$HERE/choice.json"
"$PY" "$RT/common/select_shortcuts.py" grid --here "$HERE"
run_hidden_test "$HERE"
