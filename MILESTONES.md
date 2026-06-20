# Reproduction Milestones

**Current: core_claim_plus**

## Progress Log

### [2026-06-20 12:53] - none
- Audited the inherited workspace and found only scaffold files, with no method or evaluation implementation.
- Read the paper's scheduling algorithm and evaluation setup.

### [2026-06-20 12:53] - method_runs
- Implemented a deterministic event-driven scheduler with Continuum's TTL utility model, empirical-CDF TTL search, pin/unpin behavior, and TTL-aware program-level FCFS priority.
- Implemented vLLM-style, PLAS-style, InferCept-style, and fixed-TTL comparison policies.

### [2026-06-20 12:53] - core_claim
- Local CPU reproduction showed Continuum improves average completion time on SWE-style and BFCL-style multi-turn workloads while completing all programs.
- Added offload, turn-stress, and ablation experiments to make the benchmark useful for future agents.

### [2026-06-20 13:08] - core_claim
- First packaged CPU job failed before method execution due to missing workspace import path in the clean Apptainer environment.
- Added explicit package initialization and `PYTHONPATH=/home/user` exports to the runnable scripts, then verified `scripts/run.sh` in a clean local shell.

### [2026-06-20 13:20] - core_claim_plus
- Packaged CPU test job `be56b5fe-bf9` completed successfully and `validate.py --compare` passed in the container.
- Reproduced the core latency-reduction claim on SWE-style traces and extended it to BFCL-style, CPU-offload, more-turn robustness, and ablation settings.
- All scored experiments completed every program and include cache-retention constraints.

## Stop Justification
- Completed at milestone `core_claim_plus`.
