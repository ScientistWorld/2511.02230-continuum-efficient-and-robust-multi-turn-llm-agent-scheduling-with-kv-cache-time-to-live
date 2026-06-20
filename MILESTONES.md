# Reproduction Milestones

**Current: core_claim_plus**

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
