#!/bin/bash
# Visible train split.  Runs every method declared in method/policies/*.json and
# the fixed baselines through the evaluator-owned serving engine on the public
# train traces (eval/train/), and writes scoring/scores_train.json.
set -euo pipefail
cd "$(dirname "$0")/.."
rm -f scoring/scores_train.json
export PYTHONPATH="$PWD"
python eval/train/evaluate.py "$@"
