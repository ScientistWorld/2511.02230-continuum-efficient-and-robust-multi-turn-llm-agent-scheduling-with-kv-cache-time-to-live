"""Evaluate scheduler artifacts without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPERIMENTS = {
    "swebench_scaled_no_offload": {
        "baseline": "vllm",
        "primary_metric": "avg_completion_time_s",
    },
    "bfcl_scaled_no_offload": {
        "baseline": "vllm",
        "primary_metric": "avg_completion_time_s",
    },
    "swebench_scaled_offload": {
        "baseline": "vllm",
        "primary_metric": "avg_completion_time_s",
    },
    "turn_robustness_scaled": {
        "baseline": "vllm",
        "primary_metric": "avg_completion_time_s",
    },
    "ablation_scaled": {
        "baseline": "plas",
        "primary_metric": "avg_completion_time_s",
    },
}


METRICS = [
    "avg_completion_time_s",
    "p90_completion_time_s",
    "p95_completion_time_s",
    "avg_queue_wait_s",
    "throughput_jobs_per_s",
    "cache_hit_rate",
    "completed_fraction",
    "peak_pinned_memory_fraction",
    "expired_pin_fraction",
    "deadlock_unpins",
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


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=Path("scoring/scores.json"))
    args = parser.parse_args()
    scores = {"experiments": {}}
    for exp_name, spec in EXPERIMENTS.items():
        paths = discover_artifacts(args.artifacts, exp_name)
        baseline_name = spec["baseline"]
        if baseline_name not in paths:
            raise FileNotFoundError(
                f"{exp_name} needs baseline artifact {baseline_name}.json for ratios"
            )
        artifacts = {name: load_json(path) for name, path in paths.items()}
        baseline = artifacts[baseline_name]
        exp_results = {}
        for policy, artifact in sorted(artifacts.items()):
            values = {metric: artifact[metric] for metric in METRICS if metric in artifact}
            values["delay_reduction_x"] = baseline["avg_completion_time_s"] / artifact["avg_completion_time_s"]
            values["p90_delay_reduction_x"] = baseline["p90_completion_time_s"] / artifact["p90_completion_time_s"]
            values["p95_delay_reduction_x"] = baseline["p95_completion_time_s"] / artifact["p95_completion_time_s"]
            values["throughput_improvement_x"] = artifact["throughput_jobs_per_s"] / baseline["throughput_jobs_per_s"]
            exp_results[policy] = values
        scores["experiments"][exp_name] = {"results": exp_results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
