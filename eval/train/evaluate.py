"""Score every scheduling method on disk against the eval-owned baselines.

A *method* is declared by a manifest ``method/policies/<name>.json``:

    {"command": ["python", "method/my_policy.py", "--flag"]}

The command is started once per trace (cwd = workspace root) and must speak
the line-delimited JSON protocol in briefing/evaluation.md.  This script owns
the serving engine, the traces, the baselines and every number it writes: it
never reads anything a method wrote.  A method that crashes, hangs, breaks the
protocol or leaves programs unfinished in any trace of an experiment gets the
worst value of every metric of that experiment.

Usage:  python eval/<split>/evaluate.py [--policies-dir DIR] [--output FILE]
"""

from __future__ import annotations

import argparse
import json
import math
import multiprocessing
import os
import re
import shutil
import sys
import tempfile
import traceback
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[2]
if str(WORKSPACE) not in sys.path:
    sys.path.insert(0, str(WORKSPACE))

from eval.train.baselines import BASELINES  # noqa: E402
from eval.train.engine import (  # noqa: E402
    CAPACITY_TOKENS,
    Engine,
    InProcessPolicy,
    PolicyError,
    SubprocessPolicy,
)
from eval.train.workloads import generate  # noqa: E402

SPLIT = "train"
TRACES = 4
PROGRAMS = 160
DEFAULT_OUTPUT = "scoring/scores_train.json"


def trace_seed(experiment: str, index: int) -> str:
    return f"public-train:{experiment}:{index}"


class _sealed:
    """Train traces are public: nothing to hide while method code runs."""

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


# Every experiment: the workload, the operating point, the baselines that run
# next to the methods, and the baseline the ratios are taken against.
EXPERIMENTS = {
    "swebench_scaled_no_offload": {
        "dataset": "swebench", "arrival_rate": 0.30, "offload": False,
        "baselines": ["vllm", "plas"], "reference": "vllm"},
    "bfcl_scaled_no_offload": {
        "dataset": "bfcl", "arrival_rate": 3.0, "offload": False,
        "baselines": ["vllm", "plas"], "reference": "vllm"},
    "swebench_scaled_offload": {
        "dataset": "swebench", "arrival_rate": 0.30, "offload": True,
        "baselines": ["vllm", "plas", "infercept"], "reference": "vllm"},
    "turn_robustness_scaled": {
        "dataset": "swebench", "arrival_rate": 1.0, "offload": True, "turn_multiplier": 3,
        "baselines": ["vllm", "infercept"], "reference": "vllm"},
    "ablation_scaled": {
        "dataset": "bfcl", "arrival_rate": 3.0, "offload": False,
        "baselines": ["vllm", "program_fcfs"], "reference": "program_fcfs"},
    "tool_shift_scaled": {
        "dataset": "bfcl", "arrival_rate": 3.0, "offload": False, "shift": True,
        "baselines": ["vllm", "program_fcfs"], "reference": "vllm"},
    "mixed_agents_scaled": {
        "dataset": "mixed", "arrival_rate": 1.5, "offload": False,
        "baselines": ["vllm", "program_fcfs"], "reference": "vllm"},
}

# Scored metrics: name -> value given to a failed run.
WORST = {
    "delay_reduction_x": 0.0,
    "p90_delay_reduction_x": 0.0,
    "p95_delay_reduction_x": 0.0,
    "throughput_improvement_x": 0.0,
    "queue_wait_fraction": 1.0,
}

_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$")


# --------------------------------------------------------------------------
# Method discovery
# --------------------------------------------------------------------------


def discover(policies_dir: Path) -> dict[str, dict]:
    """name -> {"command": [...]} or {"error": "..."}."""
    methods: dict[str, dict] = {}
    if not policies_dir.is_dir():
        return methods
    for path in sorted(policies_dir.glob("*.json")):
        name = path.stem
        if name in BASELINES:
            name = f"{name}_method"
        if not _NAME.match(name):
            continue
        try:
            manifest = json.loads(path.read_text())
            command = manifest["command"]
            if not (isinstance(command, list) and command and all(isinstance(c, str) for c in command)):
                raise ValueError("command must be a non-empty list of strings")
            if command[0] in ("python", "python3"):
                command = [sys.executable] + command[1:]  # the evaluator's own interpreter
            methods[name] = {"command": command}
        except Exception as exc:  # malformed manifest -> failed method
            methods[name] = {"error": f"bad manifest {path.name}: {exc}"}
    return methods


