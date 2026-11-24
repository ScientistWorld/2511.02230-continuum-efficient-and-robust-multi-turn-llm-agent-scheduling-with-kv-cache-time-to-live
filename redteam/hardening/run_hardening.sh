#!/bin/bash
# Verification for HARDENING.md: run every variant / shortcut in
# redteam/hardening/policies/ through the train and the hidden-test evaluators,
# derive the constant-grid shortcut from train, and build rank tables.
set -uo pipefail
cd /home/user
export PYTHONPATH=/home/user
H=redteam/hardening
chmod u+rwx eval/test 2>/dev/null || true
# shortcut_forge_files writes fake scoring/scores_*.json and outputs/<experiment>/;
# keep the real score files aside and restore them (and drop the forgeries) at the end.
BK=$(mktemp -d)
cp -p scoring/scores.json scoring/scores_train.json scoring/scores_test.json "$BK"/ 2>/dev/null || true
python eval/train/evaluate.py --policies-dir $H/policies --output $H/scores_train_all.json --log-dir outputs/hardening_logs_train
python $H/grid.py $H/scores_train_all.json $H/grid_choice.json
python -c "import json; json.dump({'command': ['python', 'redteam/hardening/shortcuts/constant_grid.py']}, open('$H/policies/shortcut_constant_grid.json', 'w'))"
python eval/test/evaluate.py --policies-dir $H/policies --output $H/scores_test_all.json --log-dir outputs/hardening_logs_test
POOL=continuum,static_ttl,weaker_vllm_as_method,weaker_nopin_fcfs,weaker_fifo_priority,fixed_ttl_1,fixed_ttl_2,fixed_ttl_4,fixed_ttl_8,fixed_ttl_16,bruteforce_retain45,better_progress,better_window,better_progress_window,better_shared_miss,better_progress_shared,better_all
python $H/rank.py $H/scores_test_all.json --pool $POOL --out $H/rank_table_test.md
python $H/rank.py $H/scores_train_all.json --pool $POOL --out $H/rank_table_train.md
grep -h "oracle:" outputs/hardening_logs_test/shortcut_read_hidden_oracle__*__0.log | sort | uniq -c > $H/oracle_test_log.txt || true
rm -f scoring/scores.json scoring/scores_train.json scoring/scores_test.json
cp -p "$BK"/*.json scoring/ 2>/dev/null || true
rm -rf "$BK"
for e in swebench_scaled_no_offload bfcl_scaled_no_offload swebench_scaled_offload turn_robustness_scaled ablation_scaled tool_shift_scaled mixed_agents_scaled; do
  rm -rf "outputs/$e"
done
echo "hardening verification done"
