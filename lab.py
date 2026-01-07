from __future__ import annotations

import argparse
import sys
from typing import Any, Dict

from experiments import get_experiments


def parse_args(argv: list[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="AURA Lab experiment runner")
    parser.add_argument(
        "--experiment",
        "-e",
        default="experiment1",
        help="Experiment name (e.g., experiment1)",
    )
    parser.add_argument(
        "--runs",
        "-n",
        type=int,
        default=1,
        help="Number of runs to execute",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Base RNG seed (increments by run index)",
    )
    return parser.parse_args(argv)


def main(argv: list[str]) -> int:
    args = parse_args(argv)

    experiments = get_experiments()
    if args.experiment not in experiments:
        available = ", ".join(sorted(experiments.keys()))
        print(f"Unknown experiment: {args.experiment}. Available: {available}")
        return 2

    run_fn = experiments[args.experiment]

    for i in range(args.runs):
        seed = args.seed + i
        kwargs: Dict[str, Any] = {"seed": seed}
        run_fn(**kwargs)

    print(f"Completed {args.runs} run(s) of {args.experiment}.")
    print("Reports written under mission_logs/.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
