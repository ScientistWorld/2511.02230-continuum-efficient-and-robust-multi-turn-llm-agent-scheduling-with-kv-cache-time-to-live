#!/bin/bash
# Run baseline schedulers from the paper on a generated workload.

set -euo pipefail

cd /home/user
export PYTHONPATH=/home/user:${PYTHONPATH:-}

WORKLOAD="${1:-data/workloads/swebench_scaled.json}"
OUTDIR="${2:-outputs/baselines}"
OFFLOAD="${3:-}"

args=(--workload "$WORKLOAD" --output-dir "$OUTDIR")
if [ "$OFFLOAD" = "--offload" ]; then
  args+=(--offload)
fi

python baseline/run_baselines.py "${args[@]}"
