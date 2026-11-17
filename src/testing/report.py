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