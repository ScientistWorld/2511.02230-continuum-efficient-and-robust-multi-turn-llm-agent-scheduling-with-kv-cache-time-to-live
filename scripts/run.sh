#!/bin/bash
# Job script for train/test evaluation scoring.

set -euo pipefail

cd /home/user
export PYTHONPATH=/home/user:${PYTHONPATH:-}

bash scripts/evaluate_train.sh outputs scoring/scores_train.json
bash scripts/evaluate_test.sh outputs scoring/scores_test.json
