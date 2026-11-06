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

---

# Problem Definition

## Research Question

How should an LLM serving system schedule multi-turn agent programs that alternate between model inference and external tool execution, when the next request often reuses the previous request's KV cache after a short but variable delay?

## Why It Matters

Agentic workloads issue many related inference requests per user task. If a serving engine evicts useful KV cache at every tool call, each later turn can pay extra prefill/reload and queueing delay, increasing end-to-end job completion time.

## Success Criteria

A successful system should reduce average and tail job completion time for multi-turn tool-using agents, improve or preserve throughput, avoid hangs under memory pressure, and work when tool-call durations are long-tailed rather than perfectly predictable.

---

# Paper's Method

## Key Contribution

Continuum adds tool-aware KV-cache time-to-live management to LLM serving. Instead of evicting a finished request's KV cache immediately, it selectively pins the cache for a computed TTL when the request produced a tool call.

## Approach

The scheduler records per-tool inter-request durations from previous turns. For a finished request, it estimates the benefit of retaining the KV cache as the avoided prefill/reload cost plus an out-of-order queueing-delay term based on workload memoryfulness. It estimates the cost as the time that pinned GPU memory blocks other work.

Continuum chooses the TTL by enumerating historical tool durations and maximizing the paper's expected net benefit objective: empirical probability that the tool returns within TTL times benefit, minus TTL cost. It falls back to global tool-call history or a fixed cold-start TTL when per-tool history is sparse.

The scheduler then prioritizes preempted requests, requests whose program has a live TTL pin, and finally program-level FCFS order. Expired pins are released, and if pins would deadlock scheduling, the latest-arriving pinned program is unpinned as a victim.

## Main Claims

The primary claim is that tool-aware TTL KV-cache retention reduces multi-turn agent job completion time compared with end-of-turn eviction. Secondary claims are that the method works with CPU/SSD offload, improves tail latency and throughput, scales better as turn counts increase, and introduces only small scheduler overhead.

---

# Evaluation

## Metrics

The benchmark measures end-to-end program completion time, P90 completion time, job throughput, cache-hit rate, peak pinned-memory fraction, expired-pin fraction, and completed-program fraction. Lower completion time and memory pressure are better; higher throughput, cache-hit rate, and completed fraction are better.

The reported comparison metric is `delay_reduction_x`, computed as the baseline average completion time divided by the method average completion time for the same workload. Values above 1 mean the method is faster than the baseline.

## Baselines and Targets

The main baseline is vanilla vLLM-style end-of-turn eviction. Additional baselines include program-level attained-service scheduling and an InferCept-style local preserve policy under CPU offload. The paper reports delay reductions from 1.12x to 3.66x and throughput improvements from 1.10x to 3.22x across evaluated setups, with a text-highlighted result of roughly 2x average response-time reduction for Llama-3.1-8B settings.

## Evaluation Protocol

Run `scripts/reproduce.sh` to generate deterministic SWE-Bench-like and BFCL-like multi-turn traces from the paper's published workload statistics, execute each scheduler on identical traces, and then run `scripts/evaluate.sh`. Evaluation reads JSON artifacts from `outputs/` and writes `scoring/scores.json`; it does not import or execute the method implementation.

---

# Reproduction Log

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 0m | **GPU**: 0.0h

<details>
<summary>Progress Log</summary>

<!-- Write your progress here -->

</details>

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 0m | **GPU**: 0.0h

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 0m | **GPU**: 0.0h

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 30m | **GPU**: 0.0h

### Iteration 1: gpt-5.5
- **Milestone**: `none` | **Status**: error
- **Working time**: 30m | **GPU**: 0.0h

### Iteration 1: gpt-5.5
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 36m | **GPU**: 0.0h
- **Jobs**: 2 total (1 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-20 12:53] - none
- Audited the inherited workspace and found only scaffold files, with no method or evaluation implementation.
- Read the paper's scheduling algorithm and evaluation setup.

### [2026-06-20 12:53] - method_runs
- Implemented a deterministic event-driven scheduler with Continuum's TTL utility model, empirical-CDF TTL search, pin/unpin behavior, and TTL-aware program-level FCFS priority.
- Implemented vLLM-style, PLAS-style, InferCept-style, and fixed-TTL comparison policies.

