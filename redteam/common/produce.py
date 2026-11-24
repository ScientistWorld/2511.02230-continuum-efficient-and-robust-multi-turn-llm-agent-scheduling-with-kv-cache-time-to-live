"""Build a full outputs/ tree (5 experiments) for one scheduler variant.

Baseline artifacts (vllm/plas/infercept/static_ttl) are copied unchanged from a
baseline tree (the reference's own outputs for the official workloads, or a
seed-run baseline tree); only the method entry `continuum.json` is produced by
the variant.  The 5 experiments need 4 distinct simulations because
ablation_scaled uses the same configuration as swebench_scaled_no_offload.
"""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
import sys
from pathlib import Path

RT = Path(__file__).resolve().parents[1]
SIM = RT / "common" / "sim_variants.py"
GYM_SIM = Path("/home/user/method/continuum_sim.py")

# experiment -> (workload key, offload, capacity)
EXPS = {
    "swebench_scaled_no_offload": ("swe", False, 8.0),
    "bfcl_scaled_no_offload": ("bfcl", False, 8.0),
    "swebench_scaled_offload": ("swe", True, 3.0),
    "turn_robustness_scaled": ("turn3", True, 3.0),
    "ablation_scaled": ("swe", False, 8.0),
}
BASELINE_OF = {e: ("plas" if e == "ablation_scaled" else "vllm") for e in EXPS}

# official workloads + 3 extra workload seeds, same generator settings as
# scripts/reproduce.sh (programs=120; arrival 0.13/0.13/0.25; turn mult 1/1/3)
SEED_SETS = {
    "official": {"swe": 7, "bfcl": 11, "turn3": 13},
    "seedB": {"swe": 101, "bfcl": 111, "turn3": 113},
    "seedC": {"swe": 201, "bfcl": 211, "turn3": 213},
    "seedD": {"swe": 301, "bfcl": 311, "turn3": 313},
}
GEN_ARGS = {
    "swe": ["--dataset", "swebench", "--programs", "120", "--arrival-rate", "0.13"],
    "bfcl": ["--dataset", "bfcl", "--programs", "120", "--arrival-rate", "0.13"],
    "turn3": ["--dataset", "swebench", "--programs", "120", "--arrival-rate", "0.25", "--turn-multiplier", "3"],
}
WL_DIR = RT / "seed_runs" / "workloads"


def workload_path(set_name: str, key: str) -> Path:
    if set_name == "official":
        return Path("/home/user/data/workloads") / {
            "swe": "swebench_scaled.json",
            "bfcl": "bfcl_scaled.json",
            "turn3": "swebench_turn3_scaled.json",
        }[key]
    return WL_DIR / set_name / f"{key}.json"


def prior_path(set_name: str, key: str) -> Path:
    return WL_DIR / f"prior_{set_name}" / f"{key}.json"


def gen(key: str, seed: int, out: Path) -> None:
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        [sys.executable, "/home/user/data/workloads.py", *GEN_ARGS[key], "--seed", str(seed), "--output", str(out)],
        check=True,
    )


def ensure_workloads(set_name: str) -> None:
    for key, seed in SEED_SETS[set_name].items():
        if set_name != "official":
            gen(key, seed, workload_path(set_name, key))
        gen(key, 9000 + seed, prior_path(set_name, key))  # warm-start prior trace


def run_sim(args: list[str], out: Path) -> None:
    if out.exists():
        return
    out.parent.mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".tmp")
    subprocess.run([sys.executable, *args, "--output", str(tmp)], check=True, env={"PYTHONPATH": "/home/user", "PATH": "/usr/local/bin:/usr/bin:/bin"})
    tmp.rename(out)


def ensure_seed_baselines(set_name: str) -> Path:
    """Run the gym's own simulator for the baseline policies on a seed set."""
    base = RT / "seed_runs" / set_name / "_baselines"
    for exp, (key, off, cap) in EXPS.items():
        pol = BASELINE_OF[exp]
        a = [str(GYM_SIM), "--workload", str(workload_path(set_name, key)), "--policy", pol, "--capacity", str(cap)]
        if off:
            a.append("--offload")
        run_sim(a, base / exp / f"{pol}.json")
    return base


def produce(variant: str, set_name: str, outdir: Path, baselines: Path, extra: list[str], cap_scale: float = 1.0,
            workload_override: dict | None = None) -> None:
    ensure_workloads(set_name)
    outdir.mkdir(parents=True, exist_ok=True)
    for exp in EXPS:
        (outdir / exp).mkdir(parents=True, exist_ok=True)
        for f in sorted((baselines / exp).glob("*.json")):
            if f.name != "continuum.json":
                shutil.copy2(f, outdir / exp / f.name)
    cache: dict[tuple, Path] = {}
    for exp, (key, off, cap) in EXPS.items():
        dst = outdir / exp / "continuum.json"
        if variant == "vllm_as_method":
            src_exp = "swebench_scaled_no_offload" if exp == "ablation_scaled" else exp
            shutil.copy2(baselines / src_exp / "vllm.json", dst)
            continue
        wl = (workload_override or {}).get(key, workload_path(set_name, key))
        cfg = (str(wl), off, cap * cap_scale)
        if cfg in cache:
            shutil.copy2(cache[cfg], dst)
            continue
        a = [str(SIM), "--workload", str(wl), "--variant", variant, "--capacity", str(cap * cap_scale)]
        if off:
            a.append("--offload")
        if variant == "warm_history":
            a += ["--prior-workload", str(prior_path(set_name, key))]
        a += extra
        run_sim(a, dst)
        cache[cfg] = dst


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", required=True)
    ap.add_argument("--set", default="official", choices=sorted(SEED_SETS))
    ap.add_argument("--outdir", type=Path, required=True)
    ap.add_argument("--baselines", type=Path, default=None,
                    help="baseline tree; default: reference outputs (official) or seed baselines")
    ap.add_argument("--cap-scale", type=float, default=1.0)
    ap.add_argument("--workload-override", type=str, default=None, help="JSON {key: path}")
    ap.add_argument("extra", nargs=argparse.REMAINDER)
    a = ap.parse_args()
    extra = [x for x in a.extra if x != "--"]
    if a.baselines is None:
        a.baselines = RT / "ref_outputs" if a.set == "official" else ensure_seed_baselines(a.set)
    wo = json.loads(a.workload_override) if a.workload_override else None
    produce(a.variant, a.set, a.outdir, a.baselines, extra, a.cap_scale, wo)


if __name__ == "__main__":
    main()
