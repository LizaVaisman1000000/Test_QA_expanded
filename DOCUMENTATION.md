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

### Measurement sampling (`src/testing/sampler.py`)
- Count, duration and frequency depend on each other (count = duration x frequency), so any two of them can be given. `resolve_sampling_plan` computes the rest and rejects missing, non-positive or contradicting settings with a clear message.
- Readings are scheduled against the start time (start + i x interval) and not by sleeping a fixed interval after each reading. This prevents drift: the time spent measuring would otherwise accumulate. If a reading is late (e.g. a timeout), the next one is taken immediately and the schedule catches up.
- `time.perf_counter()` is used because it is a monotonic clock, unaffected by system clock changes during a test.
- Measured result: 5 readings at 4 Hz were spaced 0.25 s apart, with no drift.

### Result analysis (`src/testing/analysis.py`)
- `analyze()` computes mean, median, standard deviation, minimum and maximum for one ammeter, plus the number of valid and failed readings and a count of each failure reason.
- Failed readings are excluded from the statistics. Counting a failure as 0 A would distort every metric; instead failures are reported separately.
- Sample standard deviation (n-1) is used, since the readings are a sample of the ammeter's behavior.
- Edge cases return `None` instead of crashing or inventing numbers: no valid readings gives no statistics, and fewer than two valid readings gives no standard deviation.
- The coefficient of variation (std dev / mean x 100) is included so ammeters with very different ranges (CIRCUTOR ~0.01 A, ENTES ~100 A) can be compared fairly. It is the basis for the accuracy comparison.
- Verified against hand-calculated values (1, 2, 3, 4, 5 gives mean 3, median 3, std dev 1.5811) and the all-failed, single-reading and empty cases.

### Result management (`src/testing/result_store.py`)
- Each test run is saved as one human-readable JSON file in `results/runs/`. A run holds a unique id, creation time, metadata (Python version, platform, notes), the settings used, the raw readings and the computed statistics per ammeter.
- Run ids combine a timestamp (with microseconds) and a random suffix: readable, sorted in creation order, and unique. A first version used a timestamp with whole seconds, and two runs saved in the same second were listed in the wrong order; microseconds fixed this.
- Files are written to a temporary file and then renamed, so a crash while saving cannot leave a corrupt result file.
- `list_runs` skips a damaged file with a warning instead of failing, so one bad file does not hide the other runs.
- Run ids are validated so an id like `../secret` cannot read files outside the results folder.
- `compare_runs` compares mean, median, standard deviation and coefficient of variation between two runs, with the percentage change.

### Test framework (`src/testing/test_framework.py`)
- `AmmeterTestFramework.run()` is the single entry point: it validates the request, starts the emulators if configured, samples each ammeter, analyzes the readings and saves one run. `run_test(ammeter_type)` tests a single ammeter. The file arrived as a skeleton (`run_test` only said `pass`, and `Dict` was not imported); it was implemented keeping its original class name, constructor and method signature.
- Emulators are started automatically by default (`start_emulators: true`) and can be turned off in `config.yaml`, so the same framework can test real devices.
- The framework waits until an emulator accepts connections, instead of sleeping a fixed time: faster when the server starts quickly, and a clear error if it never starts.
- Ammeter names and sampling settings are validated before anything starts, so mistakes fail immediately and not after a long test.
- Sampling settings come either from explicit arguments or from `config.yaml`, never a mix of both, to avoid contradicting settings.
- Observation: Greenlee readings are very spread out (resistance 0.1-100 Ohm gives currents from about 0.01 A to 100 A), so the median is a more robust measure than the mean for comparing ammeters.

### Reporting and command line (`src/testing/report.py`, `cli.py`)
- Report functions take plain dictionaries, so one table format serves both a fresh test and a run loaded from a saved JSON file.
- Failed readings are never hidden: the report lists which ammeter failed and why.
- The command line uses Python's built-in `argparse` (no extra library, works on every OS): `run`, `list`, `show` and `compare`. Expected mistakes (unknown ammeter, unknown run id, bad settings) print one `Error:` line and no traceback.
- Observation from the sample runs: the mean of the Greenlee readings changed by -46.8% between two runs while the median changed by only +15.5%. A single large reading pulls the mean, so the median is the more stable summary for ammeters with widely spread readings.

## Sample test results
Two real runs are saved in `results/runs/` (run ids appear in `python cli.py list`): one with all three ammeters, one with Greenlee only. They can be displayed with `python cli.py show <run id>` and compared with `python cli.py compare <run id A> <run id B>`.

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
The README was rewritten to match the final project: it listed AmmeterTester.py (never existed) and main.py inside Ammeters/.