### [2026-06-20 12:53] - core_claim
- Local CPU reproduction showed Continuum improves average completion time on SWE-style and BFCL-style multi-turn workloads while completing all programs.
- Added offload, turn-stress, and ablation experiments to make the benchmark useful for future agents.

### [2026-06-20 13:08] - core_claim
- First packaged CPU job failed before method execution due to missing workspace import path in the clean Apptainer environment.
- Added explicit package initialization and `PYTHONPATH=/home/user` exports to the runnable scripts, then verified `scripts/run.sh` in a clean local shell.

### [2026-06-20 13:20] - core_claim_plus
- Packaged CPU test job `be56b5fe-bf9` completed successfully and `validate.py --compare` passed in the container.
- Reproduced the core latency-reduction claim on SWE-style traces and extended it to BFCL-style, CPU-offload, more-turn robustness, and ablation settings.
- All scored experiments completed every program and include cache-retention constraints.

</details>

### Iteration 2: gpt-5.5
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h
- **Jobs**: 2 total (1 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-20 13:02] - core_claim_plus
- Validated the packaged Continuum reproduction with `python validate.py --compare`.
- Reproduced the core delay-reduction claim on a scaled SWE-Bench-style workload and additional BFCL-style, CPU-offload, higher-turn, and ablation settings.
- Confirmed evaluation is reusable and method-independent: `eval/` and `data/` do not import from `method/`, and `scripts/evaluate.sh` scores JSON artifacts produced by scheduler runs.

### [2026-06-20 13:04] - core_claim_plus
- Audited the existing method, evaluation, scripts, scoring files, and environment packaging after the continuation reset.
- Fixed audit issues by setting Continuum's cold-start threshold to the paper's `K = 100`, changing the PLAS baseline to use cumulative attained service, and clarifying that the simulator implements the simplified Equation 2 form.
- Reran `bash scripts/reproduce.sh`, `bash scripts/evaluate.sh outputs`, and `python validate.py --compare`; the regenerated scores still support the scaled core claim and additional settings.
- Restored the milestone to `core_claim_plus` after the stricter rerun.

</details>

### Iteration 3: gpt-5.5
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 9m | **GPU**: 0.0h
- **Jobs**: 2 total (1 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-20 12:58] - core_claim
- Implemented a scaled discrete-event reproduction of Continuum's KV-cache TTL scheduler.
- Submitted a CPU packaged job that ran `scripts/reproduce.sh` and `python validate.py --compare` successfully.
- Demonstrated the core completion-time reduction claim on a SWE-Bench-style multi-turn workload.

### [2026-06-20 13:09] - core_claim_plus
- Covered additional BFCL-style, CPU-offload, higher-turn, and ablation settings.
- Evaluation reports benefit metrics plus constraints including completion fraction, cache-hit rate, peak pinned memory, and expired-pin behavior.
- The exact vLLM/Llama hardware experiments and unreleased paper traces remain out of scope for this scaled reproduction.

### [2026-06-20 13:34] - core_claim_plus
- Continued-agent audit verified the implementation is a real scaled Continuum scheduler rather than an input-output surrogate.
- Reran standalone evaluation, validator comparison, and Python bytecode checks successfully.
- Tightened scoring documentation for TTL-expiry and source qualification of prose-derived reference targets.

</details>

### Iteration 4: gpt-5.5 (designer_stage_1)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h
- **Jobs**: 2 total (1 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-20 12:58] - core_claim
- Implemented a scaled discrete-event reproduction of Continuum's KV-cache TTL scheduler.
- Submitted a CPU packaged job that ran `scripts/reproduce.sh` and `python validate.py --compare` successfully.
- Demonstrated the core completion-time reduction claim on a SWE-Bench-style multi-turn workload.

### [2026-06-20 13:09] - core_claim_plus
- Covered additional BFCL-style, CPU-offload, higher-turn, and ablation settings.
- Evaluation reports benefit metrics plus constraints including completion fraction, cache-hit rate, peak pinned memory, and expired-pin behavior.
- The exact vLLM/Llama hardware experiments and unreleased paper traces remain out of scope for this scaled reproduction.

