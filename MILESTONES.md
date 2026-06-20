# Reproduction Milestones

**Current: core_claim**

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

## Stop Justification

Not stopped. Submitting a CPU job to validate the packaged reproduction in the compute environment.
