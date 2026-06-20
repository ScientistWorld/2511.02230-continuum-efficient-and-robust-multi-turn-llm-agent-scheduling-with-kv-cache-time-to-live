#!/bin/bash
# Score the held-out test slice for every method seen by the train scorer.

set -euo pipefail

cd /home/user

ARTIFACTS="${1:-outputs}"
OUTPUT="${2:-scoring/scores_test.json}"
TRAIN_SCORES="${3:-scoring/scores_train.json}"

python eval/test/evaluate.py \
  --artifacts "$ARTIFACTS" \
  --output "$OUTPUT" \
  --train-scores "$TRAIN_SCORES"
