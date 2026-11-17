# Design Documentation

## Environment
- Python 3.15.2, virtual environment in `venv/` (not committed)
- Libraries installed: none so far

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