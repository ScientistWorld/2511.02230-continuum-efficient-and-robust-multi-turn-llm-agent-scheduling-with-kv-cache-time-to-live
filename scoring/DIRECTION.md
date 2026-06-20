# Research Direction

## Research Problem

This benchmark is about scheduling and KV-cache residency for multi-turn LLM agents whose requests are separated by external tool calls. The research question is how to reduce full-program latency while keeping memory retention bounded and robust to variable tool durations.

## Core Contribution Scope

Improvements must stay within tool-aware cache-retention and request-scheduling policies for LLM serving. A valid improvement may change TTL estimation, priority ordering, cold-start handling, pin-victim selection, or how queueing benefit is estimated.

## Out of Bounds

- Replacing the problem with model-quality improvements, prompt changes, or faster tool implementations.
- Changing the workload generator or timing model only for the proposed method.
- Winning by increasing simulated GPU memory, reducing miss cost, or disabling memory pressure.
- Moving evaluation logic into the method implementation.
