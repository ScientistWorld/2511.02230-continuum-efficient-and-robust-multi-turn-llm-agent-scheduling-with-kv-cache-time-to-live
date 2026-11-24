# Train/Test Evaluation Design Notes

Current design (iteration 11). The rationale and verification are in `HARDENING.md`, and the problem-facing protocol is in `briefing/evaluation.md`.

## Split

- **Train** (`eval/train/`, `scripts/evaluate_train.sh` → `scoring/scores_train.json`, copied to `scoring/scores.json`): 4 public traces per experiment, 160 programs each.
- **Test** (`eval/test/`, `scripts/evaluate_test.sh` → `scoring/scores_test.json`): 8 hidden traces per experiment. They are generated in memory from a key inside `eval/test/`, from the same distribution with different seeds. `eval/test/` is an independent copy (no imports from `eval/train/`) and is chmod 000 while policies run.
- Both splits score the same metrics. They differ in their traces, so a method cannot tune to the test traces.

## What the evaluator owns

The serving engine (memory, timing, offload), trace generation, baselines (vLLM, program-FCFS, PLAS, InferCept), metric computation and failure handling all live in `eval/`. A method is a policy process discovered from `method/policies/*.json`. `eval/` never imports `method/` and never reads method-written files.

## Scored metrics (every experiment)

`delay_reduction_x`, `p90_delay_reduction_x`, `p95_delay_reduction_x`, `throughput_improvement_x` (higher is better) and `queue_wait_fraction` (lower is better). A failed run gets 0 for the ratios and 1 for `queue_wait_fraction`. Absolute times, hit rate, retained memory, forced releases and expiries are unscored `_diagnostics`.

## Runtime

The full hardening suite (24 policies × 7 experiments × 12 traces) plus the reference reproduction ran in about 6 minutes on one CPU.
