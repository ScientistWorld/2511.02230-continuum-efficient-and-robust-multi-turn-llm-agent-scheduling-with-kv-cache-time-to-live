#!/bin/bash
# Score the visible train slice from pre-generated scheduler artifacts.

set -euo pipefail

cd /home/user

ARTIFACTS="${1:-outputs}"
OUTPUT="${2:-scoring/scores_train.json}"

python eval/train/evaluate.py --artifacts "$ARTIFACTS" --output "$OUTPUT"
