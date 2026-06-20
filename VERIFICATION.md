# Verification Report

## Initial Assessment

The workspace claimed `core_claim_plus`, and that milestone is justified. The implementation is a scaled discrete-event reproduction of the paper's scheduler: it runs end-to-end, produces artifacts, and shows the core latency-reduction claim on multiple deterministic workload settings.

The main caveat is scope: this is not the paper's full vLLM/Llama hardware evaluation. It is a synthetic-trace simulator parameterized by the paper's published workload statistics.

## Issues Found

- **Minor:** `eval/evaluate_results.py` only scored a fixed list of method artifact names. A future scientist could write a new artifact under `outputs/<experiment>/` and have it ignored by `scripts/evaluate.sh`.
- **Minor:** `scoring/scores.json` omitted two constraint metrics already defined in `reference.json`: `avg_queue_wait_s` and `deadlock_unpins`.
- **Cosmetic/environment:** `README.md` and `manifest.json` are bind-mounted from `/dev/null` in this session, so they appear modified as character devices locally. The committed repository still contains normal tracked versions. They were marked skip-worktree locally to keep verification focused on repository content.
- **Cosmetic:** Stale tracked `trajectory/turn_*.jsonl` artifacts were deleted in the working tree and should not ship as root-level generated artifacts.

## Fixes Applied

- Updated `eval/evaluate_results.py` to discover all JSON artifacts per experiment and use only the configured baseline name for ratios.
- Regenerated `scoring/scores.json` via `bash scripts/evaluate.sh outputs`, adding the missing constraint metrics.
- Removed the stale tracked `trajectory/turn_*.jsonl` entries from the Git index.
- Re-ran `bash scripts/evaluate_train.sh`, `bash scripts/evaluate_test.sh`, and `python validate.py --compare`.

## Final Judgment

The workspace is ready to serve as a research gym in both improve and from-scratch modes. The problem/evaluation docs and `eval/`/`data/` separation are method-safe enough for from-scratch agents, while improve-mode agents have a working paper-method implementation and baseline artifacts to compare against.

- Milestone: core_claim_plus
- Ready for gym use: yes
- Confidence: medium
- Key limitation: synthetic-trace simulator only; the exact vLLM/Llama hardware experiments and unreleased traces are not reproduced.
