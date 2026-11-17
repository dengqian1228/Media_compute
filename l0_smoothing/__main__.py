"""Command-line entry point for one image run or replay."""

import argparse
from pathlib import Path

from .workflow import replay_record, run_and_save


def main() -> int:
    parser = argparse.ArgumentParser(prog="python -m l0_smoothing")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="smooth one 8-bit L or RGB image")
    run.add_argument("input", type=Path, help="input image path")
    run.add_argument("--output-dir", type=Path, default=Path("results"))
    run.add_argument("--lambda", dest="lambda_", type=float, default=0.02)
    run.add_argument("--kappa", type=float, default=2.0)
    run.add_argument("--beta-max", type=float, default=1e5)

    replay = commands.add_parser("replay", help="rerun and compare a saved record")
    replay.add_argument("record", type=Path, help="path to run.json")
    replay.add_argument("--output-dir", type=Path)
    replay.add_argument("--input", type=Path, help="optional replacement input image")
    replay.add_argument("--float-atol", type=float, default=1e-12)

    args = parser.parse_args()
    try:
        if args.command == "run":
            record = run_and_save(
                args.input,
                args.output_dir,
                lambda_=args.lambda_,
                kappa=args.kappa,
                beta_max=args.beta_max,
            )
            print(record.resolve())
            return 0
        record, passed = replay_record(
            args.record,
            output_parent=args.output_dir,
            input_path=args.input,
            float_atol=args.float_atol,
        )
        print(record.resolve())
        if not passed:
            parser.exit(1, "replay output comparison failed; see the new run.json\n")
        return 0
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"error: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())
