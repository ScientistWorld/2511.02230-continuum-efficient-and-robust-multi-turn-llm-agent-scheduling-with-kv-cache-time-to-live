# Progress

## What Works

Implemented a scaled reproduction of Continuum as a deterministic discrete-event scheduler. The implementation includes the paper's tool-call history tracking, empirical-CDF TTL optimization, cold-start fallback, TTL pin/unpin behavior, TTL-aware program-level FCFS priority, and victim unpinning under memory pressure.

`scripts/reproduce.sh` generates SWE-Bench-like and BFCL-like traces, runs baselines and Continuum variants, and writes `scoring/scores.json` through the independent evaluator.

## Results

The packaged CPU test job `be56b5fe-bf9` completed successfully in the Apptainer environment and `validate.py --compare` passed. The reproduced scores are:

- SWE-style no offload: Continuum `delay_reduction_x` 1.347 over vLLM.
- BFCL-style no offload: Continuum `delay_reduction_x` 1.212 over vLLM.
- SWE-style CPU offload: Continuum `delay_reduction_x` 1.056 over vLLM and better than InferCept's 1.005.
- More-turn stress: Continuum `delay_reduction_x` 1.141.
- Ablation: Continuum improves over program-level scheduling and simple fixed TTL.

All experiments completed every program (`completed_fraction` 1.0). The scored experiments also report cache-hit behavior, peak pinned memory fraction, and expired pin fraction so future methods cannot improve latency merely by retaining all KV cache indefinitely.

## Remaining

The exact paper traces, vLLM fork integration, and Llama-3.1 hardware measurements are not reproduced. A higher milestone would require using the released Continuum/vLLM code and real traces or collecting equivalent vLLM traces.

## Issues

The workspace initially had only scaffold files. The paper's exact traces are not bundled here, and the public repository is a vLLM fork that is too heavy for a quick CPU-only reproduction. The implemented benchmark uses deterministic synthetic traces parameterized by the paper's published workload statistics.

The first packaged CPU test job failed before running the method because the clean Apptainer environment did not put `/home/user` on Python's module search path. The reproduction scripts now export `PYTHONPATH=/home/user:${PYTHONPATH:-}`, and `data/__init__.py` makes the shared workload module an explicit package.

The retry packaged CPU job succeeded and validated the reusable scripts, method outputs, independent evaluation, and scoring schema.

On 2026-06-20, a continuation audit fixed two implementation fidelity issues: Continuum now uses the paper's `K = 100` cold-start threshold, and the PLAS comparison uses cumulative attained service instead of turn index. A rerun of `bash scripts/reproduce.sh`, `bash scripts/evaluate.sh outputs`, and `python validate.py --compare` passed. With the stricter settings, the current milestone remains `core_claim_plus`.

Updated reproduced scores after this audit:

- SWE-style no offload: Continuum `delay_reduction_x` 1.345 over vLLM.
- BFCL-style no offload: Continuum `delay_reduction_x` 1.175 over vLLM.
- SWE-style CPU offload: Continuum `delay_reduction_x` 1.055 over vLLM and better than InferCept's 1.005.
- More-turn stress: Continuum `delay_reduction_x` 1.155.
- Ablation: Continuum improves over program-level attained-service scheduling and simple fixed TTL.

Validation later flagged the ablation reference because `reference.json` had used `1.0` as a placeholder for Static TTL's primary metric even though the paper text only states that Figure 15 shows gradual improvement and does not report an exact numeric value. The reference now keeps Static TTL as an ablation baseline but omits an invented paper-side primary metric; the reproduced Static TTL score remains in `scores.json`.

## Deviations from Paper

- Paper used real GPT-5-generated SWE-Bench and BFCL traces with vLLM/LMCache serving Llama-3.1 models on A100/B200/H100 GPUs. This reproduction uses a discrete-event simulator and synthetic traces from the paper's Table 1 statistics because the exact traces and hardware are unavailable in this workspace.
- Paper measured real wall-clock serving. This reproduction measures simulated completion time, throughput, and memory-retention behavior under a fixed timing model. The method algorithm is preserved; the serving backend is scaled down.
