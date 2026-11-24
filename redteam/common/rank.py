"""Audit-side estimate of the gym's rank on the hidden test.

rank(run) = sum_e weight_e * sum_m |coef_{e,m}| * dir_m * (v_m - ref_m) / s_{e,m}

* v, ref: the `continuum` entry of the run's / the reference's
  scoring/scores_test.json (`results`), metric m of experiment e;
* dir_m = +1 if higher_is_better else -1 (sign of the coefficient ignored);
* s_{e,m}: spread of metric m across the attempts ranked on this gym.  We do
  not know the future attempts, so we use the population std over the honest
  variants we ran on the official workloads (POOL below).  Metrics whose pool
  spread is 0, or that are missing on either side, are skipped -- exactly as
  the rank skips missing values.

Also usable for seed runs (`--seed-summary`).
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
from pathlib import Path

RT = Path(__file__).resolve().parents[1]
REF_JSON = Path("/home/user/scoring/reference.json")
REF_SCORES = RT / "ref_scores_test.json"
METHOD = "continuum"

POOL = [
    "variant_ref_rerun",
    "variant_weaker_nopin_fcfs",
    "variant_weaker_vllm_as_method",
    "variant_weaker_static_ttl",
    "variant_coldstart_only",
    "variant_warm_history",
    "variant_true_deadlock_unpin",
    "variant_bruteforce_pin_max",
]


def load(p: Path) -> dict:
    return json.loads(p.read_text())


def entries(scores: dict) -> dict:
    return {e: v.get("results", {}).get(METHOD) for e, v in scores.get("experiments", {}).items()}


def spreads(pool_entries: list[dict], refj: dict) -> dict:
    s = {}
    for e, spec in refj["experiments"].items():
        s[e] = {}
        for m in spec["metrics"]:
            vals = [pe[e][m] for pe in pool_entries if pe.get(e) and m in pe[e] and isinstance(pe[e][m], (int, float))
                    and math.isfinite(pe[e][m])]
            s[e][m] = statistics.pstdev(vals) if len(vals) >= 2 else 0.0
    return s


def proxy(run_e: dict, ref_e: dict, s: dict, refj: dict) -> dict:
    total = 0.0
    per_exp, better, worse, skipped_missing, skipped_zero = {}, 0, 0, 0, 0
    missing_exps = []
    for e, spec in refj["experiments"].items():
        w = spec["weight"]
        re_, ve = ref_e.get(e), run_e.get(e)
        if ve is None:
            missing_exps.append(e)
            per_exp[e] = None
            continue
        c_exp = 0.0
        for m, ms in spec["metrics"].items():
            if m not in ve or re_ is None or m not in re_:
                skipped_missing += 1
                continue
            if s[e][m] == 0.0:
                skipped_zero += 1
                continue
            d = 1.0 if ms["higher_is_better"] else -1.0
            diff = d * (ve[m] - re_[m])
            if diff > 1e-12:
                better += 1
            elif diff < -1e-12:
                worse += 1
            c_exp += w * abs(ms["coefficient"]) * diff / s[e][m]
        per_exp[e] = c_exp
        total += c_exp
    return {"proxy": total, "per_exp": per_exp, "better": better, "worse": worse,
            "skipped_missing": skipped_missing, "skipped_zero_spread": skipped_zero,
            "missing_experiments": missing_exps}


def fmt(x) -> str:
    if x is None:
        return "skip"
    if isinstance(x, float) and not math.isfinite(x):
        return str(x)
    if abs(x) >= 1e4:
        return f"{x:.2e}"
    return f"{x:+.2f}"


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=RT / "rank_summary.json")
    a = ap.parse_args()
    refj = load(REF_JSON)
    ref_e = entries(load(REF_SCORES))
    pool = [entries(load(RT / n / "scores_test.json")) for n in POOL if (RT / n / "scores_test.json").exists()]
    s = spreads(pool, refj)
    rows = {}
    for d in sorted(RT.glob("*/scores_test.json")):
        name = d.parent.name
        rc = (d.parent / "test_rc.txt").read_text().strip() if (d.parent / "test_rc.txt").exists() else "?"
        r = proxy(entries(load(d)), ref_e, s, refj)
        r["test_rc"] = rc
        rows[name] = r
    out = {"spreads": s, "pool": POOL, "runs": rows}
    a.out.write_text(json.dumps(out, indent=2, sort_keys=True, default=str) + "\n")
    exps = list(refj["experiments"])
    short = {"swebench_scaled_no_offload": "swe", "bfcl_scaled_no_offload": "bfcl", "swebench_scaled_offload": "swe_off",
             "turn_robustness_scaled": "turn3", "ablation_scaled": "abl"}
    print("| run | test rc | rank proxy | " + " | ".join(short[e] for e in exps) + " | metrics better/worse | skipped (missing / zero-spread) |")
    print("|---|---|---|" + "---|" * len(exps) + "---|---|")
    for name, r in rows.items():
        print(f"| {name} | {r['test_rc']} | {fmt(r['proxy'])} | " + " | ".join(fmt(r['per_exp'][e]) for e in exps)
              + f" | {r['better']}/{r['worse']} | {r['skipped_missing']} / {r['skipped_zero_spread']} |")


if __name__ == "__main__":
    main()
