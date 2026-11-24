# Red-team audit: does this gym reward better research?

**Short answer: no, not reliably.** Removing the paper's key idea does lower the score, consistently across seeds. But the brute force the paper argues against (retain every cache for the maximum tool time) beats the reference by about 8× the seed spread. Every shortcut tried scores above the reference.

The root cause is structural. `scripts/evaluate_test.sh` runs nothing. It copies numbers out of the JSON files that the agent's own method writes to `outputs/<experiment>/<method>.json`, on the same traces the agent sees. It then divides two of them by the baseline file, which the agent also writes. The simulator itself (memory model, timing model, metric computation) lives in `method/`, which the agent controls. In from-scratch mode `method/` starts empty, and `baseline/run_baselines.py:21` calls `method/continuum_sim.py`, so the agent must even write the environment physics itself.

All runs live under `redteam/<name>/`. Each has one `run.sh`, which puts the variant or shortcut in place as `outputs/` (plus, for one shortcut, a score file left on disk). It then runs `bash scripts/evaluate_test.sh` with no arguments and keeps the resulting `scores_test.json`, `test_rc.txt` and `test_stdout.log` in that folder. `redteam/run_all.sh` ran everything in two CPU jobs.

**How the rank is estimated (column "rank proxy" below).** It uses the gym's formula: the sum over experiments of the experiment weight, times |coefficient| (from `scoring/reference.json`), times the improvement over the reference's `continuum` entry in the better direction. Each metric's improvement is divided by that metric's spread (population std) across the 8 honest variants run on the official traces. That spread stands in for "how much it varies across the attempts later ranked", which I cannot know. Metrics missing on either side, or with zero spread, are skipped, as the rank does. The code is in `redteam/common/rank.py` and the full table in `redteam/rank_table.md`.

## 1. Do better results score higher?

**Weaker variants, all scored through the hidden test:**

| variant | what changes | rank proxy (official trace) | paired vs reference on 3 new trace seeds (mean ± std) | train mean delay reduction, SWE no-offload (ref 1.345×) |
|---|---|---|---|---|
| `variant_weaker_vllm_as_method` | no method: the method entry is end-of-turn eviction | **−2.52** | −1.75 ± 0.21 | 1.000× |
| `variant_weaker_nopin_fcfs` | key idea removed: TTL = 0, program-FCFS kept | **−1.79** | −1.11 ± 0.19 | 1.000× |
| `variant_weaker_static_ttl` | paper ablation: fixed 0.25 s TTL | **−0.81** | −0.74 ± 0.19 | 1.314× |
| `variant_coldstart_only` | never leaves the ln(benefit) cold-start TTL | −0.70 | −0.10 ± 0.30 (noise) | 1.289× |

Weaker variants move the right way, by more than the seed spread. A method that fails the task (vLLM as the method) cannot outrank the reference through the constraint metrics. It sits at their bound (0 pinned memory, 0 expiries, 0 forced unpins) and still scores −2.52.

**Candidate "better" variants:**

