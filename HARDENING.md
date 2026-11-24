# Hardening (iteration 11): response to REDTEAM.md

**Outcome.** The gym now runs the scheduler itself. Scores follow research quality on the hidden test:
- **Variants and brute force:** weaker variants lose, and the paper's ablation order holds. The 45 s brute force that topped the old gym (+4.17) now ranks −1.23. Every constant-TTL grid choice also ranks below the reference.
- **Shortcuts:** all eleven old shortcuts are closed.
- **Improvements:** paper-faithful refinements of the reference rank above it.

All numbers below come from job `e0d6851c-e68`, reproduced bit-identically by job `36403e22-096` (exit code 0, `validate.py --post-design`: all checks passed). Both ran `redteam/hardening/run_hardening.sh` and then `scripts/reproduce.sh`. Rank tables: `redteam/hardening/rank_table_test.md` (hidden test, 7 experiments × 8 traces × 160 programs) and `rank_table_train.md` (4 traces).

## 1. What changed

| REDTEAM finding | fix |
|---|---|
| The test copied numbers from method-written JSON files. The simulator, timing model and baselines lived in `method/`. | `eval/{train,test}/engine.py` is an evaluator-owned discrete-event serving engine: KV memory, chunked-prefill iterations whose duration grows with prefill work and batch context, an LRU evictable cache, and an offload reload path. Baselines (vLLM, program-FCFS, PLAS/Autellix, InferCept) live in `eval/*/baselines.py`. A method is only a **policy process** (`method/policies/<name>.json` → command). It speaks a JSON-lines protocol (`briefing/evaluation.md`) and answers the retain-for (TTL), admission-order and victim queries. `method/continuum_sim.py`, `baseline/run_baselines.py`, `eval/evaluate_results.py` and `data/workloads*` were removed. |
| Test = train traces with a different metric subset. Every hidden value was recomputable. | Test traces are generated in memory from a key inside `eval/test/` (8 traces per experiment; train has 4 public traces). Every trace re-draws tool medians, spreads, popularity and environment speed, so nothing trace-specific can be memorised. While policies run, `eval/test/` is chmod 000. The oracle shortcut log confirms this: `oracle: cannot read eval/test` (7/7 runs). |
| Retention was free: requests skipped the head of line, and forced unpins happened even while others ran. | Admission follows the policy's order and **stops at the first request that does not fit** (Algorithm 1). A victim is requested only when nothing is running. Recomputed prefill slows every co-running request. So retained memory now blocks others, and that is the cost Continuum's TTL trades off. |
| Tool names were i.i.d. with one shared duration distribution, so tool-awareness carried no signal. | Per-workload catalogues of named tools with distinct long-tailed distributions (Fig. 5 tail shares), plus rare hung calls. Two new experiments: `tool_shift_scaled` (tool latencies change abruptly twice per trace) and `mixed_agents_scaled` (SWE and BFCL agents share the engine). |
| Missing method or metric was skipped. No range checks. A crash kept a forged score file. | Fail closed. The output file is deleted first and written last. A crash, hang, protocol violation, invalid reply (negative or non-finite TTL, non-permutation order, bogus victim) or any unfinished program gives the **worst value of every metric** in that experiment. Every method on disk is scored in every experiment. |
| Headline metrics absent from the test. | Scored in every experiment on both splits: `delay_reduction_x` (mean), `p90/p95_delay_reduction_x`, `throughput_improvement_x`, and `queue_wait_fraction` (cost side, lower is better). The rest (absolute times, hit rate, retained memory, forced releases, expiries) are `_diagnostics`. |
| `completed_fraction` saturated, so starving long programs paid. | Completion is a hard gate (see above). Tails are computed per trace over all programs. |
| η used each program's true turn count (future information). | The policy never receives turn counts, tool durations before return, or future arrivals. The reference estimates η from completed programs only. |

`scoring/reference.json` was rebuilt for the new experiments and metrics by `redteam/hardening/make_reference.py`. Paper values are readings of Figs. 8, 9, 10, 13 and 15b; each experiment has a `source_note`. Numeric values are given for the proposed method, the ratio reference and the ablation arms. For other baselines the figure reading is quoted in the note, with the engine's deviation.

## 2. Do better results score higher? (hidden test)

Rank proxy: the same formula as REDTEAM (`redteam/hardening/rank.py`). It is the weight × |coef| × directed difference from the reference, divided by each metric's spread over 17 honest variants. The paired column is the weighted mean per-trace ratio of reference to method mean completion time (> 1 is better), ± its standard error.

| variant | what it is | rank proxy | paired delay ratio |
|---|---|---|---|
| `better_progress_window` | + ties broken by turns served; last-150 per-tool window, K = 20 | **+0.12** | 1.012 ± 0.004 |
| `better_window` | sliding per-tool history (adapts to shifts) | **+0.09** | 1.008 ± 0.004 |
| `better_progress` | progress tie-break | **+0.06** | 1.008 ± 0.004 |
| `better_all` / `better_progress_shared` | all of the above + miss cost charged to co-runners | **+0.05** | 1.026 / 1.024 ± 0.005 |
| `continuum` (reference), `continuum_rerun` | paper method | 0.00 | 1 (bit-identical rerun) |
| `better_shared_miss` | shared-miss cost alone | −0.16 | 0.998 ± 0.005 |
| `static_ttl` | paper ablation: cold-start TTL only | **−0.29** | 0.975 ± 0.004 |
| `fixed_ttl_{4,8,16,2,1}` | constant TTL | −0.78 … −1.62 | 0.86 – 0.947 |
| `bruteforce_retain45` | retain every KV for 45 s (old winner, +4.17) | **−1.23** | 0.915 ± 0.006 |
| `weaker_nopin_fcfs` | key idea removed (TTL 0, program FCFS kept) | −5.04 | 0.530 |
| `weaker_vllm_as_method` | end-of-turn eviction, request FCFS | −6.16 | 0.413 |
| `weaker_fifo_priority` | TTL kept, priority removed | −9.70 | 0.206 |

