#!/bin/bash
# Hidden test.  Runs every method declared in method/policies/*.json and the
# fixed baselines through the evaluator-owned serving engine on hidden traces
# (generated in memory by eval/test/), and writes scoring/scores_test.json.
# Takes no arguments.  A failed method gets the worst value of every metric.
set -euo pipefail
cd "$(dirname "$0")/.."
chmod u+rwx eval/test 2>/dev/null || true   # undo a seal left by a killed run
rm -f scoring/scores_test.json
export PYTHONPATH="$PWD"
python eval/test/evaluate.py "$@"
