#!/bin/bash
# Score every method on disk on the visible train traces and write
# scoring/scores.json (same content as scoring/scores_train.json).
# Method-independent: methods are discovered from method/policies/*.json and
# run as separate processes; eval/ never imports method/.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/evaluate_train.sh
cp scoring/scores_train.json scoring/scores.json
