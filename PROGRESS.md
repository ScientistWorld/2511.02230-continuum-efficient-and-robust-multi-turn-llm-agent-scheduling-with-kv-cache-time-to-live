# Progress

## What Works (iteration 11, after hardening)

- **Paper's method as a policy.** `method/continuum_policy.py` implements Continuum (arXiv 2511.02230) as a scheduling policy:
  - per-tool and global tool-duration history from the tool-call handler;
  - TTL from the paper's cost model (Eq. 2): the empirical CDF over recorded durations, benefit = Prefill-Reload + T·η, and τ* = argmax P(τ)·Benefit − τ;
  - cold start τ = ln(Benefit) while |S| ≤ K = 100;
  - priority to programs holding a live pin, then program-level FCFS;
  - latest-arrival victim on deadlock.

  `method/policies/continuum.json` is the paper method. `static_ttl.json` is the paper's Static TTL ablation.
- **Evaluator owns the measurement.** The evaluator (`eval/train`, `eval/test`) owns a discrete-event serving engine and runs the policy over a JSON-lines protocol. The engine models KV memory, chunked-prefill iterations, an LRU evictable cache, CPU-offload reload, and head-of-line admission as in Algorithm 1. The evaluator also owns the traces (Table 1 statistics, named tools with distinct long-tailed durations) and the baselines (vLLM, program-FCFS, PLAS/Autellix, InferCept).
- **Hidden test, fail-closed scoring.** The hidden test traces are generated in memory from a key, and a failed run gets the worst value of every metric. See `HARDENING.md`.
- **One command runs everything.** `bash scripts/reproduce.sh` writes `scoring/scores_train.json`, `scores.json` and `scores_test.json`. It takes about 6 minutes on one CPU, including the hardening suite. `python validate.py --post-design` passes.

## Results (hidden test; train in parentheses; ratio vs vLLM unless noted)

| experiment | delay reduction | P95 | throughput | paper |
|---|---|---|---|---|
| SWE no offload | 3.04 (3.07) | 2.35 | 2.15 | 1.66 (Fig. 8) |
| BFCL no offload | 2.15 (2.06) | 2.07 | 1.97 | 1.48 (Fig. 8) |
| SWE + CPU offload | 2.37 (2.41); InferCept 1.92 | 1.82 | 1.67 | 1.59; InferCept ≈ 1.09 (Fig. 9) |
| 3× turns + offload | 4.26 (4.18); InferCept 3.01 | 3.85 | 3.40 | 2.3; InferCept ≈ 1.35 (Fig. 13) |
| ablation (vs program-FCFS) | Continuum 1.74 > Static TTL 1.67 > 1.00 > vLLM 0.82 | | | 1.31 > 1.19 > 1.00 > 0.90 (Fig. 15b) |
| tool shift (extension) | 2.07 (2.10); Static TTL 1.93 | 1.90 | 1.79 | no paper value |
| mixed agents (extension) | 2.07 (2.03); Static TTL 2.00 | 2.27 | 2.14 | no paper value |

These results reproduce the paper's claims:
- Continuum cuts mean, P90 and P95 completion time.
- It improves throughput (1.67–3.40×; paper 1.10–3.22×).
- It beats InferCept with offload.
- Its gain grows with turn count.
- The ablation order matches.

Absolute speedups are larger than the paper's figure readings but within 2× of them. The operating points are deeply overloaded, with 37–80 % of completion time spent queueing.

## Remaining

- **No real-system reproduction.** The exact paper traces, the vLLM/LMCache fork and the Llama-3.1 GPU measurements are not reproduced. This is a scaled engine.
- **Baseline deviations.**
  - PLAS does not show the paper's SWE-Bench degradation (≈ 1.0× vs ≈ 0.54×).
  - InferCept is stronger than in the paper.
  - Static TTL nearly ties Continuum on SWE + offload and 3× turns. Fig. 15a shows a similar near-tie at high SWE load.
- **Claims not measured.** Scheduler overhead (Table 3) and SSD offload (Fig. 14).

## History

- **2026-06-20 (iterations 1–10).** The first scaled reproduction was a discrete-event simulator inside `method/`, which wrote per-policy artifacts that `eval/` copied into scores. It reached `secondary_claims`: Continuum beat vLLM 1.35× on SWE and 1.18× on BFCL, with P95 claims added later.
- **Iteration 10 (red team, `REDTEAM.md`).** The audit found the gym did not reward better research:
  - the test only copied method-written numbers, and traces were visible;
  - retention was free, so a 45 s brute force won by about 8× the seed spread;
  - every shortcut tried beat the reference.
- **Iteration 11 (hardening, `HARDENING.md`).** The simulator, traces and baselines moved into `eval/`, and the method became a policy process. The engine was rebuilt with head-of-line admission and a shared-iteration timing model, so retention now has a cost. Tool catalogues became tool-specific and tool-shift and mixed-agent experiments were added. Test traces are hidden and generated in memory, scoring fails closed, and the headline and throughput metrics are scored in both splits. `scoring/reference.json` was rebuilt from figure readings (`redteam/hardening/make_reference.py`).
  - Verification job `e0d6851c-e68`: weaker variants, the brute force, constant-TTL grids and all shortcuts score at or below the reference, while paper-faithful refinements score above it.
  - That job exited 1 only because `reference.json` had not yet been updated for the new schema and `rank.py` assumed every method ran in every experiment. Both are fixed, and `validate.py --post-design` now passes on the job's outputs.
  - Confirmation job `36403e22-096` reran the full `scripts/run.sh` (hardening suite, reference reproduction, validator) with exit code 0. All checks passed and the scores were bit-identical to the previous job.

## Deviations from Paper

- **Hardware and traces.** The paper used real GPT-5-generated SWE-Bench and BFCL traces on vLLM/LMCache with Llama-3.1 (8B and 70B) on A100, B200 and H100 GPUs. This gym uses a scaled discrete-event serving engine and synthetic traces from the paper's Table 1 statistics and Fig. 5 tool-time shapes.
- **Simulated time.** Completion time and throughput are simulated, not wall-clock.
- **Algorithm preserved.** The paper's algorithm is kept: tool-call handler, cost-model TTL, cold start, priority, and deadlock victim. η and T are estimated online from observed history only.
