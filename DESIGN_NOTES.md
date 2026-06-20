# Train/Test Evaluation Design Notes

## What I Checked

- Read `eval/train/evaluate.py`, `eval/test/evaluate.py`, `scripts/evaluate_train.sh`, `scripts/evaluate_test.sh`, and `scoring/reference.json`.
- Checked that the evaluators read scheduler artifacts from `outputs/<experiment>/<method>.json` rather than importing or executing `method/`.
- Checked for train/test cross-imports and score-stub files.
- Checked `reference.json` for paper-agreement metric names and for missing `higher_is_better`, `coefficient`, or `description` fields.
- Ran `bash -n` on both train/test evaluation shell scripts.

## Changes Made

- Fixed a test-slice coupling issue: `eval/test/evaluate.py` no longer depends on `scoring/scores_train.json` to enumerate methods. It now discovers methods directly from held-out artifact directories, matching the train evaluator's method-agnostic artifact interface.
- Updated `scripts/evaluate_test.sh` to match the new standalone test evaluator interface and removed the stale train-score argument.
- Added `avg_queue_wait_s` to the visible train slice, because queueing bubbles are a direct mechanism in the paper's claim and a useful development signal.
- Added `avg_queue_wait_s` and `deadlock_unpins` to the held-out test slice. These catch shortcuts that improve mean completion time by excessive pinning, stalled scheduling, or relying on recovery unpins.
- Added required metric descriptions throughout `scoring/reference.json`.
- Added `avg_queue_wait_s` and `deadlock_unpins` to every experiment's metric schema with nonzero constraint-oriented coefficients.

## Design Rationale

The current artifacts are run-level scheduler summaries, so a conventional per-sample data split would not isolate hidden behavior without rerunning compute. I kept a metric-split design: train exposes headline mean delay, queue wait, throughput, and completion, while test independently scores tail latency plus cache/resource robustness. This makes a narrow method that optimizes visible mean latency by over-retaining KV cache more likely to regress on hidden `peak_pinned_memory_fraction`, `expired_pin_fraction`, `deadlock_unpins`, and `p90_delay_reduction_x`.

## Runtime Concerns for the Next Iteration

- The held-out test slice assumes every method artifact includes `p90_completion_time_s`, `avg_queue_wait_s`, `cache_hit_rate`, `peak_pinned_memory_fraction`, `expired_pin_fraction`, `deadlock_unpins`, and `completed_fraction`. Existing artifacts do, but future method runners should preserve this JSON schema.
- `completed_fraction` is currently saturated at 1.0 in the existing artifacts. It is still useful as a guardrail, but it may not distinguish methods unless a future shortcut drops work.
- This pass did not execute the evaluators or generate `scoring/scores_train.json` / `scoring/scores_test.json`, per the design-only instruction.
