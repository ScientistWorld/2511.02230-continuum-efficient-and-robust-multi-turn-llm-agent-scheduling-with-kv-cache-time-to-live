#!/bin/bash
# Runs every red-team variant / shortcut (each through the gym's hidden test),
# the workload-seed reruns, and the summaries.  Resumable: finished runs are
# skipped via a .done marker.
set -uo pipefail
cd /home/user
RT=/home/user/redteam
export PYTHONPATH=/home/user
PY=$(command -v python3 || command -v python)

RUNS=(
  variant_ref_rerun
  variant_weaker_nopin_fcfs
  variant_weaker_vllm_as_method
  variant_weaker_static_ttl
  variant_coldstart_only
  variant_warm_history
  variant_true_deadlock_unpin
  variant_bruteforce_pin_max
  shortcut_oracle_ttl
  shortcut_forge_artifacts
  shortcut_impossible_values
  shortcut_inflate_baseline
  shortcut_omit_constraint_keys
  shortcut_crash_keeps_forged_scores
  shortcut_starve_long_programs
  shortcut_bigger_gpu
  shortcut_easier_workload
  shortcut_static_grid_overfit
  shortcut_drop_bad_experiment
)

for d in "${RUNS[@]}"; do
  if [ -f "$RT/$d/.done" ] && [ -f "$RT/$d/scores_test.json" ]; then
    echo "skip $d (done)"; continue
  fi
  start=$(date +%s)
  if bash "$RT/$d/run.sh" > "$RT/$d/run.log" 2>&1; then
    touch "$RT/$d/.done"
    echo "ok   $d ($(( $(date +%s) - start ))s)"
  else
    echo "FAIL $d"; tail -20 "$RT/$d/run.log"
  fi
done

"$PY" "$RT/common/check_recompute.py" | tee "$RT/check_recompute.txt"
"$PY" "$RT/common/rank.py" > "$RT/rank_table.md"
cat "$RT/rank_table.md"

"$PY" "$RT/common/seeds.py" run
"$PY" "$RT/common/seeds.py" summary | tee "$RT/seed_runs/seed_table.md"
"$PY" "$RT/common/rank.py" > "$RT/rank_table.md"

if diff -rq outputs "$RT/ref_outputs" > /dev/null; then echo "gym outputs/ restored OK"; else echo "WARNING: outputs/ differs from reference snapshot"; fi
md5sum scoring/scores_test.json "$RT/ref_scores_test.json"
