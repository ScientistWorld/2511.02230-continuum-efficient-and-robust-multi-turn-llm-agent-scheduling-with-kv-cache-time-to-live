#!/bin/bash
# SHORTCUT: take a policy with mixed results and delete its artifact from the experiments where it looks worse than the reference; the test simply omits the method there (no worst-value fill). Needs the variant_* runs first.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
rm -f "$HERE/choice.json"
"$PY" "$RT/common/select_shortcuts.py" drop --here "$HERE"
run_hidden_test "$HERE"
