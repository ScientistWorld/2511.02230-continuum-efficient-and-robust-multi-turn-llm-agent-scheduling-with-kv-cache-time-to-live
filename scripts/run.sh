#!/bin/bash
# Job script for the scaled Continuum reproduction and train/test scoring.

set -euo pipefail

cd /home/user
export PYTHONPATH=/home/user:${PYTHONPATH:-}

bash scripts/reproduce.sh
python validate.py --compare
bash scripts/evaluate_train.sh outputs scoring/scores_train.json
bash scripts/evaluate_test.sh outputs scoring/scores_test.json
