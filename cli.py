import argparse
import sys
from dataclasses import asdict

from src.testing.comparison import evaluate_run
from src.testing.plots import PLOT_TYPES, save_plots
from src.testing.report import (format_comparison, format_evaluation,
                                format_run_list, format_stats_table)
from src.testing.result_store import ResultStore
from src.testing.test_framework import AmmeterTestFramework
from src.utils.config import load_config


def cmd_run(args):
    framework = AmmeterTestFramework(args.config)
    if args.simulate_failures is not None:
        # Switch failure simulation on for this run only; config.yaml is not changed.
        simulation = framework.config["testing"].get("simulation") or {}
        simulation.update(enabled=True, failure_rate=args.simulate_failures)
        if args.seed is not None:
            simulation["seed"] = args.seed
        framework.config["testing"]["simulation"] = simulation
    outcome = framework.run(ammeters=args.ammeters, count=args.count,
                            duration=args.duration, frequency=args.frequency,
                            save=not args.no_save, notes=args.notes)
    stats = {name: asdict(r["stats"]) for name, r in outcome["results"].items()}
    print("\n" + format_stats_table(stats))
    first = next(iter(outcome["results"].values()))
    if first["settings"].get("simulation"):
        print("\nNote: failure simulation was ON for this run; failed readings are intentional.")
    if outcome["run_id"]:
        print(f"\nSaved as run {outcome['run_id']}")
    print(f"Log file: {outcome['log_file']}")


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


def cmd_evaluate(args, store):
    run = store.load_run(args.run_id)
    # A failed reading is stored with value None; evaluate_run counts those
    # as failures (success rate) and keeps them out of the statistics.
    readings = {name: [m["value"] for m in data["measurements"]]
                for name, data in run["ammeters"].items()}
    print(f"Run {run['run_id']}\n")
    print(format_evaluation(evaluate_run(readings, args.reference), args.reference))


def cmd_plot(args, store):
    config = load_config(args.config)
    visualization = (config.get("analysis") or {}).get("visualization") or {}
    if not visualization.get("enabled", True):
        raise ValueError("Charts are switched off (analysis.visualization.enabled "
                         "in config.yaml)")
    types = args.types or visualization.get("plot_types") or list(PLOT_TYPES)
    directory = visualization.get("directory", "results/plots")
    paths, skipped = save_plots(store.load_run(args.run_id), directory, types)
    for path in paths:
        print(f"Saved {path}")
    for plot_type, reason in skipped:
        print(f"Skipped '{plot_type}': {reason}")


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
    run.add_argument("--simulate-failures", type=float, metavar="RATE",
                     help="make readings fail on purpose with this probability (0 to 1)")
    run.add_argument("--seed", type=int,
                     help="repeat the same simulated failures (use with --simulate-failures)")
    run.set_defaults(func=cmd_run)

    sub.add_parser("list", help="list saved runs").set_defaults(func=cmd_list)
    show = sub.add_parser("show", help="show one saved run")
    show.add_argument("run_id")
    show.set_defaults(func=cmd_show)
    compare = sub.add_parser("compare", help="compare two saved runs")
    compare.add_argument("run_a")
    compare.add_argument("run_b")
    compare.set_defaults(func=cmd_compare)

    evaluate = sub.add_parser("evaluate", help="rank the ammeters of a saved run")
    evaluate.add_argument("run_id")
    evaluate.add_argument("--reference", type=float,
                          help="known true current in amperes (enables an accuracy check)")
    evaluate.set_defaults(func=cmd_evaluate)

    plot = sub.add_parser("plot", help="draw charts of a saved run (needs matplotlib)")
    plot.add_argument("run_id")
    plot.add_argument("--types", nargs="+", choices=PLOT_TYPES,
                      help="which charts to draw (default: plot_types in config.yaml)")
    plot.set_defaults(func=cmd_plot)
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