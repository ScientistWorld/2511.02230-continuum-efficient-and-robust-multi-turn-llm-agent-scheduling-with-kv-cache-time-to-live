# Progress

## What Works

Implemented a scaled reproduction of Continuum as a deterministic discrete-event scheduler. The implementation includes the paper's tool-call history tracking, empirical-CDF TTL optimization, cold-start fallback, TTL pin/unpin behavior, TTL-aware program-level FCFS priority, and victim unpinning under memory pressure.

`scripts/reproduce.sh` generates SWE-Bench-like and BFCL-like traces, runs baselines and Continuum variants, and writes `scoring/scores.json` through the independent evaluator.

## Results

Local CPU run before submission produced:

- SWE-style no offload: Continuum `delay_reduction_x` 1.347 over vLLM.
- BFCL-style no offload: Continuum `delay_reduction_x` 1.212 over vLLM.
- SWE-style CPU offload: Continuum `delay_reduction_x` 1.056 over vLLM and better than InferCept's 1.005.
- More-turn stress: Continuum `delay_reduction_x` 1.141.
- Ablation: Continuum improves over program-level scheduling and simple fixed TTL.

All experiments completed every program (`completed_fraction` 1.0).

## Remaining

The exact paper traces, vLLM fork integration, and Llama-3.1 hardware measurements are not reproduced. A higher milestone would require using the released Continuum/vLLM code and real traces or collecting equivalent vLLM traces.

## Issues

The workspace initially had only scaffold files. The paper's exact traces are not bundled here, and the public repository is a vLLM fork that is too heavy for a quick CPU-only reproduction. The implemented benchmark uses deterministic synthetic traces parameterized by the paper's published workload statistics.

The first packaged CPU test job failed before running the method because the clean Apptainer environment did not put `/home/user` on Python's module search path. The reproduction scripts now export `PYTHONPATH=/home/user:${PYTHONPATH:-}`, and `data/__init__.py` makes the shared workload module an explicit package.

## Deviations from Paper

- Paper used real GPT-5-generated SWE-Bench and BFCL traces with vLLM/LMCache serving Llama-3.1 models on A100/B200/H100 GPUs. This reproduction uses a discrete-event simulator and synthetic traces from the paper's Table 1 statistics because the exact traces and hardware are unavailable in this workspace.
- Paper measured real wall-clock serving. This reproduction measures simulated completion time, throughput, and memory-retention behavior under a fixed timing model. The method algorithm is preserved; the serving backend is scaled down.
