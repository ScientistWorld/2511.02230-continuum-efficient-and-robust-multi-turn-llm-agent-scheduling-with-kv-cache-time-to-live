"""Synthetic agent-serving workloads matching the paper's published statistics.

The paper's exact SWE-Bench and BFCL traces were not bundled with the
workspace.  This module creates deterministic, non-trivial ReAct-style traces
from the reported means/standard deviations in Table 1, so schedulers can be
compared on the same multi-turn, long-tailed tool-call problem.
"""

from __future__ import annotations

import argparse
import json
import math
import random
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True)
class Turn:
    turn_index: int
    context_tokens: int
    mem: float
    prefill_s: float
    reload_s: float
    decode_s: float
    tool_name: str | None
    tool_time_s: float


@dataclass(frozen=True)
class Program:
    program_id: str
    dataset: str
    arrival_s: float
    turns: list[Turn]


DATASET_STATS = {
    "swebench": {
        "turn_mean": 10.9,
        "turn_sd": 2.1,
        "tool_mean_s": 0.925,
        "tool_sd_s": 3.550,
        "tokens_mean": 70126,
        "tokens_sd": 19732,
        "tools": ["bash", "pytest", "sed", "grep", "python", "git", "ls", "cat"],
    },
    "bfcl": {
        "turn_mean": 6.3,
        "turn_sd": 2.3,
        "tool_mean_s": 1.923,
        "tool_sd_s": 2.133,
        "tokens_mean": 93256,
        "tokens_sd": 68687,
        "tools": ["fetch_url", "search", "open", "click", "extract", "answer"],
    },
}


def _lognormal_params(mean: float, sd: float) -> tuple[float, float]:
    variance = sd * sd
    sigma2 = math.log(1.0 + variance / (mean * mean))
    return math.log(mean) - 0.5 * sigma2, math.sqrt(sigma2)


def _positive_normal(rng: random.Random, mean: float, sd: float, lo: int) -> int:
    for _ in range(100):
        value = int(round(rng.gauss(mean, sd)))
        if value >= lo:
            return value
    return lo


def generate_workload(
    dataset: str,
    *,
    programs: int,
    arrival_rate: float,
    seed: int,
    turn_multiplier: int = 1,
) -> list[Program]:
    stats = DATASET_STATS[dataset]
    rng = random.Random(seed)
    tool_mu, tool_sigma = _lognormal_params(stats["tool_mean_s"], stats["tool_sd_s"])
    arrival = 0.0
    result: list[Program] = []
    for pid in range(programs):
        arrival += rng.expovariate(arrival_rate)
        base_turns = _positive_normal(rng, stats["turn_mean"], stats["turn_sd"], 2)
        n_turns = max(2, base_turns * turn_multiplier)
        total_tokens = _positive_normal(rng, stats["tokens_mean"], stats["tokens_sd"], 8192)
        turns: list[Turn] = []
        for idx in range(n_turns):
            progress = (idx + 1) / n_turns
            context = max(512, int(total_tokens * progress / turn_multiplier))
            mem = 0.35 + 1.65 * context / 128000.0
            prefill = 0.18 + 0.000020 * context + 1.8e-10 * context * context
            reload = 0.08 + 0.000006 * context
            decode = 0.45 + 0.000003 * max(256, context) + rng.uniform(0.0, 0.20)
            if idx + 1 == n_turns:
                tool_name = None
                tool_time = 0.0
            else:
                tool_name = rng.choice(stats["tools"])
                tool_time = min(45.0, rng.lognormvariate(tool_mu, tool_sigma))
            turns.append(
                Turn(
                    turn_index=idx,
                    context_tokens=context,
                    mem=mem,
                    prefill_s=prefill,
                    reload_s=reload,
                    decode_s=decode,
                    tool_name=tool_name,
                    tool_time_s=tool_time,
                )
            )
        result.append(Program(f"{dataset}-{pid:04d}", dataset, arrival, turns))
    return result


def write_workload(path: Path, programs: list[Program], config: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    clean_config = {key: str(value) if isinstance(value, Path) else value for key, value in config.items()}
    payload = {"config": clean_config, "programs": [asdict(p) for p in programs]}
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n")


def load_workload(path: Path) -> list[Program]:
    payload = json.loads(path.read_text())
    programs = []
    for p in payload["programs"]:
        turns = [Turn(**t) for t in p["turns"]]
        programs.append(Program(p["program_id"], p["dataset"], p["arrival_s"], turns))
    return programs


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset", choices=sorted(DATASET_STATS), required=True)
    parser.add_argument("--programs", type=int, default=120)
    parser.add_argument("--arrival-rate", type=float, default=0.13)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--turn-multiplier", type=int, default=1)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    programs = generate_workload(
        args.dataset,
        programs=args.programs,
        arrival_rate=args.arrival_rate,
        seed=args.seed,
        turn_multiplier=args.turn_multiplier,
    )
    write_workload(args.output, programs, vars(args))


if __name__ == "__main__":
    main()
