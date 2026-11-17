import statistics
from dataclasses import dataclass, field
from typing import Dict, List, Optional

from src.testing.ammeter_client import Measurement


@dataclass
class Stats:
    """Summary of one ammeter's test run."""
    ammeter: str
    total: int                       # readings attempted
    valid: int                       # readings that returned a number
    failed: int                      # readings that failed
    mean: Optional[float]
    median: Optional[float]
    std_dev: Optional[float]         # None if fewer than 2 valid readings
    minimum: Optional[float]
    maximum: Optional[float]
    cv_percent: Optional[float]      # coefficient of variation: std_dev / mean x 100
    errors: Dict[str, int] = field(default_factory=dict)   # failure reason -> count


def analyze(measurements: List[Measurement]) -> Stats:
    """Compute statistics for the readings of ONE ammeter."""
    if not measurements:
        raise ValueError("No measurements to analyze")
    names = {m.ammeter for m in measurements}
    if len(names) > 1:
        raise ValueError(f"analyze() expects one ammeter, got: {sorted(names)}")

    # Failed readings are counted and explained, but kept out of the statistics:
    # treating a failure as 0 A would pull the mean down and make the ammeter
    # look less accurate than it is.
    values = [m.value for m in measurements if m.ok]
    errors: Dict[str, int] = {}
    for m in measurements:
        if not m.ok:
            errors[m.error] = errors.get(m.error, 0) + 1

    mean = median = std_dev = minimum = maximum = cv = None
    if values:
        mean = statistics.mean(values)
        median = statistics.median(values)
        minimum, maximum = min(values), max(values)
    if len(values) >= 2:
        # Sample standard deviation (n-1): the readings are a sample of how the
        # ammeter behaves, not the complete set of all possible readings.
        std_dev = statistics.stdev(values)
    if std_dev is not None and mean:   # mean must not be 0 or None
        # Spread relative to the size of the readings. This makes ammeters with
        # very different ranges (0.01 A vs 100 A) comparable with each other.
        cv = std_dev / abs(mean) * 100

    return Stats(
        ammeter=measurements[0].ammeter,
        total=len(measurements), valid=len(values), failed=len(measurements) - len(values),
        mean=mean, median=median, std_dev=std_dev,
        minimum=minimum, maximum=maximum, cv_percent=cv, errors=errors,
    )