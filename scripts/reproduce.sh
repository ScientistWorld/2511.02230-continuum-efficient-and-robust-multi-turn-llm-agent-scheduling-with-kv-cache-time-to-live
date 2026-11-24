#!/bin/bash
# End-to-end reproduction: score the paper's method (Continuum) and its
# Static-TTL ablation (method/policies/) against the baselines on the train and
# hidden test traces.  CPU only; no downloads.
set -euo pipefail
cd "$(dirname "$0")/.."
bash scripts/evaluate.sh          # scores_train.json + scores.json
bash scripts/evaluate_test.sh     # scores_test.json
