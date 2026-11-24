#!/bin/bash
# Score only the fixed baselines (vLLM, program-level FCFS, PLAS, InferCept) on
# the train traces.  The baselines live in eval/ (eval/train/baselines.py) so
# every method is compared against the same reference points.
set -euo pipefail
cd "$(dirname "$0")/.."
empty="$(mktemp -d)"
export PYTHONPATH="$PWD"
python eval/train/evaluate.py --policies-dir "$empty" --output outputs/baselines_train.json
rmdir "$empty"
echo "wrote outputs/baselines_train.json"
