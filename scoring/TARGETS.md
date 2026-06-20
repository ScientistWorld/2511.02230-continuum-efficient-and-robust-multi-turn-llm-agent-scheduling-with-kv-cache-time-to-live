# Evaluation Targets

## Primary: swebench_scaled_no_offload

Tests whether a scheduler reduces end-to-end completion time on a coding-agent-style multi-turn workload without host-memory fallback.
- **Metric:** `delay_reduction_x` (higher is better)

## Primary: bfcl_scaled_no_offload

Tests whether the same effect appears on a web-search/function-calling-style multi-turn workload.
- **Metric:** `delay_reduction_x` (higher is better)

## Constraint: completed_fraction

All scheduler variants should finish every program under bounded state retention and memory pressure.
- **Metric:** `completed_fraction` (higher is better)

## Constraint: peak_pinned_memory_fraction

Retained serving state should not win merely by occupying all available memory indefinitely.
- **Metric:** `peak_pinned_memory_fraction` (lower is better)

## Constraint: expired_pin_fraction

Bounded retention should release stale serving state when tool calls run longer than expected.
- **Metric:** `expired_pin_fraction` (lower is generally better, but nonzero values demonstrate active stale-state expiry)

## Tail Latency: p95_delay_reduction_x

The paper reports P90 and P95 latency improvements on SWE-Bench traces; the benchmark should reward methods that reduce high-percentile completion time, not only the mean.
- **Metric:** `p95_delay_reduction_x` (higher is better)

## Robustness: swebench_scaled_offload

Tests whether completion-time reduction remains when missed reusable state can be reloaded from host memory rather than fully recomputed.
- **Metric:** `delay_reduction_x` (higher is better)

## Robustness: turn_robustness_scaled

Tests whether the scheduler remains beneficial when the same total work is split across more tool-interleaved turns.
- **Metric:** `delay_reduction_x` (higher is better)

## Ablation: ablation_scaled

Tests whether the full scheduler improves over simpler program-level and fixed-retention variants.
- **Metric:** `delay_reduction_x` (higher is better)
