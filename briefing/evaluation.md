# Evaluation

## Metrics

The benchmark measures end-to-end program completion time, P90 completion time, job throughput, cache-hit rate, peak pinned-memory fraction, expired-pin fraction, and completed-program fraction. Lower completion time and memory pressure are better; higher throughput, cache-hit rate, and completed fraction are better.

The reported comparison metric is `delay_reduction_x`, computed as the baseline average completion time divided by the method average completion time for the same workload. Values above 1 mean the method is faster than the baseline.

## Baselines and Targets

The main baseline is vanilla vLLM-style end-of-turn eviction. Additional baselines include program-level attained-service scheduling and an InferCept-style local preserve policy under CPU offload. The paper reports delay reductions from 1.12x to 3.66x and throughput improvements from 1.10x to 3.22x across evaluated setups, with a text-highlighted result of roughly 2x average response-time reduction for Llama-3.1-8B settings.

## Evaluation Protocol

Run `scripts/reproduce.sh` to generate deterministic SWE-Bench-like and BFCL-like multi-turn traces from the paper's published workload statistics, execute each scheduler on identical traces, and then run `scripts/evaluate.sh`. Evaluation reads JSON artifacts from `outputs/` and writes `scoring/scores.json`; it does not import or execute the method implementation.