### [2026-06-20 13:34] - core_claim_plus
- Continued-agent audit verified the implementation is a real scaled Continuum scheduler rather than an input-output surrogate.
- Reran standalone evaluation, validator comparison, and Python bytecode checks successfully.
- Tightened scoring documentation for TTL-expiry and source qualification of prose-derived reference targets.

</details>

### Iteration 5: gpt-5.5 (designer_stage_2)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 3m | **GPU**: 0.0h
- **Jobs**: 2 total (1 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-20 12:58] - core_claim
- Implemented a scaled discrete-event reproduction of Continuum's KV-cache TTL scheduler.
- Submitted a CPU packaged job that ran `scripts/reproduce.sh` and `python validate.py --compare` successfully.
- Demonstrated the core completion-time reduction claim on a SWE-Bench-style multi-turn workload.

### [2026-06-20 13:09] - core_claim_plus
- Covered additional BFCL-style, CPU-offload, higher-turn, and ablation settings.
- Evaluation reports benefit metrics plus constraints including completion fraction, cache-hit rate, peak pinned memory, and expired-pin behavior.
- The exact vLLM/Llama hardware experiments and unreleased paper traces remain out of scope for this scaled reproduction.

### [2026-06-20 13:34] - core_claim_plus
- Continued-agent audit verified the implementation is a real scaled Continuum scheduler rather than an input-output surrogate.
- Reran standalone evaluation, validator comparison, and Python bytecode checks successfully.
- Tightened scoring documentation for TTL-expiry and source qualification of prose-derived reference targets.

</details>

### Iteration 6: gpt-5.5 (designer_stage_3)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 3m | **GPU**: 0.0h
- **Jobs**: 3 total (2 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-20 12:58] - core_claim
- Implemented a scaled discrete-event reproduction of Continuum's KV-cache TTL scheduler.
- Submitted a CPU packaged job that ran `scripts/reproduce.sh` and `python validate.py --compare` successfully.
- Demonstrated the core completion-time reduction claim on a SWE-Bench-style multi-turn workload.

### [2026-06-20 13:09] - core_claim_plus
- Covered additional BFCL-style, CPU-offload, higher-turn, and ablation settings.
- Evaluation reports benefit metrics plus constraints including completion fraction, cache-hit rate, peak pinned memory, and expired-pin behavior.
- The exact vLLM/Llama hardware experiments and unreleased paper traces remain out of scope for this scaled reproduction.

### [2026-06-20 13:34] - core_claim_plus
- Continued-agent audit verified the implementation is a real scaled Continuum scheduler rather than an input-output surrogate.
- Reran standalone evaluation, validator comparison, and Python bytecode checks successfully.
- Tightened scoring documentation for TTL-expiry and source qualification of prose-derived reference targets.

</details>

### Iteration 7: gpt-5.5 (packager)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 2m | **GPU**: 0.0h
- **Jobs**: 3 total (2 completed, 1 failed)

<details>
<summary>Progress Log</summary>

### [2026-06-20 12:58] - core_claim
- Implemented a scaled discrete-event reproduction of Continuum's KV-cache TTL scheduler.
- Submitted a CPU packaged job that ran `scripts/reproduce.sh` and `python validate.py --compare` successfully.
- Demonstrated the core completion-time reduction claim on a SWE-Bench-style multi-turn workload.

### [2026-06-20 13:09] - core_claim_plus
- Covered additional BFCL-style, CPU-offload, higher-turn, and ablation settings.
- Evaluation reports benefit metrics plus constraints including completion fraction, cache-hit rate, peak pinned memory, and expired-pin behavior.
- The exact vLLM/Llama hardware experiments and unreleased paper traces remain out of scope for this scaled reproduction.

### [2026-06-20 13:34] - core_claim_plus
- Continued-agent audit verified the implementation is a real scaled Continuum scheduler rather than an input-output surrogate.
- Reran standalone evaluation, validator comparison, and Python bytecode checks successfully.
- Tightened scoring documentation for TTL-expiry and source qualification of prose-derived reference targets.

</details>


---

# Reproduction Milestones

**Current: core_claim_plus**
