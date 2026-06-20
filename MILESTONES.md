# Reproduction Milestones

**Current: core_claim_plus**

## Progress Log

### [2026-06-20 13:02] - core_claim_plus
- Validated the packaged Continuum reproduction with `python validate.py --compare`.
- Reproduced the core delay-reduction claim on a scaled SWE-Bench-style workload and additional BFCL-style, CPU-offload, higher-turn, and ablation settings.
- Confirmed evaluation is reusable and method-independent: `eval/` and `data/` do not import from `method/`, and `scripts/evaluate.sh` scores JSON artifacts produced by scheduler runs.

## Stop Justification
- Completed at milestone `core_claim_plus`.
