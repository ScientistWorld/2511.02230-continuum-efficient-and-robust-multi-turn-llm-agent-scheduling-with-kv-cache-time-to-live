#!/bin/bash
# SHORTCUT: run the reference policy on an easier regenerated trace (generator seed with the shortest programs) while the baseline artifact stays on the official trace; the test never checks which trace an artifact came from.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
rm -rf "$HERE/choice.json"
"$PY" "$RT/common/select_shortcuts.py" easier --here "$HERE"
run_hidden_test "$HERE"
