import random
import time

# What each failure looks like to the client:
#   timeout  - the reply comes too late, so the client's timeout expires
#   garbage  - the reply is not a number
#   no_reply - the connection closes without any reply
FAILURE_TYPES = ("timeout", "garbage", "no_reply")


def make_faulty(emulator_class, failure_rate: float, failure_types=FAILURE_TYPES,
                delay_seconds: float = 3.0, seed=None):
    """Return a version of `emulator_class` that fails on purpose.

    failure_rate:  probability (0 to 1) that one reading fails.
    delay_seconds: how late a "timeout" reply is; must be longer than the
                   client's timeout, or the client would still receive it.
    seed:          makes the failure pattern reproducible (same seed, same pattern).
    """
    if not 0 <= failure_rate <= 1:
        raise ValueError("failure_rate must be between 0 and 1")
    failure_types = list(failure_types)
    unknown = [t for t in failure_types if t not in FAILURE_TYPES]
    if unknown or not failure_types:
        raise ValueError(f"failure_types must be a non-empty subset of {FAILURE_TYPES}; "
                         f"got {failure_types}")
    if delay_seconds <= 0:
        raise ValueError("delay_seconds must be positive")

    # Own random generator: the emulators reseed the global one with the clock,
    # which would make a seeded pattern impossible to reproduce.
    rng = random.Random(seed)

    class FaultyEmulator(emulator_class):
        def send_reply(self, conn, current):
            if rng.random() >= failure_rate:
                return super().send_reply(conn, current)   # healthy reading
            failure = rng.choice(failure_types)
            print(f"[simulated failure: {failure}]")
            if failure == "timeout":
                time.sleep(delay_seconds)
                super().send_reply(conn, current)          # arrives too late
            elif failure == "garbage":
                conn.sendall(b"ERR#?")
            # "no_reply": send nothing; the connection closes when the handler ends

    FaultyEmulator.__name__ = f"Faulty{emulator_class.__name__}"
    return FaultyEmulator