"""Held-out test-slice scorer for scheduler artifacts.

The test slice uses the train score file only to enumerate the exact methods
that were visible during development. It then scores held-out tail and
resource-constraint metrics from the same pre-generated method artifacts.
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
    "cache_hit_rate",
    "peak_pinned_memory_fraction",
    "expired_pin_fraction",
    "completed_fraction",
]


def load_json(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"missing artifact: {path}")
    return json.loads(path.read_text())


def train_methods(train_scores_path: Path) -> dict[str, list[str]]:
    payload = load_json(train_scores_path)
    experiments = payload.get("experiments", {})
    methods_by_experiment: dict[str, list[str]] = {}
    for experiment, exp_data in experiments.items():
        if experiment.startswith("_") or not isinstance(exp_data, dict):
            continue
        results = exp_data.get("results", exp_data)
        if not isinstance(results, dict):
            continue
        methods = sorted(
            name
            for name, values in results.items()
            if not name.startswith("_") and isinstance(values, dict)
        )
        if methods:
            methods_by_experiment[experiment] = methods
    if not methods_by_experiment:
        raise ValueError(f"no train-slice methods found in {train_scores_path}")
    return methods_by_experiment


def score_experiment(
    artifacts_dir: Path,
    experiment: str,
    baseline_name: str,
    methods: list[str],
) -> dict:
    exp_dir = artifacts_dir / experiment
    baseline_path = exp_dir / f"{baseline_name}.json"
    baseline = load_json(baseline_path)
    baseline_p90 = baseline["p90_completion_time_s"]

    results = {}
    for method_name in methods:
        artifact = load_json(exp_dir / f"{method_name}.json")
        values = {metric: artifact[metric] for metric in TEST_METRICS if metric in artifact}
        values["p90_delay_reduction_x"] = baseline_p90 / artifact["p90_completion_time_s"]
        results[method_name] = values
    return {"slice": "test", "results": results}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--artifacts", type=Path, default=Path("outputs"))
    parser.add_argument("--output", type=Path, default=Path("scoring/scores_test.json"))
    parser.add_argument(
        "--train-scores",
        type=Path,
        default=Path("scoring/scores_train.json"),
        help="Train-slice scores used only for method-key enumeration.",
    )
    args = parser.parse_args()

    methods_by_experiment = train_methods(args.train_scores)
    unknown = sorted(set(methods_by_experiment) - set(EXPERIMENTS))
    if unknown:
        raise ValueError(f"train scores contain unsupported experiments: {unknown}")

    scores = {
        "_slice": "test",
        "_metric_suite": "held-out tail-latency and cache/resource constraints",
        "experiments": {},
    }
    for experiment, methods in sorted(methods_by_experiment.items()):
        scores["experiments"][experiment] = score_experiment(
            args.artifacts,
            experiment,
            EXPERIMENTS[experiment]["baseline"],
            methods,
        )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(scores, indent=2, sort_keys=True) + "\n")


if __name__ == "__main__":
    main()
