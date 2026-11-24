# Evaluation Targets

All targets are computed by the evaluator from its own serving-engine simulation of each method's
policy on its own traces (`scripts/evaluate_train.sh` for visible traces, `scripts/evaluate_test.sh`
for hidden traces). Ratios are taken against the reference baseline of each experiment, which runs on exactly the
same traces. Paper values and their sources are in `scoring/reference.json`.

## Benefit targets

### Primary: swebench_scaled_no_offload
Whole-program completion time on coding-agent (SWE-Bench-like) programs, no host-memory fallback (paper Fig. 8).
- **Metric:** `delay_reduction_x` vs vLLM (higher is better). Paper reading: 1.66x.

### Primary: bfcl_scaled_no_offload
Same claim on web-search / function-calling (BFCL-like) programs (paper Fig. 8).
- **Metric:** `delay_reduction_x` vs vLLM (higher is better). Paper reading: 1.48x.

### Robustness: swebench_scaled_offload
Benefit remains when lost serving state can be reloaded from host memory (paper Figs. 9 and 10).
- **Metrics:** `delay_reduction_x` (paper 1.59x), `p90_delay_reduction_x` (paper 1.56x), `p95_delay_reduction_x` (paper 1.59x) vs vLLM with offload.

### Robustness: turn_robustness_scaled
Same total work split across 3x more tool-interleaved turns, with offload (paper Fig. 13, 3x multiplier).
- **Metric:** `delay_reduction_x` vs vLLM with offload (paper 2.3x).

### Ablation: ablation_scaled
Program-level ordering alone vs. adding fixed retention vs. the full scheduler (paper Fig. 15b).
- **Metric:** `delay_reduction_x` vs program-level FCFS (paper: vLLM 0.90x, Static TTL 1.19x, full method 1.31x).

### Extension: tool_shift_scaled
Tool latencies change abruptly twice within a trace; a scheduler must adapt online. Not a paper figure.
- **Metric:** `delay_reduction_x` vs vLLM (reference value 1.48x is a closest-workload proxy, not a paper measurement).

### Extension: mixed_agents_scaled
Coding and web agents share one engine. Not a paper figure.
- **Metric:** `delay_reduction_x` vs vLLM (reference value 1.57x is a closest-workload proxy, not a paper measurement).

### Tail latency and throughput (every experiment)
- `p95_delay_reduction_x`, `p90_delay_reduction_x`: per-trace tail completion-time ratios (paper Fig. 10).
- `throughput_improvement_x`: drain-time ratio (paper claims 1.10x-3.22x overall).

## Constraint targets

### Constraint: queue_wait_fraction (every experiment, scored, lower is better)
Fraction of program completion time spent waiting for admission. Retaining serving state that blocks other requests
raises it. A method cannot win on completion time by letting retained memory stall everybody else without paying here.

### Constraint: every program completes (hard gate)
A run that leaves any program unfinished, crashes, hangs, breaks the protocol or returns impossible values
(negative/non-finite retention, invalid orders or victims) gets the worst value of every scored metric in that
experiment (0 for ratios, 1 for `queue_wait_fraction`).

### Constraint: fixed resources and no future information (enforced by the evaluator)
GPU KV capacity, recompute/reload costs and the timing model live in the evaluator and are identical for every method
and baseline. The policy only sees the past (tool durations are revealed after the tool returns; turn counts and future
arrivals are never revealed). These are not scored because they cannot be violated.
