import argparse
import sys
from dataclasses import asdict

from src.testing.report import format_comparison, format_run_list, format_stats_table
from src.testing.result_store import ResultStore
from src.testing.test_framework import AmmeterTestFramework
from src.utils.config import load_config


def cmd_run(args):
    framework = AmmeterTestFramework(args.config)
    outcome = framework.run(ammeters=args.ammeters, count=args.count,
                            duration=args.duration, frequency=args.frequency,
                            save=not args.no_save, notes=args.notes)
    stats = {name: asdict(r["stats"]) for name, r in outcome["results"].items()}
    print("\n" + format_stats_table(stats))
    if outcome["run_id"]:
        print(f"\nSaved as run {outcome['run_id']}")


def cmd_list(args, store):
    print(format_run_list(store.list_runs()))


def cmd_show(args, store):
    run = store.load_run(args.run_id)
    print(f"Run {run['run_id']}  ({run['created_at']})")
    if run["metadata"]["notes"]:
        print(f"Notes: {run['metadata']['notes']}")
    print(f"Settings: {run['settings']}\n")
    print(format_stats_table({n: d["stats"] for n, d in run["ammeters"].items()}))


def cmd_compare(args, store):
    print(format_comparison(store.compare_runs(args.run_a, args.run_b),
                            args.run_a, args.run_b))


def build_parser():
    parser = argparse.ArgumentParser(description="Ammeter testing framework")
    parser.add_argument("--config", default="config/config.yaml", help="path to config file")
    sub = parser.add_subparsers(dest="command", required=True)

    run = sub.add_parser("run", help="run a test and save the result")
    run.add_argument("--ammeters", nargs="+", help="names from config.yaml (default: all)")
    run.add_argument("--count", type=int, help="number of measurements")
    run.add_argument("--duration", type=float, help="total duration in seconds")
    run.add_argument("--frequency", type=float, help="measurements per second (Hz)")
    run.add_argument("--notes", default="", help="free text saved with the run")
    run.add_argument("--no-save", action="store_true", help="do not save the result")
    run.set_defaults(func=cmd_run)

    sub.add_parser("list", help="list saved runs").set_defaults(func=cmd_list)
    show = sub.add_parser("show", help="show one saved run")
    show.add_argument("run_id")
    show.set_defaults(func=cmd_show)
    compare = sub.add_parser("compare", help="compare two saved runs")
    compare.add_argument("run_a")
    compare.add_argument("run_b")
    compare.set_defaults(func=cmd_compare)
    return parser


def main():
    args = build_parser().parse_args()
    try:
        if args.command == "run":
            args.func(args)
        else:
            args.func(args, ResultStore.from_config(load_config(args.config)))
    except (ValueError, RuntimeError, OSError) as e:
        # Expected problems (bad settings, unknown run id, missing file) get a
        # short readable message instead of a Python traceback.
        print(f"Error: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())