# --------------------------------------------------------------------------
# Running
# --------------------------------------------------------------------------


def _trace(experiment: str, index: int) -> list[dict]:
    cfg = EXPERIMENTS[experiment]
    return generate(trace_seed(experiment, index), cfg["dataset"], programs=PROGRAMS,
                    arrival_rate=cfg["arrival_rate"], turn_multiplier=cfg.get("turn_multiplier", 1),
                    shift=cfg.get("shift", False))


def run_task(task: tuple) -> tuple:
    """Run one (method, experiment, trace).  Returns (method, experiment, index, summary-or-error)."""
    method, kind, spec, experiment, index, log_dir = task
    cfg = EXPERIMENTS[experiment]
    programs = _trace(experiment, index)
    scratch = None
    policy = None
    try:
        if kind == "baseline":
            policy = InProcessPolicy(BASELINES[spec]())
        else:
            scratch = tempfile.mkdtemp(prefix="policy-")
            env = dict(os.environ)
            env["PYTHONPATH"] = str(WORKSPACE)
            env["TMPDIR"] = scratch
            env["PYTHONHASHSEED"] = "0"
            log = Path(log_dir) / f"{method}__{experiment}__{index}.log"
            policy = SubprocessPolicy(spec, cwd=str(WORKSPACE), env=env, stderr_path=str(log))
        summary = Engine(programs, offload=cfg["offload"], policy=policy, capacity=CAPACITY_TOKENS).run()
        if summary["completed"] != summary["programs"]:
            raise PolicyError(f"only {summary['completed']}/{summary['programs']} programs completed")
        return method, experiment, index, summary
    except Exception as exc:
        if kind == "baseline":
            raise
        if isinstance(policy, SubprocessPolicy):
            policy.kill()
        detail = str(exc) if isinstance(exc, PolicyError) else f"{type(exc).__name__}: {exc}"
        return method, experiment, index, {"error": detail[:500]}
    finally:
        if scratch:
            shutil.rmtree(scratch, ignore_errors=True)


# --------------------------------------------------------------------------
# Metrics
# --------------------------------------------------------------------------


def _pct(values: list[float], q: float) -> float:
    s = sorted(values)
    return s[max(0, math.ceil(q * len(s)) - 1)]


def _gmean(values: list[float]) -> float:
    return math.exp(sum(math.log(v) for v in values) / len(values))


