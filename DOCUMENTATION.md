# Design Documentation

## Environment
- Python 3.13 (virtual environment in `venv/`, not committed)
- Libraries installed (see `requirements.txt`):
  - PyYAML 6.0.3: required by the provided `src/utils/config.py` to read `config/config.yaml`
- Note: Python 3.15 was tried first, but PyYAML has no prebuilt package for it yet and
  could not be compiled without a C compiler, so the environment was rebuilt on Python 3.13.

## Design decisions

### Unified measurement interface (`src/testing/ammeter_client.py`)
- One configurable `AmmeterClient` class instead of one subclass per brand. The ammeters differ only in port and command, so both come from `config/config.yaml`. Adding an ammeter means adding a config block, with no new code.
- Every reading is returned as a `Measurement` object (ammeter, timestamp, value, error), so results look the same for every brand.
- `measure()` never raises. A failed reading (timeout, refused connection, unknown command, non-numeric reply) is returned with `value=None` and the reason in `error`, so one bad reading cannot stop a long test.
- Note: on Windows, a request to a port with nothing listening ends as a timeout and not as "connection refused" (Windows keeps retrying for about 2 seconds); Linux/macOS report "refused" immediately.

## Bugs found and fixed

| # | File | Problem | Fix | Why |
|---|------|---------|-----|-----|
| 1 | main.py | Ports 5001-5003 used instead of README ports 5000-5002 | Changed to 5000, 5001, 5002 | Match the documented configuration |
| 2 | main.py | Truncated commands (e.g. `MEASURE_GREENLEE`) | Use full commands from README | The emulator compares the request to its command exactly and silently ignores anything else |
| 3 | main.py | Request lines were commented out | Re-enabled them | Otherwise nothing is requested or printed |
| 4 | Circutor_Ammeter.py | Expected `MEASURE_CIRCUTOR -get_measurement -current`, which disagrees with README and config.yaml | Removed the `-current` suffix | Two documents agree on the shorter command, so the emulator was the outlier |
| 5 | base_ammeter.py | Server could fail to restart immediately ("Address already in use") on some systems | Added `SO_REUSEADDR` before `bind` | The OS briefly reserves a closed port (mainly Linux/macOS); this allows immediate reuse. Not reproducible on Windows, added for cross-platform compatibility |
| 6 | client.py | Value was only printed, never returned; no timeout or error handling | Function now returns a float (or None), has a timeout, and catches network and parsing errors | Later code needs the numbers; a dead emulator must not hang or crash a test |

## README inconsistencies
- README lists `src/testing/AmmeterTester.py`, but the repo contains `src/testing/test_framework.py`.
- README places `main.py` in `Ammeters/`, but its imports only work from the project root.