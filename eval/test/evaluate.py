"""Held-out test-slice scorer for scheduler artifacts.

This evaluator is intentionally method-agnostic: it discovers JSON artifacts
under outputs/<experiment>/ and scores held-out tail/resource metrics without
importing or executing method code.
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


TEST_METRICS = [
    "p90_completion_time_s",
    "p95_completion_time_s",
    "avg_queue_wait_s",
    "cache_hit_rate",
    "peak_pinned_memory_fraction",
    "expired_pin_fraction",
    "deadlock_unpins",
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


def score_experiment(
    artifacts_dir: Path,
    experiment: str,
    baseline_name: str,
) -> dict:
    paths = discover_artifacts(artifacts_dir, experiment)
    if baseline_name not in paths:
        raise FileNotFoundError(
            f"{experiment} needs baseline artifact {baseline_name}.json for ratios"
        )

    artifacts = {name: load_json(path) for name, path in paths.items()}
    baseline = artifacts[baseline_name]
    baseline_p90 = baseline["p90_completion_time_s"]
    baseline_p95 = baseline["p95_completion_time_s"]

    results = {}
    for method_name, artifact in sorted(artifacts.items()):
        values = {metric: artifact[metric] for metric in TEST_METRICS if metric in artifact}
        values["p90_delay_reduction_x"] = baseline_p90 / artifact["p90_completion_time_s"]
        values["p95_delay_reduction_x"] = baseline_p95 / artifact["p95_completion_time_s"]
        results[method_name] = values
    return {"slice": "test", "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=Path("scoring/scores_test.json"))
    args = parser.parse_args()

    scores = {
        "_slice": "test",
        "_metric_suite": "held-out tail-latency and cache/resource constraints",
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
    method_count = sum(
        len(experiment["results"]) for experiment in scores["experiments"].values()
    )
    value_count = sum(
        len(values)
        for experiment in scores["experiments"].values()
        for values in experiment["results"].values()
    )
    print(
        f"Wrote test scores to {args.output} "
        f"({len(scores['experiments'])} experiments, {method_count} methods, "
        f"{value_count} metric values)."
    )


if __name__ == "__main__":
    main()
