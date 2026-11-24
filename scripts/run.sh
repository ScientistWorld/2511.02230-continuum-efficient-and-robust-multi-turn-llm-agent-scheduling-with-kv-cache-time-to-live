#!/bin/bash
# Job script.  1) hardening verification (variants and shortcuts through both
# evaluators, rank tables); 2) the reference reproduction from the final code
# (scores_train.json, scores.json, scores_test.json from method/policies only);
# 3) validation.  The reference runs come last so nothing a shortcut wrote can
# survive in scoring/.
set -uo pipefail
cd /home/user
export PYTHONPATH=/home/user
bash redteam/hardening/run_hardening.sh
bash scripts/reproduce.sh
python validate.py --post-design
