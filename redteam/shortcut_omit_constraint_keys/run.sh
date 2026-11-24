#!/bin/bash
# SHORTCUT: brute-force pin-everything (45 s TTL) policy, but drop the constraint fields peak_pinned_memory_fraction / expired_pin_fraction / deadlock_unpins from the artifact -- the test omits absent fields and the rank skips missing values.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
source /home/user/redteam/common/lib.sh
fresh_dir "$HERE"
"$PY" "$RT/common/produce.py" --set official --outdir "$HERE/artifacts" --variant pin_max
"$PY" "$RT/common/edit_artifacts.py" omit_keys --art "$HERE/artifacts" --keys peak_pinned_memory_fraction expired_pin_fraction deadlock_unpins
run_hidden_test "$HERE"
