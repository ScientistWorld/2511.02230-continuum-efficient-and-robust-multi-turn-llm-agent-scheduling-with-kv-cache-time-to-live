"""Evaluate scheduler artifacts without importing method code."""

from __future__ import annotations

import argparse
import json
from pathlib import Path


EXPERIMENTS = {
    "swebench_scaled_no_offload": {
        "policies": ["vllm", "continuum"],
        "primary_metric": "avg_completion_time_s",
    },
    "bfcl_scaled_no_offload": {
        "policies": ["vllm", "continuum"],
        "primary_metric": "avg_completion_time_s",
    },
    "swebench_scaled_offload": {
        "policies": ["vllm", "infercept", "continuum"],
        "primary_metric": "avg_completion_time_s",
    },
    "turn_robustness_scaled": {
        "policies": ["vllm", "continuum"],
        "primary_metric": "avg_completion_time_s",
    },
    "ablation_scaled": {
        "policies": ["plas", "static_ttl", "continuum"],
        "primary_metric": "avg_completion_time_s",
    },
}


METRICS = [
    "avg_completion_time_s",
    "p90_completion_time_s",
    "throughput_jobs_per_s",
    "cache_hit_rate",
    "completed_fraction",
    "peak_pinned_memory_fraction",
    "expired_pin_fraction",
]


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing artifact: {path}")
    return json.loads(path.read_text())


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=Path("scoring/scores.json"))
    args = parser.parse_args()
    scores = {"experiments": {}}
    for exp_name, spec in EXPERIMENTS.items():
        artifacts = {
            policy: load_json(args.artifacts / exp_name / f"{policy}.json")
            for policy in spec["policies"]
        }
        baseline = artifacts["vllm"] if "vllm" in artifacts else artifacts[spec["policies"][0]]
        exp_results = {}
        for policy, artifact in artifacts.items():
            values = {metric: artifact[metric] for metric in METRICS if metric in artifact}
            values["delay_reduction_x"] = baseline["avg_completion_time_s"] / artifact["avg_completion_time_s"]
            values["p90_delay_reduction_x"] = baseline["p90_completion_time_s"] / artifact["p90_completion_time_s"]
            values["throughput_improvement_x"] = artifact["throughput_jobs_per_s"] / baseline["throughput_jobs_per_s"]
            exp_results[policy] = values
        scores["experiments"][exp_name] = {"results": exp_results}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
