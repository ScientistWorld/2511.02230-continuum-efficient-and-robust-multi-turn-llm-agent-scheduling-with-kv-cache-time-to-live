# Experiment Overview

Every experiment runs the submitted scheduling policy and fixed baselines inside the same evaluator-owned serving
engine on the same multi-turn agent traces, at an overloaded operating point where requests queue for GPU memory.
Each reports completion-time ratios (mean, P90, P95), a throughput ratio, and the fraction of time spent waiting for
admission.

## swebench_scaled_no_offload

The central claim: on coding-agent programs with many short model/tool alternations, a better serving policy finishes
whole programs sooner than end-of-turn eviction, without extra memory.

## bfcl_scaled_no_offload

The same claim on web-search / function-calling programs, which have fewer turns, larger contexts and different tool
latencies. Checks that the result is not specific to one agent type.

## swebench_scaled_offload

Lost serving state can be reloaded from host memory instead of rebuilt. Checks that the benefit survives when misses
are cheaper, i.e. that it comes from more than avoided recomputation, and compares against an offload-aware baseline.

## turn_robustness_scaled

The same total work split into three times as many turns. Checks that the benefit holds, and grows, as agent
workflows get longer-horizon.

## ablation_scaled

Compares progressively richer variants against program-level ordering alone. Establishes how much of the benefit comes
from the claimed improvements rather than from ordering alone.

## tool_shift_scaled

Tool latencies change abruptly part-way through each trace (benchmark extension). Checks that a policy adapts to
changing tool behaviour online instead of relying on stale estimates.

## mixed_agents_scaled

Coding and web agents with different tools share one engine (benchmark extension). Checks that a policy copes with
heterogeneous tools and programs at the same time.
