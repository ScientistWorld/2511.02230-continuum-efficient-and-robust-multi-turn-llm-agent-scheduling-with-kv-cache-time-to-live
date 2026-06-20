#!/bin/bash
# Score the held-out test slice from pre-generated scheduler artifacts.

set -euo pipefail

cd /home/user

ARTIFACTS="${1:-outputs}"
OUTPUT="${2:-scoring/scores_test.json}"

python eval/test/evaluate.py \
  --artifacts "$ARTIFACTS" \
  --output "$OUTPUT"