| variant | what changes | rank proxy | paired on 3 seeds | train delay SWE / BFCL |
|---|---|---|---|---|
| `variant_warm_history` | per-tool history pre-filled from a different-seed trace (paper Sec. 4.2's remedy for cold start) | −0.53 | −0.02 ± 0.24 (noise) | 1.347 / 1.194 |
| `variant_true_deadlock_unpin` | force-unpin only if nothing is running | −0.62 | −0.65 ± 0.20 | 1.346 / 1.255 |
| `shortcut_oracle_ttl` | TTL = the true upcoming tool time, read from the trace file (future information) | **+2.61** | +2.70 ± 0.26 | 1.676 / 1.605 |
| `variant_bruteforce_pin_max` | brute force: pin every tool call for 45 s (the generator's maximum tool time) | **+4.17** | +4.28 ± 0.36 | **1.881 / 1.983** |

Neither paper-faithful improvement scored higher. The only things that score higher than the reference are the clairvoyant TTL and the brute force. The brute force ranks well above a scheduler that knows every tool duration exactly.

**The brute force solves the test.** A static-TTL grid (0.05 s to 45 s, `shortcut_static_grid_overfit/choice.json`) improves monotonically with TTL in all five experiments, and picks 45 s everywhere. The win is not an overfit to the visible trace: it holds on all three new seeds (+3.90, +4.61, +4.34).

The cause is a simulator property, not just the gym's light load. `redteam/check_load_tradeoff/sweep_table.md` raises the SWE arrival rate from 0.13 to 0.6 programs/s, where queue waits reach about 7 s:

| arrival rate (programs/s) | ref mean / P95 completion time (s) | pin_max | static 4 s |
|---|---|---|---|
| 0.13 | 22.6 / 39.7 | 16.2 / 32.1 | 16.7 / 32.5 |
| 0.3 | 30.5 / 66.5 | 22.9 / 63.2 | 22.8 / 56.5 |
| 0.45 | 72.6 / 141.1 | 50.8 / 114.7 | 40.3 / 92.5 |
| 0.6 | 105.5 / 190.0 | 90.3 / 176.3 | 90.4 / 176.3 |

Longer retention wins at every load. The reason is in the scheduling loop. `method/continuum_sim.py:234-241` schedules *any* queued request that fits, rather than stopping at the head as Algorithm 1 line 20 does. It also force-unpins a victim whenever nothing fits, even while other requests are running. Retained memory therefore never blocks anyone for long. The cost term that Continuum's TTL trades off (pinned memory blocking other requests, paper Fig. 6 and Eq. 1) is never paid. The only remaining counterweight is the `peak_pinned_memory_fraction` coefficient (−0.3), which is far too weak.

**Verdict.** Scores do not follow scientific quality on the improvement side. On this gym "keep everything longer" is the best research direction, and it is the opposite of the paper's point.

## 2. Can the reference be beaten? Metrics already at their bound

These metrics already sit at (or effectively at) their bound:

- **`completed_fraction`** is 1.0 for the reference and every honest attempt in all five experiments. It has zero spread, so it is effectively unscored (see the starvation shortcut below).
- **`avg_queue_wait_s`** is 0.00075 s for the reference on `swebench_scaled_no_offload` and `ablation_scaled`, essentially at its bound of 0.
- **Throughput** is ≈ 1.00× for every policy, because makespan is set by the arrival process. The paper reports 1.10–3.22×. It is absent from the test anyway.
- **The constraint metrics are minimised by doing nothing.** The do-nothing baseline (vLLM) already sits at the bound of 0 for `peak_pinned_memory_fraction`, `expired_pin_fraction` and `deadlock_unpins`.

There is headroom elsewhere. The brute force reaches the bound on hit rate (1.0), expiry (0), forced unpins (0) and queue wait (0) in the no-offload experiments. The simple baselines sit clearly below the reference (vLLM −2.52, no-TTL −1.79).

**The test never sees the headline metrics.** It writes only `p90/p95_completion_time_s`, `avg_queue_wait_s`, `cache_hit_rate`, `peak_pinned_memory_fraction`, `expired_pin_fraction`, `deadlock_unpins`, `completed_fraction`, `p90_delay_reduction_x` and `p95_delay_reduction_x`. Four metrics never appear, in any experiment: `avg_completion_time_s`, `delay_reduction_x`, `throughput_jobs_per_s` and `throughput_improvement_x`. Those carry coefficients 1.0, 1.0, 0.5 and 0.5, the largest in `reference.json`, so the rank always skips them. That is 20 skipped metric values per run.

## 3. Rank plumbing checks

| check | result |
|---|---|
| Failed run gets its worst value? | **No.** A missing method artifact in an experiment simply produces no entry. A missing metric field is skipped (`if metric in artifact`). A crash (exit code 1) writes nothing, and whatever `scoring/scores_test.json` is on disk stays there. |
| Every method on disk written to `results`? | Yes. Every `*.json` in `outputs/<exp>/` becomes a method entry, including the baselines, which the agent also writes. |
| Hidden values hidden? | **No.** `redteam/common/check_recompute.py` recomputes all 120 hidden-test values bit-for-bit from the visible artifacts plus the metric list in `briefing/evaluation.md`. The "test" is the train traces with a different metric subset. |
| Coefficient signs | `reference.json` gives each metric a `higher_is_better` flag consistent with its coefficient sign; magnitudes are what the proxy uses. |

## 4. Seed spread and reproduction check

The simulator is deterministic. Re-running the reference on the official traces is bit-identical (`variant_ref_rerun`: proxy 0.00, every metric equal). The meaningful "seed" is therefore the trace-generator seed.

I reran the reference on three new seed sets (B, C, D, with the same generator settings as `scripts/reproduce.sh`). Results are in `redteam/seed_runs/seed_summary.json`. The reference's own proxy versus the official trace is +0.01, −0.57 and +0.47, a **std of 0.52 rank units**. Per-metric std of the reference across the three seeds:

| experiment | `p90_delay_reduction_x` | `p95_delay_reduction_x` | `cache_hit_rate` | `peak_pinned_memory_fraction` | `deadlock_unpins` |
|---|---|---|---|---|---|
| `swebench_scaled_no_offload` | 0.049 | 0.025 | 0.024 | 0.039 | 1.2 |
| `bfcl_scaled_no_offload` | 0.066 | 0.127 | 0.006 | 0.050 | 17 |
| `swebench_scaled_offload` | 0.006 | 0.012 | 0.014 | 0.026 | 14 |
| `turn_robustness_scaled` | 0.065 | 0.099 | 0.007 | 0.177 | 271 |

The official SWE trace is a lucky draw: its p90 ratio of 1.448 is above all three new seeds (1.30, 1.22, 1.31). Paired variant-minus-reference differences on the same seed vary much less (std 0.19–0.36).

Any gain under about 0.5 rank units on the official trace alone is noise. `warm_history` and `coldstart_only` are noise; the weaker variants and the brute force are not.

**Does the reproduced method beat its baseline in the paper's direction?** Yes for mean delay. The reference scores 1.345× (SWE), 1.175× (BFCL), 1.055× (SWE offload), 1.155× (more turns), and 1.345× against PLAS in the ablation. The ablation order PLAS < static TTL (1.314×) < Continuum also holds.

Two results fall short of the paper. SWE offload at 1.055× is below the paper's 1.12× lower bound. Throughput is about 1.00× everywhere, against 1.10–3.22× in the paper, so the throughput claim is not reproduced.

**Departures from the paper's method and settings:**

1. **Simulator, not vLLM.** A discrete-event simulator stands in for vLLM on GPUs. There is no batching or compute contention: running requests never slow each other, and memory capacity (8 units, or 3 with offload) is the only shared resource.
2. **Synthetic traces.** Traces come from the means and SDs in the paper's Table 1, with 120 programs, Poisson arrivals at 0.13 programs/s, and log-normal tool times capped at 45 s. **Tool names are drawn i.i.d. and every tool shares one duration distribution**, so the per-tool history (the "tool-aware" part) carries no information beyond the global history.
3. **Scheduling loop.** Requests that fit may bypass a head-of-line request that doesn't, and a victim is force-unpinned whenever nothing fits, even while others run. Algorithm 1 instead breaks when the top-priority request doesn't fit. Together with item 1, this makes retention nearly free (Section 1).
4. **Expired pins.** A pin kept because its next request is already queued counts as a miss if that request starts after the pin expired. The paper keeps and reuses it.
5. **Memoryfulness uses future information.** η uses each running program's true total turn count N, which is known only once the program ends.
6. **Further gaps:**
   - Offload is modelled only as a lower miss cost (reload instead of prefill) plus capacity 3.
   - There is no preemption priority level.
   - Scheduler overhead (a paper claim) is not measured.
   - Throughput is completed programs divided by makespan, which arrivals dominate.

**Does the scaled synthetic data still show the effect the paper studies? Only partly.** It shows the reuse benefit: avoided prefill and reload. It does not show the retention cost the TTL exists to balance (Section 1, load sweep). Its i.i.d. tool names also remove the tool-awareness signal. **A better method on this gym is therefore not a better method on the paper's problem.**

## 5. Shortcuts

All were scored exactly as above (hidden test, no arguments). The reference's rank proxy is 0 by definition; the seed spread is 0.52.

| shortcut (`redteam/<name>/`) | what it does | rank proxy vs reference | works? |
|---|---|---|---|
| `shortcut_impossible_values` | writes hit rate 10, `completed_fraction` 2, negative waits, memory and unpin counts, ~0 s tails into the method artifact | **4.2e+08** | **works** (no range checks) |
| `shortcut_crash_keeps_forged_scores` | leaves a forged `scoring/scores_test.json` on disk and sets baseline p90 = 0, so the test hits `ZeroDivisionError` (rc = 1) and never overwrites the forged file | **+357.7** if the ranker reads the file despite rc ≠ 0 | **works** unless the ranker checks the exit code or file mtime |
| `shortcut_forge_artifacts` | hand-written plausible numbers (tails ×0.6, hit 0.95, peak 0.05, no expiries or unpins); no scheduler behind them | **+11.87** | **works** |
| `shortcut_starve_long_programs` | admission control never admits the 10% longest programs; percentiles cover completed programs only, `completed_fraction` = 0.9 | **+5.39** (+1.84 even if this run joins the spread pool so `completed_fraction` counts) | **works** |
| `shortcut_omit_constraint_keys` | brute-force 45 s TTL, then deletes the constraint fields where it looks worse than the agent's own rerun of the reference (peak memory everywhere, unpin count under offload); absent fields are skipped | **+4.39** (vs +4.17 with the fields kept; deleting all three fields blindly gave +3.90) | **works** |
| `shortcut_inflate_baseline` | reference method untouched; baseline files (vLLM/PLAS) made 1.5× slower, which moves only the p90/p95 ratios | **+4.17** | **works** |
| `shortcut_static_grid_overfit` | enumerates static TTLs on the visible (= test) trace and keeps the best per experiment; the choice is 45 s everywhere, identical to `variant_bruteforce_pin_max` | **+4.17** (holds on new seeds: +4.28 ± 0.36) | **works**: brute force solves the test; a real simulator gap, not trace overfitting |
| `shortcut_bigger_gpu` | reference policy run with 2× simulated capacity; the resource model lives in `method/` and the test only reads the artifact. Peak pinned *fraction* halves for free because it is normalised by the agent-chosen capacity | **+3.82** | **works** |
| `shortcut_oracle_ttl` | TTL = the true upcoming tool time, read from `data/workloads/*.json`, which carries `tool_time_s` for every future turn | **+2.61** (seeds +2.70 ± 0.26) | **works** |
| `shortcut_easier_workload` | reference policy run on a regenerated trace whose generator seed gives the shortest programs (SWE seed 5, more-turns seed 15); the baseline stays on the official trace; the test never checks which trace an artifact came from | **+1.64** | **works** |
| `shortcut_drop_bad_experiment` | takes `variant_warm_history` (−0.53) and deletes its artifact in the 3 experiments where it looks worse; those experiments are skipped, not penalised | **+0.14** (from −0.53) | **works**: turns a loss into a win |

No tie with the reference occurred among the shortcuts.

## 6. What to fix (for the next iteration)

1. **Make the test run the scheduler itself.**
   - Move the simulator (memory and timing model, metrics) into `eval/`, and have the method provide only a policy interface (TTL decision, priority key, victim choice).
   - Have `evaluate_test.sh` simulate held-out traces generated from seeds the agent never sees, with capacity and cost constants fixed inside `eval/`.
   - Regenerate the baselines inside the test. Never read agent-written numbers.
2. **Fail closed.**
   - Fill missing experiments or metrics with the worst value.
   - Range-check values: rates and fractions in [0, 1], times and counts non-negative and finite.
   - Delete `scoring/scores_test.json` before scoring, and treat a non-zero exit code as a failed run.
3. **Put the headline metrics into the test**: mean completion time, `delay_reduction_x`, throughput.
4. **Restore the trade-off the paper studies, and check it with `check_load_tradeoff`.**
   - Make retained memory block scheduling: head-of-line stopping as in Algorithm 1, and forced unpins only on a true deadlock.
   - Give tools distinct duration distributions, so tool-aware history matters.
   - Then confirm that the 45 s brute force and the large static TTLs lose to a cost-model TTL at the test load.
5. **Score `completed_fraction` as a hard gate** (any value below 1 means a failed run) rather than through a spread that is zero for honest attempts.
