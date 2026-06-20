#!/bin/bash
# Job script for the scaled Continuum reproduction.

set -euo pipefail

cd /home/user
export PYTHONPATH=/home/user:${PYTHONPATH:-}

bash scripts/reproduce.sh
python validate.py --compare
