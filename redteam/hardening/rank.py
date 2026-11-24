"""Rank proxy for the hardened gym (same formula as redteam/common/rank.py).

rank(m) = sum_e w_e * sum_k |coef_ek| * dir_k * (v_mek - v_ref,ek) / spread_ek

spread_ek = population std of metric k in experiment e over a pool of honest
attempts (the variants run here), standing in for "the attempts later ranked".
Also reports paired per-trace noise: for each experiment the per-trace ratio
(reference avg completion / method avg completion), mean and standard error.

Usage: python rank.py SCORES.json [--ref continuum] [--pool a,b,c] [--md]
"""
import argparse, json, math, statistics
from pathlib import Path

ap = argparse.ArgumentParser()
ap.add_argument("scores")
ap.add_argument("--reference-json", default="/home/user/scoring/reference.json")
ap.add_argument("--ref", default="continuum")
ap.add_argument("--pool", default="")
ap.add_argument("--out", default="")
a = ap.parse_args()
refj = json.loads(Path(a.reference_json).read_text())["experiments"]
sc = json.loads(Path(a.scores).read_text())
exps = sc["experiments"]
diag = sc.get("_diagnostics", {})
methods = sorted(set.intersection(*[set(v["results"]) for v in exps.values()]))  # methods scored in every experiment
pool = [m for m in a.pool.split(",") if m] or methods
spread = {}
for e, spec in refj.items():
    for k in spec["metrics"]:
        vals = [exps[e]["results"][m][k] for m in pool if m in exps[e]["results"]]
        spread[(e, k)] = statistics.pstdev(vals) if len(vals) > 1 else 0.0
rows = []
for m in methods:
    total, per = 0.0, {}
    for e, spec in refj.items():
        r, v = exps[e]["results"][a.ref], exps[e]["results"][m]
        c = 0.0
        for k, ms in spec["metrics"].items():
            if spread[(e, k)] == 0:
                continue
            d = 1.0 if ms["higher_is_better"] else -1.0
            c += abs(ms["coefficient"]) * d * (v[k] - r[k]) / spread[(e, k)]
        per[e] = spec["weight"] * c
        total += spec["weight"] * c
    # paired per-trace delay ratio vs reference
    paired = {}
    for e in refj:
        dm, dr = diag.get(e, {}).get(m, {}), diag.get(e, {}).get(a.ref, {})
        if "per_trace_avg_completion_s" in dm and "per_trace_avg_completion_s" in dr:
            rat = [x / y for x, y in zip(dr["per_trace_avg_completion_s"], dm["per_trace_avg_completion_s"])]
            paired[e] = (statistics.mean(rat), statistics.pstdev(rat) / math.sqrt(len(rat)))
    w = {e: refj[e]["weight"] for e in paired}
    wmean = sum(w[e] * paired[e][0] for e in paired) / max(1e-9, sum(w.values())) if paired else float("nan")
    wse = math.sqrt(sum((w[e] * paired[e][1]) ** 2 for e in paired)) / max(1e-9, sum(w.values())) if paired else float("nan")
    rows.append((total, m, per, paired, wmean, wse))
rows.sort(reverse=True)
lines = ["| method | rank proxy | " + " | ".join(refj) + " | weighted paired delay ratio vs ref (mean ± SE) |",
         "|---|---|" + "---|" * len(refj) + "---|"]
for total, m, per, paired, wmean, wse in rows:
    cells = []
    for e in refj:
        p = paired.get(e)
        cells.append(f"{per[e]:+.2f} ({p[0]:.3f}±{p[1]:.3f})" if p else f"{per[e]:+.2f}")
    lines.append(f"| {m} | {total:+.2f} | " + " | ".join(cells) + f" | {wmean:.3f} ± {wse:.3f} |")
out = "\n".join(lines)
print(out)
if a.out:
    Path(a.out).write_text(out + "\n")
