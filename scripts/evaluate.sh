#!/bin/bash
# Evaluate scheduler run artifacts and write scoring/scores.json.
#
# This script is method-independent: it reads JSON artifacts in outputs/ and
# calls only eval/ code. It does not import or execute method/.

set -euo pipefail

cd /home/user

ARTIFACTS="${1:-outputs}"
python eval/evaluate_results.py --artifacts "$ARTIFACTS" --output scoring/scores.json
