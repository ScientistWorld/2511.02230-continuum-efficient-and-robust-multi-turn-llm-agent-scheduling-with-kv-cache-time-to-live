"""Workload-seed reruns (the simulator itself is deterministic, so a "seed" is
the trace-generator seed).  For every seed set we run the gym's baselines with
the gym's own simulator, the reference policy and every honest variant, score
each tree with the gym's test evaluator, and summarise:

* the reference's spread across seeds (per test metric and in rank-proxy units)
* each variant's paired difference to the reference on the same seed.
"""

from __future__ import annotations

import argparse
import json
import math
import shutil
import statistics
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import produce  # noqa: E402
import rank  # noqa: E402

RT = Path(__file__).resolve().parents[1]
SR = RT / "seed_runs"
SETS = ["seedB", "seedC", "seedD"]
# folder name on the official run -> (variant, extra args)
VARIANTS = {
    "variant_ref_rerun": ("ref", []),
    "variant_weaker_nopin_fcfs": ("nopin_fcfs", []),
    "variant_weaker_vllm_as_method": ("vllm_as_method", []),
    "variant_weaker_static_ttl": ("static", ["--static-ttl", "0.25"]),
    "variant_coldstart_only": ("coldstart_only", []),
    "variant_warm_history": ("warm_history", []),
    "variant_true_deadlock_unpin": ("true_deadlock_unpin", []),
    "variant_bruteforce_pin_max": ("pin_max", []),
    "shortcut_oracle_ttl": ("oracle", []),
}


def score(art: Path, out: Path) -> None:
    subprocess.run([sys.executable, "/home/user/eval/test/evaluate.py", "--artifacts", str(art), "--output", str(out)],
                   check=True, stdout=subprocess.DEVNULL)


def run() -> None:
    choice_f = RT / "shortcut_static_grid_overfit" / "choice.json"
    grid_choice = json.loads(choice_f.read_text())["choice"] if choice_f.exists() else None
    for s in SETS:
        produce.ensure_workloads(s)
        base = produce.ensure_seed_baselines(s)
        for name, (v, extra) in VARIANTS.items():
            d = SR / s / name
            if (d / "scores_test.json").exists():
                continue
            produce.produce(v, s, d / "artifacts", base, extra)
            score(d / "artifacts", d / "scores_test.json")
            print(s, name, "done", flush=True)
        if grid_choice:
            d = SR / s / "shortcut_static_grid_overfit"
            if not (d / "scores_test.json").exists():
                for t in sorted(set(grid_choice.values())):
                    produce.produce("static", s, d / f"ttl_{t}", base, ["--static-ttl", t])
                art = d / "artifacts"
                shutil.copytree(base, art, dirs_exist_ok=True)
                for e, t in grid_choice.items():
                    shutil.copy2(d / f"ttl_{t}" / e / "continuum.json", art / e / "continuum.json")
                score(art, d / "scores_test.json")
                print(s, "grid done", flush=True)


def summary() -> None:
    refj = rank.load(rank.REF_JSON)
    pool = [rank.entries(rank.load(RT / n / "scores_test.json")) for n in rank.POOL
            if (RT / n / "scores_test.json").exists()]
    sp = rank.spreads(pool, refj)
    ref_off = rank.entries(rank.load(rank.REF_SCORES))
    out = {"ref_metric_spread": {}, "ref_proxy_vs_official": {}, "paired": {}}
    # 1) reference per-metric spread across seeds
    ref_by_set = {s: rank.entries(rank.load(SR / s / "variant_ref_rerun" / "scores_test.json")) for s in SETS}
    for e in refj["experiments"]:
        out["ref_metric_spread"][e] = {}
        for m in ref_off[e]:
            vals = [ref_by_set[s][e][m] for s in SETS]
            allv = vals + [ref_off[e][m]]
            out["ref_metric_spread"][e][m] = {
                "official": ref_off[e][m], "seeds": vals,
                "std_3seeds": statistics.stdev(vals), "std_4incl_official": statistics.stdev(allv)}
    # 2) reference proxy movement from the workload draw alone
    for s in SETS:
        out["ref_proxy_vs_official"][s] = rank.proxy(ref_by_set[s], ref_off, sp, refj)["proxy"]
    # 3) paired variant - reference on the same seed (proxy units)
    names = list(VARIANTS) + ["shortcut_static_grid_overfit"]
    for n in names:
        vals = []
        for s in SETS:
            f = SR / s / n / "scores_test.json"
            if f.exists():
                vals.append(rank.proxy(rank.entries(rank.load(f)), ref_by_set[s], sp, refj)["proxy"])
        if vals:
            out["paired"][n] = {"per_seed": vals, "mean": statistics.mean(vals),
                                "std": statistics.stdev(vals) if len(vals) > 1 else 0.0}
    (SR / "seed_summary.json").write_text(json.dumps(out, indent=2) + "\n")
    rp = list(out["ref_proxy_vs_official"].values())
    print("reference proxy on seeds vs official:", [f"{x:+.2f}" for x in rp],
          f"std={statistics.stdev(rp):.2f}")
    print("| variant | paired proxy vs ref per seed (B, C, D) | mean | std |")
    print("|---|---|---|---|")
    for n, r in out["paired"].items():
        print(f"| {n} | " + ", ".join(f"{x:+.2f}" for x in r["per_seed"]) + f" | {r['mean']:+.2f} | {r['std']:.2f} |")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["run", "summary"])
    a = ap.parse_args()
    {"run": run, "summary": summary}[a.mode]()
