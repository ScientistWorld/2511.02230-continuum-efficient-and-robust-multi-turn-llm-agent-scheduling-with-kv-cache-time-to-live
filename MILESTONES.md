# Reproduction Milestones

**Current: secondary_claims**

## Progress Log

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
