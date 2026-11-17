import time
from typing import List, Optional, Tuple

from src.testing.ammeter_client import AmmeterClient, Measurement


def resolve_sampling_plan(count: Optional[int] = None,
                          duration: Optional[float] = None,
                          frequency: Optional[float] = None) -> Tuple[int, float]:
    """Turn the three sampling settings into (number of samples, seconds between samples).

    The settings depend on each other (count = duration x frequency), so any two
    of them are enough. If all three are given, they must agree.
    """
    given = [v for v in (count, duration, frequency) if v is not None]
    if len(given) < 2:
        raise ValueError("Give at least two of: count, duration, frequency")
    if any(v <= 0 for v in given):
        raise ValueError("count, duration and frequency must be positive")

    if frequency is not None:
        interval = 1.0 / frequency
        if count is None:
            # Small epsilon avoids 2.9999999 being rounded down to 2 by float error.
            count = int(duration * frequency + 1e-9)
        elif duration is not None and count != int(duration * frequency + 1e-9):
            raise ValueError(
                f"Inconsistent settings: {duration}s at {frequency} Hz gives "
                f"{int(duration * frequency + 1e-9)} samples, not {count}")
    else:
        # Only count and duration were given: spread the samples over the duration.
        interval = duration / count

    count = int(count)
    if count < 1:
        raise ValueError("Settings produce less than one sample")
    return count, interval


def collect_samples(client: AmmeterClient, count: int, interval: float) -> List[Measurement]:
    """Take `count` readings, one every `interval` seconds."""
    results = []
    start = time.perf_counter()  # monotonic clock: not affected by system clock changes
    for i in range(count):
        # Schedule each reading against the START time (start + i x interval).
        # If we instead slept `interval` after every reading, the time spent
        # measuring would add up and the test would drift later and later.
        delay = start + i * interval - time.perf_counter()
        if delay > 0:
            time.sleep(delay)
        # If we are already late (e.g. the previous reading timed out), we
        # measure immediately and the schedule catches up on its own.
        results.append(client.measure())
    return results


def run_sampling(client: AmmeterClient, count: Optional[int] = None,
                 duration: Optional[float] = None,
                 frequency: Optional[float] = None) -> List[Measurement]:
    """Convenience wrapper: resolve the settings, then collect the samples."""
    count, interval = resolve_sampling_plan(count, duration, frequency)
    return collect_samples(client, count, interval)