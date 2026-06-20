# Paper's Method

## Key Contribution

Continuum adds tool-aware KV-cache time-to-live management to LLM serving. Instead of evicting a finished request's KV cache immediately, it selectively pins the cache for a computed TTL when the request produced a tool call.

## Approach

The scheduler records per-tool inter-request durations from previous turns. For a finished request, it estimates the benefit of retaining the KV cache as the avoided prefill/reload cost plus an out-of-order queueing-delay term based on workload memoryfulness. It estimates the cost as the time that pinned GPU memory blocks other work.

Continuum chooses the TTL by enumerating historical tool durations and maximizing the paper's expected net benefit objective: empirical probability that the tool returns within TTL times benefit, minus TTL cost. It falls back to global tool-call history or a fixed cold-start TTL when per-tool history is sparse.

The scheduler then prioritizes preempted requests, requests whose program has a live TTL pin, and finally program-level FCFS order. Expired pins are released, and if pins would deadlock scheduling, the latest-arriving pinned program is unpinned as a victim.

## Main Claims

The primary claim is that tool-aware TTL KV-cache retention reduces multi-turn agent job completion time compared with end-of-turn eviction. Secondary claims are that the method works with CPU/SSD offload, improves tail latency and throughput, scales better as turn counts increase, and introduces only small scheduler overhead.
