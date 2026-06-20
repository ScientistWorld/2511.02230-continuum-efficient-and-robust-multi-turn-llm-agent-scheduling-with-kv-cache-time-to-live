# Evaluation Targets

## Primary: swebench_scaled_no_offload

Tests whether a scheduler reduces end-to-end completion time on a coding-agent-style multi-turn workload without cache offload.
- **Metric:** `delay_reduction_x` (higher is better)

## Primary: bfcl_scaled_no_offload

Tests whether the same effect appears on a web-search/function-calling-style multi-turn workload.
- **Metric:** `delay_reduction_x` (higher is better)

## Constraint: completed_fraction

All scheduler variants should finish every program under bounded cache retention and memory pressure.
- **Metric:** `completed_fraction` (higher is better)

## Constraint: peak_pinned_memory_fraction

Cache retention should not win merely by pinning all memory indefinitely.
- **Metric:** `peak_pinned_memory_fraction` (lower is better)

## Robustness: swebench_scaled_offload

Tests whether completion-time reduction remains when cache misses use CPU-style reload rather than full prefill.
- **Metric:** `delay_reduction_x` (higher is better)

## Robustness: turn_robustness_scaled

Tests whether the scheduler remains beneficial when the same total work is split across more tool-interleaved turns.
- **Metric:** `delay_reduction_x` (higher is better)

## Ablation: ablation_scaled

Tests whether the full scheduler improves over simpler program-level and fixed-TTL variants.
- **Metric:** `delay_reduction_x` (higher is better)
