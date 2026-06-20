#!/bin/bash
# End-to-end scaled reproduction of Continuum's core scheduling claim.

set -euo pipefail

cd /home/user

rm -rf outputs
mkdir -p data/workloads outputs

python data/workloads.py --dataset swebench --programs 120 --arrival-rate 0.13 --seed 7 \
  --output data/workloads/swebench_scaled.json
python data/workloads.py --dataset bfcl --programs 120 --arrival-rate 0.13 --seed 11 \
  --output data/workloads/bfcl_scaled.json
python data/workloads.py --dataset swebench --programs 120 --arrival-rate 0.25 --seed 13 \
  --turn-multiplier 3 --output data/workloads/swebench_turn3_scaled.json

mkdir -p outputs/swebench_scaled_no_offload outputs/bfcl_scaled_no_offload \
  outputs/swebench_scaled_offload outputs/turn_robustness_scaled outputs/ablation_scaled

python method/continuum_sim.py --workload data/workloads/swebench_scaled.json --policy vllm \
  --output outputs/swebench_scaled_no_offload/vllm.json
python method/continuum_sim.py --workload data/workloads/swebench_scaled.json --policy continuum \
  --output outputs/swebench_scaled_no_offload/continuum.json

python method/continuum_sim.py --workload data/workloads/bfcl_scaled.json --policy vllm \
  --output outputs/bfcl_scaled_no_offload/vllm.json
python method/continuum_sim.py --workload data/workloads/bfcl_scaled.json --policy continuum \
  --output outputs/bfcl_scaled_no_offload/continuum.json

python method/continuum_sim.py --workload data/workloads/swebench_scaled.json --policy vllm --offload --capacity 3 \
  --output outputs/swebench_scaled_offload/vllm.json
python method/continuum_sim.py --workload data/workloads/swebench_scaled.json --policy infercept --offload --capacity 3 \
  --output outputs/swebench_scaled_offload/infercept.json
python method/continuum_sim.py --workload data/workloads/swebench_scaled.json --policy continuum --offload --capacity 3 \
  --output outputs/swebench_scaled_offload/continuum.json

python method/continuum_sim.py --workload data/workloads/swebench_turn3_scaled.json --policy vllm --offload --capacity 3 \
  --output outputs/turn_robustness_scaled/vllm.json
python method/continuum_sim.py --workload data/workloads/swebench_turn3_scaled.json --policy continuum --offload --capacity 3 \
  --output outputs/turn_robustness_scaled/continuum.json

python method/continuum_sim.py --workload data/workloads/swebench_scaled.json --policy plas \
  --output outputs/ablation_scaled/plas.json
python method/continuum_sim.py --workload data/workloads/swebench_scaled.json --policy static_ttl \
  --output outputs/ablation_scaled/static_ttl.json
python method/continuum_sim.py --workload data/workloads/swebench_scaled.json --policy continuum \
  --output outputs/ablation_scaled/continuum.json

bash scripts/evaluate.sh outputs
