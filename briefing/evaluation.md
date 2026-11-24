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
