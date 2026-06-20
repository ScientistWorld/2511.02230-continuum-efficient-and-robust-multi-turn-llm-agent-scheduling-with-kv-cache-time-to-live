# Experiment Overview

## swebench_scaled_no_offload

Tests the central completion-time claim on a coding-agent-style workload with many short inference/tool alternations and no cache offload. The purpose is to check whether useful cache continuity improves whole-program latency.

## bfcl_scaled_no_offload

Tests the same central claim on a function-calling and web-search-style workload with different turn counts and tool-time distribution. This checks that the result is not specific to coding-agent traces.

## swebench_scaled_offload

Tests whether the scheduling benefit remains when missed cache can be reloaded from host memory instead of recomputed from scratch. This isolates the queueing and ordering side of the problem.

## turn_robustness_scaled

Tests a higher-turn setting where more frequent tool gaps make per-turn scheduling overhead accumulate. This checks whether a scheduler remains useful as agent workflows become longer horizon.

## ablation_scaled

Compares progressively richer scheduler variants on the same workload. The goal is to establish whether the full system's benefit is attributable to the claimed scheduling improvements rather than generic program-level ordering alone.
