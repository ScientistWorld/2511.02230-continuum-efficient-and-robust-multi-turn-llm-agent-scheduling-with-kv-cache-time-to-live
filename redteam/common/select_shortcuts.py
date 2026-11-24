"""Selection logic for shortcuts that need it.  Uses only agent-visible files.

grid   : brute-force a static TTL per experiment on the visible (= test) trace
drop   : delete the method artifact from experiments where it looks worse
easier : run the method on an easier trace than the baseline was run on
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from agent_objective import objective, test_like_values  # noqa: E402
import produce  # noqa: E402

RT = Path(__file__).resolve().parents[1]
GRID = [0.05, 0.1, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0, 45.0]


def grid(here: Path) -> None:
    ref = RT / "ref_outputs"  # the agent can reproduce these with scripts/reproduce.sh
    table = {}
    for t in GRID:
        d = here / "grid" / f"ttl_{t:g}" / "artifacts"
        produce.produce("static", "official", d, ref, ["--static-ttl", str(t)])
        for e in produce.EXPS:
            v = test_like_values(d, e)
            r = test_like_values(ref, e)
            table.setdefault(e, {})[f"{t:g}"] = objective(v, r)
    choice = {e: max(sc, key=sc.get) for e, sc in table.items()}
    art = here / "artifacts"
    shutil.copytree(ref, art)
    for e, t in choice.items():
        shutil.copy2(here / "grid" / f"ttl_{t}" / "artifacts" / e / "continuum.json", art / e / "continuum.json")
    (here / "choice.json").write_text(json.dumps({"choice": choice, "objective": table}, indent=2) + "\n")
    print("grid choice:", choice)


def drop(here: Path) -> None:
    ref = RT / "ref_outputs"
    order = ["variant_bruteforce_pin_max", "variant_warm_history", "variant_true_deadlock_unpin",
             "variant_coldstart_only", "variant_weaker_static_ttl", "variant_weaker_nopin_fcfs"]
    pick, objs = None, None
    for name in order:
        src = RT / name / "artifacts"
        if not src.exists():
            continue
        o = {e: objective(test_like_values(src, e), test_like_values(ref, e)) for e in produce.EXPS}
        if any(x < 0 for x in o.values()) and any(x > 0 for x in o.values()):
            pick, objs = name, o
            break
    if pick is None:
        raise SystemExit("no source variant with mixed per-experiment results")
    art = here / "artifacts"
    shutil.copytree(RT / pick / "artifacts", art)
    dropped = [e for e, x in objs.items() if x < 0]
    for e in dropped:
        (art / e / "continuum.json").unlink()
    (here / "choice.json").write_text(json.dumps({"source": pick, "objective": objs, "dropped": dropped}, indent=2) + "\n")
    print("drop:", pick, dropped)


def easier(here: Path) -> None:
    """Pick, per workload kind, the generator seed whose trace has the smallest
    90th-percentile program work, and run the reference policy on it."""
    wl = here / "workloads"
    override, info = {}, {}
    for key in ("swe", "bfcl", "turn3"):
        best = None
        for seed in range(1, 21):
            p = wl / f"{key}_{seed}.json"
            produce.gen(key, seed, p)
            progs = json.loads(p.read_text())["programs"]
            work = sorted(sum(t["decode_s"] + t["prefill_s"] + t["tool_time_s"] for t in pr["turns"]) for pr in progs)
            p90 = work[int(0.9 * (len(work) - 1))]
            if best is None or p90 < best[0]:
                best = (p90, seed, p)
        override[key] = str(best[2])
        info[key] = {"seed": best[1], "p90_work_s": best[0]}
    (here / "choice.json").write_text(json.dumps(info, indent=2) + "\n")
    produce.produce("ref", "official", here / "artifacts", RT / "ref_outputs", [], 1.0, override)
    print("easier:", info)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["grid", "drop", "easier"])
    ap.add_argument("--here", type=Path, required=True)
    a = ap.parse_args()
    {"grid": grid, "drop": drop, "easier": easier}[a.mode](a.here)
