#!/bin/bash
# Run Continuum and its ablated TTL variants on one workload.

set -euo pipefail

cd /home/user

WORKLOAD="${1:-data/workloads/swebench_scaled.json}"
OUTDIR="${2:-outputs/method}"
OFFLOAD="${3:-}"

mkdir -p "$OUTDIR"
for policy in static_ttl continuum; do
  args=(method/continuum_sim.py --workload "$WORKLOAD" --policy "$policy" --output "$OUTDIR/${policy}.json")
  if [ "$OFFLOAD" = "--offload" ]; then
    args+=(--offload)
  fi
  python "${args[@]}"
done
