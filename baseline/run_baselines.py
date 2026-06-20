"""Run baseline schedulers used for comparison with Continuum."""

from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workload", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--offload", action="store_true")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for policy in ["vllm", "plas", "infercept"]:
        cmd = [
            sys.executable,
            "method/continuum_sim.py",
            "--workload",
            str(args.workload),
            "--policy",
            policy,
            "--output",
            str(args.output_dir / f"{policy}.json"),
        ]
        if args.offload:
            cmd.append("--offload")
        subprocess.run(cmd, check=True)


if __name__ == "__main__":
    main()
