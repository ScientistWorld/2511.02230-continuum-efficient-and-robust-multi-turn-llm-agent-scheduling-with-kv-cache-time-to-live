# Overview

- **Paper ID:** 2511.02230
- **Title:** Continuum: Efficient and Robust Multi-Turn LLM Agent Scheduling with KV Cache Time-to-Live
- **Domain:** LLM inference systems / agent serving
- **TL;DR:** Continuum keeps KV cache alive across short tool calls using a cost-model TTL, reducing repeated prefill/reload and queueing delays in multi-turn agents.

## Short Summary

The paper studies serving workloads where agent programs repeatedly alternate between LLM calls and tools. Existing serving engines usually evict KV cache at the end of each inference turn, which is inefficient when the next turn arrives soon after a tool call. Continuum estimates whether retaining the cache is worthwhile, assigns a bounded TTL, and prioritizes returning programs while preserving program-level FCFS order.

## Key Results

- Paper reports 1.12x to 3.66x delay reduction and 1.10x to 3.22x throughput improvement across model/hardware/workload settings.
- Paper reports roughly 2x average response-time reduction in highlighted Llama-3.1-8B experiments.
- Scheduler overhead remains in the single-digit millisecond range and is comparable to baseline vLLM/LMCache scheduler overhead.
