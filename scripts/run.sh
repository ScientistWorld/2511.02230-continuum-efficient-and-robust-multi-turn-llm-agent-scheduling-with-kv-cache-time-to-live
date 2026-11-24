#!/bin/bash
# TEMPORARY (red-team audit job): runs redteam/run_all.sh; restored from git afterwards.
set -euo pipefail
cd /home/user
export PYTHONPATH=/home/user:${PYTHONPATH:-}
bash redteam/run_all.sh
