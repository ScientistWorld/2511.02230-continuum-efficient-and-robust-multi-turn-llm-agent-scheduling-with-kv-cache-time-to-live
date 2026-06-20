# Problem Definition

## Research Question

How should an LLM serving system schedule multi-turn agent programs that alternate between model inference and external tool execution, when the next request often reuses the previous request's KV cache after a short but variable delay?

## Why It Matters

Agentic workloads issue many related inference requests per user task. If a serving engine evicts useful KV cache at every tool call, each later turn can pay extra prefill/reload and queueing delay, increasing end-to-end job completion time.

## Success Criteria

A successful system should reduce average and tail job completion time for multi-turn tool-using agents, improve or preserve throughput, avoid hangs under memory pressure, and work when tool-call durations are long-tailed rather than perfectly predictable.
