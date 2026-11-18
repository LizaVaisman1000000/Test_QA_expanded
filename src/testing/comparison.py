import math
import statistics
from dataclasses import dataclass
from typing import Dict, List, Optional

# Below this many valid readings, spread statistics mean too little to rank on.
MIN_VALID_READINGS = 3

# Scales the median absolute deviation (MAD) so it is comparable to a standard
# deviation for normally distributed data.
MAD_TO_STD = 1.4826


@dataclass
class Evaluation:
    ammeter: str
    total: int
    valid: int
    success_rate: float                      # percent of readings that succeeded
    median: Optional[float]
    cv_percent: Optional[float]              # std dev / mean x 100
    robust_cv_percent: Optional[float]       # 1.4826 x MAD / median x 100
    sem_percent: Optional[float]             # standard error of the mean, in % of the mean
    reference_error_percent: Optional[float]  # |median - reference| / reference x 100
    ranked: bool                             # False when there are too few valid readings


def evaluate_ammeter(name: str, readings: List[Optional[float]],
                     reference: Optional[float] = None) -> Evaluation:
    """Evaluate one ammeter. `readings` holds None for each failed reading."""
    total = len(readings)
    values = [v for v in readings if v is not None]
    valid = len(values)
    success_rate = valid / total * 100 if total else 0.0

    median = statistics.median(values) if values else None
    mean = statistics.mean(values) if values else None
    cv = robust_cv = sem = reference_error = None

    if valid >= 2 and mean:
        cv = statistics.stdev(values) / abs(mean) * 100
        # Standard error: how precisely the MEAN is known. It shrinks as 1/sqrt(n),
        # so more readings give a more trustworthy average.
        sem = cv / math.sqrt(valid)
    if valid >= 2 and median:
        mad = statistics.median([abs(v - median) for v in values])
        # Same idea as CV, but built on the median, so a few extreme readings
        # do not dominate it. A CV far above the robust CV reveals such outliers.
        robust_cv = MAD_TO_STD * mad / abs(median) * 100
    if reference is not None and median is not None:
        # The median, not the mean, estimates the ammeter's typical value:
        # one extreme reading cannot pull it far.
        reference_error = abs(median - reference) / abs(reference) * 100

    return Evaluation(name, total, valid, success_rate, median, cv, robust_cv, sem,
                      reference_error, ranked=valid >= MIN_VALID_READINGS)


def evaluate_run(readings: Dict[str, List[Optional[float]]],
                 reference: Optional[float] = None) -> List[Evaluation]:
    """Evaluate every ammeter and return them best first.

    Order: ammeters with enough valid readings first. Among those, a higher
    success rate wins (a device that drops readings is less reliable), then a
    lower coefficient of variation (more consistent).
    """
    if len(readings) < 2:
        raise ValueError("Need at least two ammeters to compare")
    if reference is not None and reference == 0:
        raise ValueError("The reference value must not be 0")

    evaluations = [evaluate_ammeter(name, values, reference)
                   for name, values in readings.items()]

    def sort_key(e: Evaluation):
        if not e.ranked:
            return (1, 0, 0)
        return (0, -e.success_rate,
                e.cv_percent if e.cv_percent is not None else float("inf"))

    return sorted(evaluations, key=sort_key)