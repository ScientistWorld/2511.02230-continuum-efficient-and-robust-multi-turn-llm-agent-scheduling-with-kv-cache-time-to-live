# Research Direction

## Research Problem

This benchmark is about scheduling and reusable serving-state residency for multi-turn LLM agents whose requests are separated by external tool calls. The research question is how to reduce full-program latency while keeping memory retention bounded and robust to variable tool durations.

## Core Contribution Scope

Improvements must stay within tool-aware state-retention and request-scheduling policies for LLM serving. A valid improvement may change retention-duration estimation, priority ordering, cold-start handling, eviction selection, or how queueing benefit is estimated.

## Out of Bounds

- Replacing the problem with model-quality improvements, prompt changes, or faster tool implementations.
- Changing the evaluator's workload generator, timing model, memory capacity or baselines.
- Using information a real serving system would not have (future tool durations, turn counts, future arrivals, the trace generator or its seeds).
- Writing score or artifact files instead of letting the evaluator run the policy.