def score_method(runs: list[dict], ref: list[dict]) -> tuple[dict, dict]:
    if any("error" in r for r in runs):
        err = next(r["error"] for r in runs if "error" in r)
        return dict(WORST), {"failed": err}
    comp = [c for r in runs for c in r["completion_s"]]
    ref_comp = [c for r in ref for c in r["completion_s"]]
    values = {
        "delay_reduction_x": sum(ref_comp) / sum(comp),
        "p90_delay_reduction_x": _gmean([_pct(b["completion_s"], 0.90) / _pct(r["completion_s"], 0.90)
                                          for b, r in zip(ref, runs)]),
        "p95_delay_reduction_x": _gmean([_pct(b["completion_s"], 0.95) / _pct(r["completion_s"], 0.95)
                                          for b, r in zip(ref, runs)]),
        "throughput_improvement_x": sum(b["makespan_s"] for b in ref) / sum(r["makespan_s"] for r in runs),
        "queue_wait_fraction": sum(r["wait_total_s"] for r in runs) / sum(comp),
    }
    for k, v in values.items():
        if not math.isfinite(v) or v < 0:
            return dict(WORST), {"failed": f"non-finite {k}"}
    hits = sum(r["hits"] for r in runs)
    misses = sum(r["misses"] for r in runs)
    diag = {
        "avg_completion_time_s": sum(comp) / len(comp),
        "p90_completion_time_s": _pct(comp, 0.90),
        "p95_completion_time_s": _pct(comp, 0.95),
        "avg_queue_wait_s": sum(r["wait_total_s"] for r in runs) / sum(r["requests"] for r in runs),
        "throughput_jobs_per_s": sum(r["programs"] for r in runs) / sum(r["makespan_s"] for r in runs),
        "cache_hit_rate": hits / max(1, hits + misses),
        "mean_retained_memory_fraction": sum(r["retained_token_seconds"] for r in runs)
        / sum(r["capacity"] * r["makespan_s"] for r in runs),
        "peak_retained_memory_fraction": max(r["peak_retained_tokens"] / r["capacity"] for r in runs),
        "retain_decisions": sum(r["retain_decisions"] for r in runs),
        "expired_unused": sum(r["expired_unused"] for r in runs),
        "forced_releases": sum(r["forced_releases"] for r in runs),
        "completed_fraction": sum(r["completed"] for r in runs) / sum(r["programs"] for r in runs),
        "per_trace_avg_completion_s": [sum(r["completion_s"]) / len(r["completion_s"]) for r in runs],
    }
    return values, diag


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def evaluate(policies_dir: Path, workers: int, log_dir: Path) -> dict:
    methods = discover(policies_dir)
    tasks = []
    for experiment, cfg in EXPERIMENTS.items():
        for i in range(TRACES):
            for b in cfg["baselines"]:
                tasks.append((b, "baseline", b, experiment, i, str(log_dir)))
            for name, manifest in methods.items():
                if "command" in manifest:
                    tasks.append((name, "policy", manifest["command"], experiment, i, str(log_dir)))
    raw: dict = {}
    with _sealed(), ProcessPoolExecutor(max_workers=workers, mp_context=multiprocessing.get_context("fork")) as pool:
        for method, experiment, index, summary in pool.map(run_task, tasks):
            raw.setdefault(experiment, {}).setdefault(method, {})[index] = summary
    scores = {"_split": SPLIT, "_traces_per_experiment": TRACES, "_programs_per_trace": PROGRAMS,
              "experiments": {}, "_diagnostics": {}}
    for experiment, cfg in EXPERIMENTS.items():
        exp_raw = raw.get(experiment, {})
        ref = [exp_raw[cfg["reference"]][i] for i in range(TRACES)]
        results, diags = {}, {}
        names = list(cfg["baselines"]) + sorted(methods)
        for name in names:
            if name in methods and "error" in methods[name]:
                results[name], diags[name] = dict(WORST), {"failed": methods[name]["error"]}
                continue
            runs = [exp_raw.get(name, {}).get(i, {"error": "missing run"}) for i in range(TRACES)]
            results[name], diags[name] = score_method(runs, ref)
        scores["experiments"][experiment] = {"reference_baseline": cfg["reference"], "results": results}
        scores["_diagnostics"][experiment] = diags
    return scores


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--policies-dir", type=Path, default=WORKSPACE / "method" / "policies")
    ap.add_argument("--output", type=Path, default=WORKSPACE / DEFAULT_OUTPUT)
    ap.add_argument("--workers", type=int, default=max(1, os.cpu_count() or 1))
    ap.add_argument("--log-dir", type=Path, default=WORKSPACE / "outputs" / f"policy_logs_{SPLIT}")
    args = ap.parse_args()
    if args.output.exists():
        args.output.unlink()  # never leave a stale score file behind
    args.log_dir.mkdir(parents=True, exist_ok=True)
    try:
        scores = evaluate(args.policies_dir, args.workers, args.log_dir)
    except Exception:
        traceback.print_exc()
        sys.exit(1)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n")
    n_methods = len(next(iter(scores["experiments"].values()))["results"])
    failed = sorted({m for d in scores["_diagnostics"].values() for m, v in d.items() if "failed" in v})
    print(f"[{SPLIT}] wrote {args.output} ({len(scores['experiments'])} experiments, {n_methods} entries each)"
          + (f"; failed methods: {failed}" if failed else ""))


if __name__ == "__main__":
    main()
