from typing import Dict, List


def _num(value, digits: int = 4) -> str:
    """Format a number compactly; '-' means 'not available'."""
    return "-" if value is None else f"{value:.{digits}g}"


def _table(headers: List[str], rows: List[List[str]]) -> str:
    # Column width = the longest text in that column, so everything lines up.
    widths = [max([len(h)] + [len(r[i]) for r in rows]) for i, h in enumerate(headers)]
    line = "  ".join("-" * w for w in widths)
    out = ["  ".join(h.ljust(w) for h, w in zip(headers, widths)), line]
    out += ["  ".join(c.ljust(w) for c, w in zip(r, widths)) for r in rows]
    return "\n".join(out)


def format_stats_table(stats_by_ammeter: Dict[str, dict]) -> str:
    """One row per ammeter. Takes plain dicts, so it works both for a fresh
    run and for a run loaded from a saved JSON file."""
    headers = ["Ammeter", "Valid", "Mean (A)", "Median (A)", "Std dev (A)",
               "Min (A)", "Max (A)", "CV (%)"]
    rows = [[name, f"{s['valid']}/{s['total']}", _num(s["mean"]), _num(s["median"]),
             _num(s["std_dev"]), _num(s["minimum"]), _num(s["maximum"]),
             _num(s["cv_percent"], 3)]
            for name, s in stats_by_ammeter.items()]
    text = _table(headers, rows)

    # Failures are never hidden: show which ammeter failed and why.
    problems = [f"  {name}: {count} x {reason}"
                for name, s in stats_by_ammeter.items()
                for reason, count in s["errors"].items()]
    if problems:
        text += "\n\nFailed readings (excluded from the statistics):\n" + "\n".join(problems)
    return text


def format_run_list(runs: List[dict]) -> str:
    if not runs:
        return "No saved runs yet."
    rows = [[r["run_id"], r["created_at"],
             ", ".join(f"{n}={_num(m)}" for n, m in r["ammeters"].items())]
            for r in runs]
    return _table(["Run id", "Created", "Mean current (A)"], rows)


def format_comparison(comparison: dict, run_a: str, run_b: str) -> str:
    out = [f"A = {run_a}", f"B = {run_b}"]
    for name, metrics in comparison.items():
        rows = [[metric, _num(v["a"]), _num(v["b"]),
                 "-" if v["change_percent"] is None else f"{v['change_percent']:+.1f}%"]
                for metric, v in metrics.items()]
        out.append(f"\n{name}\n" + _table(["Metric", "A", "B", "Change"], rows))
    return "\n".join(out)


def format_evaluation(ranking: list, reference=None) -> str:
    headers = ["Rank", "Ammeter", "Success", "Median (A)", "CV (%)",
               "Robust CV (%)", "Std error (%)"]
    if reference is not None:
        headers.append("Error vs ref (%)")

    rows = []
    for position, e in enumerate(ranking, start=1):
        row = [str(position) if e.ranked else "-", e.ammeter, f"{e.success_rate:.0f}%",
               _num(e.median), _num(e.cv_percent, 3), _num(e.robust_cv_percent, 3),
               _num(e.sem_percent, 3)]
        if reference is not None:
            row.append(_num(e.reference_error_percent, 3))
        rows.append(row)
    out = [_table(headers, rows)]

    ranked = [e for e in ranking if e.ranked]
    out.append("")
    if ranked:
        best = ranked[0]
        out.append(f"Most reliable: {best.ammeter} "
                   f"(success {best.success_rate:.0f}%, CV {_num(best.cv_percent, 3)}%)")
    else:
        out.append("No ammeter has enough valid readings to be ranked.")
    if reference is not None and ranked:
        closest = min(ranked, key=lambda e: e.reference_error_percent
                      if e.reference_error_percent is not None else float("inf"))
        out.append(f"Closest to the reference {reference} A (by median): "
                   f"{closest.ammeter} (error {_num(closest.reference_error_percent, 3)}%)")

    out.append("")
    unranked = [e.ammeter for e in ranking if not e.ranked]
    if unranked:
        out.append(f"Not ranked (fewer than 3 valid readings): {', '.join(unranked)}")
    if min(e.total for e in ranking) < 30:
        out.append("Note: fewer than 30 readings per ammeter; spread statistics are "
                   "noisy, use more readings for a firm conclusion.")
    if reference is None:
        out.append("Note: no reference value given, so this compares precision "
                   "(consistency) only, not accuracy.")
    out.append("CV = std dev / mean. Robust CV = same, using the median absolute "
               "deviation (ignores extreme readings). Std error = CV / sqrt(n).")
    return "\n".join(out)