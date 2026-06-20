# Reproduction Milestones

**Current: core_claim_plus**

## Progress Log

### [2026-06-20 13:02] - core_claim_plus
- Validated the packaged Continuum reproduction with `python validate.py --compare`.
- Reproduced the core delay-reduction claim on a scaled SWE-Bench-style workload and additional BFCL-style, CPU-offload, higher-turn, and ablation settings.
- Confirmed evaluation is reusable and method-independent: `eval/` and `data/` do not import from `method/`, and `scripts/evaluate.sh` scores JSON artifacts produced by scheduler runs.

### [2026-06-20 13:04] - core_claim_plus
- Audited the existing method, evaluation, scripts, scoring files, and environment packaging after the continuation reset.
- Fixed audit issues by setting Continuum's cold-start threshold to the paper's `K = 100`, changing the PLAS baseline to use cumulative attained service, and clarifying that the simulator implements the simplified Equation 2 form.
- Reran `bash scripts/reproduce.sh`, `bash scripts/evaluate.sh outputs`, and `python validate.py --compare`; the regenerated scores still support the scaled core claim and additional settings.
- Restored the milestone to `core_claim_plus` after the stricter rerun.

## Stop Justification
- Completed at milestone `core_claim_plus`.
