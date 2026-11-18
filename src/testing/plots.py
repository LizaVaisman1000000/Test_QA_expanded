import os
from typing import Dict, List, Tuple

from src.testing.comparison import evaluate_run

PLOT_TYPES = ("readings", "spread", "consistency")


def _pyplot():
    """Import matplotlib only when a chart is requested, so the rest of the
    framework (tests, reports, saved runs) works without it installed."""
    try:
        import matplotlib
        matplotlib.use("Agg")   # draw into image files: no window, same on every OS
        import matplotlib.pyplot as plt
    except ImportError:
        raise RuntimeError(
            "Charts need matplotlib. Install it with: pip install matplotlib") from None
    return plt


def _plot_readings(plt, run: dict):
    """Every reading over time, one chart per ammeter (their ranges differ by
    factors of thousands, so they cannot share one axis)."""
    names = list(run["ammeters"])
    fig, axes = plt.subplots(len(names), 1, figsize=(9, 2.8 * len(names)), squeeze=False)
    for ax, name in zip(axes[:, 0], names):
        data = run["ammeters"][name]
        measurements = data["measurements"]
        positions = list(range(1, len(measurements) + 1))
        # A failed reading becomes NaN: matplotlib leaves a gap in the line there.
        # Drawing a line across a failure would suggest values that were never measured.
        values = [m["value"] if m["value"] is not None else float("nan")
                  for m in measurements]
        failed = [i for i, m in zip(positions, measurements) if m["value"] is None]
        if len(failed) < len(measurements):
            ax.plot(positions, values, marker="o", linewidth=1, label="reading")
            median = data["stats"]["median"]
            ax.axhline(median, linestyle="--", linewidth=1, color="gray",
                       label=f"median {median:.4g} A")
        if failed:
            # A failed reading has no value, so its position is marked along the
            # bottom edge of the chart (y is in axes coordinates, 0 to 1).
            ax.plot(failed, [0.04] * len(failed), linestyle="none", marker="x",
                    color="red", markersize=9, transform=ax.get_xaxis_transform(),
                    label=f"failed ({len(failed)})")
        ax.set_xlim(0.5, len(measurements) + 0.5)
        ax.set_title(name, loc="left", fontsize=10)
        ax.set_ylabel("Current (A)")
        # Legend outside the chart, so it can never cover a reading.
        ax.legend(loc="center left", bbox_to_anchor=(1.01, 0.5), fontsize=8)
    axes[-1, 0].set_xlabel("Reading number")
    fig.suptitle(f"Readings of run {run['run_id']}")
    return fig


def _plot_spread(plt, run: dict):
    """Box plot of the valid readings: box = middle half of the readings, line =
    median, triangle = mean, circles = outliers."""
    series = {name: [m["value"] for m in data["measurements"] if m["value"] is not None]
              for name, data in run["ammeters"].items()}
    series = {name: values for name, values in series.items() if values}
    if not series:
        raise ValueError("no valid readings to plot")
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.boxplot(list(series.values()), showmeans=True)
    ax.set_xticks(range(1, len(series) + 1), list(series))
    if all(v > 0 for values in series.values() for v in values):
        # Currents here range from about 0.01 A to 100 A; on a linear axis the
        # small ammeters would be flat lines at the bottom.
        ax.set_yscale("log")
        ax.set_ylabel("Current (A, logarithmic scale)")
    else:
        ax.set_ylabel("Current (A)")
    # Caption: the chart should be readable without the code next to it.
    ax.set_xlabel("box = middle 50% of readings, orange line = median, "
                  "triangle = mean, circles = outliers", fontsize=8)
    ax.set_title(f"Spread of valid readings, run {run['run_id']}", fontsize=10)
    return fig


def _plot_consistency(plt, run: dict):
    """CV and robust CV per ammeter, best first (lower is better). The two bars
    differ a lot when a few extreme readings dominate."""
    readings = {name: [m["value"] for m in data["measurements"]]
                for name, data in run["ammeters"].items()}
    ranking = evaluate_run(readings)   # ValueError when fewer than 2 ammeters
    positions = list(range(len(ranking)))
    width = 0.38
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.bar([p - width / 2 for p in positions],
           [e.cv_percent or 0 for e in ranking], width, label="CV (%)")
    ax.bar([p + width / 2 for p in positions],
           [e.robust_cv_percent or 0 for e in ranking], width, label="Robust CV (%)")
    for p, e in zip(positions, ranking):
        if e.cv_percent is None:
            ax.text(p, 0, "n/a", ha="center", va="bottom")   # too few readings
    ax.set_xticks(positions, [f"{e.ammeter}\nsuccess {e.success_rate:.0f}%" for e in ranking])
    ax.set_ylabel("Coefficient of variation (%)")
    ax.set_title(f"Consistency, best first (lower is better), run {run['run_id']}", fontsize=10)
    ax.legend()
    return fig


_PAINTERS = {"readings": _plot_readings, "spread": _plot_spread,
             "consistency": _plot_consistency}


def save_plots(run: dict, directory: str,
               plot_types=PLOT_TYPES) -> Tuple[List[str], List[Tuple[str, str]]]:
    """Draw the requested charts of a saved run into `directory` as PNG files.

    Returns (paths of the saved files, [(chart type, reason it was skipped)]).
    A chart that cannot be drawn is skipped, so one problem does not lose the others.
    """
    unknown = [t for t in plot_types if t not in PLOT_TYPES]
    if unknown:
        raise ValueError(f"Unknown chart type {unknown}. Available: {', '.join(PLOT_TYPES)}")
    plt = _pyplot()
    os.makedirs(directory, exist_ok=True)

    paths, skipped = [], []
    for plot_type in plot_types:
        try:
            fig = _PAINTERS[plot_type](plt, run)
        except ValueError as e:
            skipped.append((plot_type, str(e)))
            continue
        path = os.path.join(directory, f"{run['run_id']}_{plot_type}.png")
        fig.tight_layout()
        fig.savefig(path, dpi=120, bbox_inches="tight")   # "tight" keeps the outside legend in the image
        plt.close(fig)   # free the memory of the finished chart
        paths.append(path)
    return paths, skipped