# Continuum: Efficient and Robust Multi-Turn LLM Agent Scheduling with KV Cache Time-to-Live

| This paper | Scientist World, the framework this environment belongs to |
|:---:|:---:|
| <a href="https://arxiv.org/abs/2511.02230"><img alt="This paper on arXiv" src="https://img.shields.io/badge/arXiv-2511.02230-b31b1b?logo=arxiv&logoColor=white"></a> | <a href="https://arxiv.org/abs/2611.08478"><img alt="Scientist World on arXiv" src="https://img.shields.io/badge/arXiv-2611.08478-b31b1b?logo=arxiv&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world"><img alt="Scientist World code" src="https://img.shields.io/badge/Code-Scientist_World-181717?logo=github&logoColor=white"></a> <a href="https://github.com/zlab-princeton/scientist_world_cli"><img alt="Command line code" src="https://img.shields.io/badge/Code-Command_line-181717?logo=github&logoColor=white"></a> |

| | |
|---|---|
| **Paper ID** | [2511.02230](https://arxiv.org/abs/2511.02230) |
| **Domain** | LLM inference systems / agent serving |
| **TL;DR** | Continuum keeps KV cache alive across short tool calls using a cost-model TTL, reducing repeated prefill/reload and queueing delays in multi-turn agents. |

## Summary

The paper studies serving workloads where agent programs repeatedly alternate between LLM calls and tools. Existing serving engines usually evict KV cache at the end of each inference turn, which is inefficient when the next turn arrives soon after a tool call. Continuum estimates whether retaining the cache is worthwhile, assigns a bounded TTL, and prioritizes returning programs while preserving program-level FCFS order.

## Problem

How should an LLM serving system schedule multi-turn agent programs that alternate between model inference and external tool execution, when the next request often reuses the previous request's KV cache after a short but variable delay?

## The paper's method

Continuum adds tool-aware KV-cache time-to-live management to LLM serving. Instead of evicting a finished request's KV cache immediately, it selectively pins the cache for a computed TTL when the request produced a tool call.

## Key results of the paper

- Paper reports 1.12x to 3.66x delay reduction and 1.10x to 3.22x throughput improvement across model/hardware/workload settings.
- Paper reports roughly 2x average response-time reduction in highlighted Llama-3.1-8B experiments.
- Scheduler overhead remains in the single-digit millisecond range and is comparable to baseline vLLM/LMCache scheduler overhead.

## Run it

```bash
pip install sciworld
sw research 2511.02230 --mode innovate --agent claude-code
sw evaluate 2511.02230
```

## More

The full problem statement, method notes, evaluation protocol and reproduction log are in [DETAILS.md](DETAILS.md).

