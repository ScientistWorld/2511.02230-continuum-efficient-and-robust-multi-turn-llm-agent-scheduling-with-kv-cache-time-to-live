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

## What is measured

Every scheduler is run by the evaluator inside an evaluator-owned serving engine
on multi-turn agent traces, next to fixed baselines on exactly the same traces.
The engine models one LLM replica (a 70B-class model on a 4-GPU node with about
one million tokens of KV-cache memory) serving agent programs that alternate
LLM requests with tool calls.  A request holds prompt+output tokens of KV memory
while it runs; the GPU advances in iterations (chunked prefill, 2048-token
budget) whose duration grows with the prefill work, the number of decoding
requests and their context lengths; so a recomputed prefix slows down every
request running at the same time.  When a request ends in a tool call its KV
can be retained for a while or released.  Released KV stays in an evictable LRU
cache until another admission needs the space.  With CPU offload, a program
whose KV is no longer on the GPU reloads it from host memory (cheaper than a
recompute, but still on the GPU's critical path) instead of recomputing it.

All scored numbers are recomputed by the evaluator from its own simulation; it
never reads numbers, files or verdicts written by a method.

Scored metrics (per experiment, pooled over the experiment's traces; the
reference baseline is named in each experiment):

| metric | meaning | better |
|---|---|---|
| `delay_reduction_x` | baseline mean program completion time / method mean | higher |
| `p95_delay_reduction_x` | per-trace baseline P95 / method P95 completion time (geometric mean over traces) | higher |
| `p90_delay_reduction_x` | same at P90 | higher |
| `throughput_improvement_x` | baseline drain time of the trace / method drain time (completed programs per second ratio) | higher |
| `queue_wait_fraction` | total time requests spent waiting for admission / total program completion time | lower |

A run fails if the policy crashes, hangs, answers with an invalid message or an
impossible value (negative / non-finite retention, an order that is not a
permutation of the waiting queue, a victim that holds no retained KV), or if any
program is left unfinished.  A failed run gets the worst value of every scored
metric in that experiment (0 for the ratios, 1 for `queue_wait_fraction`).
Diagnostics (absolute completion times, reuse hit rate, retained-memory
fraction, forced releases, ...) are written to `_diagnostics` but are not scored.

## Experiments

| experiment | workload | offload | baselines (ratio vs) |
|---|---|---|---|
| `swebench_scaled_no_offload` | coding-agent programs (SWE-Bench-like) | no | vLLM (ratio), PLAS |
| `bfcl_scaled_no_offload` | web-search / function-calling programs (BFCL-like) | no | vLLM (ratio), PLAS |
| `swebench_scaled_offload` | coding-agent programs | CPU | vLLM+offload (ratio), PLAS, InferCept |
| `turn_robustness_scaled` | coding-agent programs with 3x the turns, 1/3 the tokens per turn | CPU | vLLM+offload (ratio), InferCept |
| `ablation_scaled` | BFCL-like programs | no | program-level FCFS (ratio), vLLM |
| `tool_shift_scaled` | web-search / function-calling programs (BFCL-like) whose tool latencies change abruptly twice mid-trace | no | vLLM (ratio), program-level FCFS |
| `mixed_agents_scaled` | coding and web agents sharing one engine | no | vLLM (ratio), program-level FCFS |

Programs arrive as a Poisson wave (the operating points are overloaded, as in
the paper's high-load settings).  Program shapes follow the paper's Table 1
(turns, tokens per program); tool calls come from named tools with long-tailed
durations whose parameters (medians, spreads, popularity, overall environment
speed) are re-drawn for every trace, plus rare hung calls.  Train traces
(`scripts/evaluate_train.sh`) and the hidden test traces are drawn from the same
distribution with different seeds; the test uses more traces per experiment.

## How a method plugs in

A method is a policy program declared by a manifest
`method/policies/<name>.json`:

```json
{"command": ["python", "method/my_policy.py", "--some-flag"]}
```

The evaluator starts the command once per trace with the workspace root as the
working directory and talks to it over stdin/stdout, one JSON object per line.
Messages with `"q": true` need exactly one JSON reply line; all others are
notifications.  Anything the policy prints to stdout that is not a reply is a
protocol error (use stderr for logs).  Every method on disk is scored in every
experiment; method names must not collide with the baseline names.

Engine -> policy messages (`t` is simulated time in seconds; `req` and
`program` are integers):

* `{"type":"init","capacity_tokens":..,"offload":bool,"profile":{..},"q":true}`
  -> reply `{}` (anything).
* `{"type":"arrive","t","req","program","turn","program_arrival","prompt_tokens"}`;
  for `turn > 0` also `"tool"` (the tool the previous turn called) and
  `"tool_time_s"` (finish of the previous turn to this arrival).
* `{"type":"start","t","req","program","turn","hit","wait_s"}` when a request is
  admitted (`hit`: its previous KV was still on the GPU).
* `{"type":"finish","t","req","program","turn","tool","kv_tokens","service_s",
  "rebuild_s","running_tokens","retained_tokens","q":true}` when a request that
  ends in a tool call finishes -> reply `{"retain_s": seconds >= 0}`.
  `rebuild_s` is the stand-alone time to rebuild this KV if it is lost
  (recompute, or reload with offload).  When the program's last request
  finishes, the same message arrives with `"tool": null` and without `"q"`.
* `{"type":"schedule","t","waiting":[req..],"retained":[program..],
  "free_tokens","running","q":true}` -> reply `{"order":[req..]}` (a
  permutation of `waiting`) and optionally `"release":[program..]` to drop
  retained KV early.  The engine admits in that order and stops at the first
  request that does not fit (no skipping ahead).
* `{"type":"victim","t","retained":[program..],"head":req,"q":true}` when
  nothing is running, the head of the order does not fit and KV is retained ->
  reply `{"victim": program}`; that program's retained KV is released.
* `{"type":"end"}` at the end of the trace (then stdin closes).

Retained KV is released automatically when its time is up, unless the
program's next request is already waiting.  The evaluator never reveals a tool
call's duration before it returns, a program's number of turns, or anything
about future arrivals.

Limits: each policy process gets a CPU-time limit far above what a reasonable
policy needs (minutes per trace) and a long idle backstop against hangs; no
metric depends on wall-clock time.

## Commands

* `bash scripts/evaluate_train.sh` -> `scoring/scores_train.json` (visible traces).
* `bash scripts/evaluate_test.sh` -> `scoring/scores_test.json` (hidden traces; no arguments).
* Policy stderr logs go to `outputs/policy_logs_<split>/`.

The paper reports 1.12x to 3.66x delay reduction and 1.10x to 3.22x throughput
improvement over vLLM-style serving on real hardware; the simulated engine is a
scaled model of that setting, so absolute values differ (see
`scoring/reference.json`).

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

### Iteration 8: gpt-5.5 (verifier)
- **Milestone**: `core_claim_plus` | **Status**: done
- **Working time**: 5m | **GPU**: 0.0h
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

### [2026-06-20 14:00] - core_claim_plus
- Final verification confirmed the claimed milestone remains justified.
- Fixed `scripts/evaluate.sh`'s evaluator path to score all method artifacts in each experiment rather than a fixed policy list.
- Regenerated `scoring/scores.json` with the missing queue-wait and deadlock-unpin constraint metrics and reran validation successfully.

</details>

### Iteration 9: gpt-5.5 (verifier)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 11m | **GPU**: 0.0h
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

### [2026-06-20 14:00] - core_claim_plus
- Final verification confirmed the claimed milestone remains justified.
- Fixed `scripts/evaluate.sh`'s evaluator path to score all method artifacts in each experiment rather than a fixed policy list.
- Regenerated `scoring/scores.json` with the missing queue-wait and deadlock-unpin constraint metrics and reran validation successfully.

### [2026-06-20 13:43] - secondary_claims
- Added P95 completion-time and P95 delay-reduction scoring to cover the paper's tail-latency claim alongside the existing offload, turn-robustness, and ablation experiments.
- Regenerated `scoring/scores.json`, `scoring/scores_train.json`, and `scoring/scores_test.json` from method artifacts.
- Reran `python validate.py --compare` and Python bytecode checks successfully.

### [2026-06-20 13:47] - secondary_claims
- Final verification confirmed the scaled gym remains at `secondary_claims`.
- Tightened method-agnostic documentation for from-scratch agents and removed tracked generated root artifacts from the repository index.
- Reran `bash -n scripts/*.sh`, `bash scripts/evaluate.sh outputs`, and `python validate.py --compare` successfully.

</details>

### Iteration 10: claude-opus-5-5 (redteam)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 14m | **GPU**: 0.0h
- **Jobs**: 5 total (4 completed, 1 failed)

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

### [2026-06-20 14:00] - core_claim_plus
- Final verification confirmed the claimed milestone remains justified.
- Fixed `scripts/evaluate.sh`'s evaluator path to score all method artifacts in each experiment rather than a fixed policy list.
- Regenerated `scoring/scores.json` with the missing queue-wait and deadlock-unpin constraint metrics and reran validation successfully.

### [2026-06-20 13:43] - secondary_claims
- Added P95 completion-time and P95 delay-reduction scoring to cover the paper's tail-latency claim alongside the existing offload, turn-robustness, and ablation experiments.
- Regenerated `scoring/scores.json`, `scoring/scores_train.json`, and `scoring/scores_test.json` from method artifacts.
- Reran `python validate.py --compare` and Python bytecode checks successfully.

### [2026-06-20 13:47] - secondary_claims
- Final verification confirmed the scaled gym remains at `secondary_claims`.
- Tightened method-agnostic documentation for from-scratch agents and removed tracked generated root artifacts from the repository index.
- Reran `bash -n scripts/*.sh`, `bash scripts/evaluate.sh outputs`, and `python validate.py --compare` successfully.

</details>

### Iteration 11: claude-opus-5-5 (hardener)
- **Milestone**: `secondary_claims` | **Status**: done
- **Working time**: 1.2h | **GPU**: 0.0h
- **Jobs**: 7 total (5 completed, 2 failed)

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

### [2026-06-20 14:00] - core_claim_plus
- Final verification confirmed the claimed milestone remains justified.
- Fixed `scripts/evaluate.sh`'s evaluator path to score all method artifacts in each experiment rather than a fixed policy list.
- Regenerated `scoring/scores.json` with the missing queue-wait and deadlock-unpin constraint metrics and reran validation successfully.

### [2026-06-20 13:43] - secondary_claims
- Added P95 completion-time and P95 delay-reduction scoring to cover the paper's tail-latency claim alongside the existing offload, turn-robustness, and ablation experiments.
- Regenerated `scoring/scores.json`, `scoring/scores_train.json`, and `scoring/scores_test.json` from method artifacts.
- Reran `python validate.py --compare` and Python bytecode checks successfully.

### [2026-06-20 13:47] - secondary_claims
- Final verification confirmed the scaled gym remains at `secondary_claims`.
- Tightened method-agnostic documentation for from-scratch agents and removed tracked generated root artifacts from the repository index.
- Reran `bash -n scripts/*.sh`, `bash scripts/evaluate.sh outputs`, and `python validate.py --compare` successfully.

### [2026-11-24] - secondary_claims
- **Hardening (iteration 11), answering `REDTEAM.md`.** The evaluator now owns a discrete-event serving engine, the traces and the baselines, and runs each method as a policy process. The hidden test generates its traces in memory, and scoring fails closed. Retention now costs something: head-of-line admission, and prefill shared by co-running requests.
- **Verification (job `e0d6851c-e68`, `HARDENING.md`).** Weaker variants, the 45 s brute force (−1.23, old +4.17), constant-TTL grids and all eleven old shortcuts score at or below the reference. Paper-faithful refinements score above it.
- **Paper's claims on the hidden test.** Continuum beats vLLM by 2.15–4.26× (mean) with matching P90/P95 gains and 1.67–3.40× throughput (paper: 1.10–3.22×). It also beats InferCept with offload, grows with turn count, and the paper's ablation order holds. `validate.py --post-design` passes with the rebuilt `scoring/reference.json`.
- Confirmation job `36403e22-096`: the full `scripts/run.sh` exits 0 and all validator checks pass.

</details>


---

# Reproduction Milestones

**Current: secondary_claims**
