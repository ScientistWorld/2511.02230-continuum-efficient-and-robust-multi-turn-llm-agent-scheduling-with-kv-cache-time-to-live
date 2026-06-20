"""Visible train-slice scorer for scheduler artifacts.

This evaluator is intentionally method-agnostic: it reads JSON artifacts that
methods already wrote under outputs/<experiment>/<method>.json and never
imports or executes method code.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPERIMENTS = {
    "swebench_scaled_no_offload": {"baseline": "vllm"},
    "bfcl_scaled_no_offload": {"baseline": "vllm"},
    "swebench_scaled_offload": {"baseline": "vllm"},
    "turn_robustness_scaled": {"baseline": "vllm"},
    "ablation_scaled": {"baseline": "plas"},
}


TRAIN_METRICS = [
    "avg_completion_time_s",
    "avg_queue_wait_s",
    "throughput_jobs_per_s",
    "completed_fraction",
]


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing artifact: {path}")
    return json.loads(path.read_text())


def discover_artifacts(artifacts_dir: Path, experiment: str) -> dict[str, Path]:
    exp_dir = artifacts_dir / experiment
    if not exp_dir.is_dir():
        raise FileNotFoundError(f"missing experiment artifact directory: {exp_dir}")
    paths = {
        path.stem: path
        for path in sorted(exp_dir.glob("*.json"))
        if path.is_file()
    }
    if not paths:
        raise FileNotFoundError(f"no JSON artifacts found in {exp_dir}")
    return paths


def score_experiment(artifacts_dir: Path, experiment: str, baseline_name: str) -> dict:
    paths = discover_artifacts(artifacts_dir, experiment)
    if baseline_name not in paths:
        raise FileNotFoundError(
            f"{experiment} needs baseline artifact {baseline_name}.json for ratios"
        )

    artifacts = {name: load_json(path) for name, path in paths.items()}
    baseline = artifacts[baseline_name]
    baseline_avg = baseline["avg_completion_time_s"]
    baseline_throughput = baseline["throughput_jobs_per_s"]

    results = {}
    for method_name, artifact in sorted(artifacts.items()):
        values = {metric: artifact[metric] for metric in TRAIN_METRICS if metric in artifact}
        values["delay_reduction_x"] = baseline_avg / artifact["avg_completion_time_s"]
        values["throughput_improvement_x"] = (
            artifact["throughput_jobs_per_s"] / baseline_throughput
        )
        results[method_name] = values
    return {"slice": "train", "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=Path("scoring/scores_train.json"))
    args = parser.parse_args()

    scores = {
        "_slice": "train",
        "_metric_suite": "visible mean-latency, throughput, and completion metrics",
        "experiments": {},
    }
    for experiment, spec in EXPERIMENTS.items():
        scores["experiments"][experiment] = score_experiment(
            args.artifacts,
            experiment,
            spec["baseline"],
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