- **Ordering.** The ordering is monotone in quality. The paper's ablation order holds on the test: vLLM 0.82× < program-FCFS 1.00× < Static TTL 1.67× < Continuum 1.74×, relative to program-FCFS. The paper reports 0.90 < 1.00 < 1.19 < 1.31.
- **Brute force and fixed TTLs now lose for the paper's reason.** The 45 s brute force has the highest hit rate (0.95–0.99) but 1.5–5× the reference's mean retained memory. Its queue-wait fraction is higher (e.g. 0.68 vs 0.54 on BFCL) and its mean completion time worse in all 7 experiments. A sweep of fixed TTLs from 1 to 45 s never beats the reference's cost-model TTL.
- **Improvements are detectable but small.** Improvements of 1–2.6 % are 2–5 standard errors on the paired test ratio. On the 4-trace train split the same variants are within noise (SE about 0.005–0.01). Scientists should judge gains below about 1 % with care.

## 3. Shortcuts (hidden test)

| shortcut | old gym | now |
|---|---|---|
| forge score / artifact files (`shortcut_forge_files`) | +11.87 | −6.16: scored as what the policy actually does (no retention) |
| impossible values (`shortcut_invalid_values`) | 4.2e8 | −12.51: worst values everywhere |
| crash where it looks bad (`shortcut_crash_on_offload`) | +0.14 (drop experiment) / +357.7 (crash leaves forged score file) | −2.82: worst values in the two offload experiments |
| clairvoyant TTL from the trace generator (`shortcut_read_hidden_oracle`) | +2.61 | 0.00: cannot read `eval/test`, falls back to the reference. On train, where traces are public, exact-duration TTL is **worse** than the cost model (−1.33): pinning long tools blocks others |
| per-family constant-TTL grid fit on train (`shortcut_constant_grid`) | +4.17 | −0.71 |
| shortest-prompt-first, starve big programs (`shortcut_smallest_first`) | +5.39 (starvation) | −9.36: all programs must finish, and tails are per trace |
| inflate baselines, bigger GPU, easier trace, omit constraint keys | +1.64 … +4.39 | not possible: baselines, capacity, traces and metric set belong to the evaluator |

## 4. Reproduction against the paper (`scoring/scores_test.json`, delay reduction vs the experiment's reference baseline)

| experiment | Continuum (test / train) | paper reading | other arms (test) |
|---|---|---|---|
| SWE no offload | 3.04 / 3.07 | 1.66 (Fig. 8) | PLAS 1.00 (paper ≈ 0.54) |
| BFCL no offload | 2.15 / 2.06 | 1.48 (Fig. 8) | PLAS 1.02 (paper ≈ 1.08) |
| SWE + offload | 2.37 / 2.41 (P90 1.85, P95 1.82) | 1.59 (P90 1.56, P95 1.59; Figs. 9, 10) | InferCept 1.92 (paper ≈ 1.09), PLAS 0.98 (≈ 0.96) |
| 3× turns + offload | 4.26 / 4.18 | 2.3 (Fig. 13) | InferCept 3.01 (paper ≈ 1.35) |
| ablation (vs program-FCFS) | 1.74 / 1.78 | 1.31 (Fig. 15b) | Static TTL 1.67 (1.19), vLLM 0.82 (0.90) |
| tool shift (extension) | 2.07 / 2.10 | none (proxy 1.48) | Static TTL 1.93 |
| mixed agents (extension) | 2.07 / 2.03 | none (proxy 1.57) | Static TTL 2.00 |

Throughput improvement is 1.67–3.40× (paper: 1.10–3.22×). The old gym's throughput was about 1.00×, so this claim is now reproduced. `validate.py --post-design` passes; every reproduced primary value is within 2× of the paper reading.

**Known deviations.**
1. **Larger absolute speedups.** The operating points are deeply overloaded, with 37–80 % of completion time spent queueing, as in the paper's highest-load points. They are amplified by the scaled engine.
2. **PLAS does not show the paper's SWE-Bench degradation.** It stays at about 1.0× instead of about 0.54×.
3. **InferCept is stronger than in the paper,** particularly with 3× turns.
4. **Static TTL nearly matches Continuum on SWE + offload and 3× turns** (2.40 vs 2.37, 4.38 vs 4.26 on test). The paper's Fig. 15a shows the same near-tie at high SWE load (≈ 1.40 vs 1.41). Continuum's tool-aware TTL wins clearly where tool behaviour is informative or shifting: BFCL, tool shift, mixed and ablation, +3.3 % to +7.2 %.

## 5. Residual risks

- **The `eval/test/` seal is advisory against a same-UID process.** A policy could `chmod` it back. Real hiding relies on `eval/test/` not being shipped to the scientist. The seal only stops accidental or naive reads.
- **Train traces are public by design.** A policy can identify them, which only helps on train.
- **`queue_wait_fraction` is normalised by completion time.** A method that removes service time (more hits) without removing waiting raises it slightly, e.g. `better_all`. Its coefficient (−0.3) is small next to the delay terms.
- **The rank-proxy spread is dominated by the weak variants.** Near-reference differences therefore look small in proxy units. The paired ratio column is the more sensitive comparison.
