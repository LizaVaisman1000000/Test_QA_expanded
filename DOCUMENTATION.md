# Design Documentation

## Environment
- Python 3.13 (virtual environment in `venv/`, not committed)
- Libraries installed (full list with versions in `requirements.txt`):
  - PyYAML 6.0.3: required by the provided `src/utils/config.py` to read `config/config.yaml`
  - matplotlib 3.11.2: for the optional charts (`cli.py plot`). It also installs its own dependencies, such as numpy and pillow. Nothing else works differently without it.
- Everything else uses only Python's standard library (`socket`, `statistics`, `json`, `argparse`, `logging`, ...).
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

### Accuracy and consistency comparison (`src/testing/comparison.py`)
- The emulators have no common true current: each generates random values in its own range (about 0.01 A for CIRCUTOR, about 100 A for ENTES). So the comparison measures precision (consistency) by default, and accuracy only when the user supplies a reference value (`--reference`). The report states which of the two it is showing.
- Consistency is measured with the coefficient of variation (CV = std dev / mean), which puts ammeters with very different ranges on one scale. A robust CV (1.4826 x median absolute deviation / median) is shown next to it: if the CV is much larger than the robust CV, a few extreme readings dominate. The standard error of the mean (CV / sqrt(n)) shows how precisely the mean is known.
- Ranking rule: ammeters with at least 3 valid readings are ranked first; among them a higher success rate wins (a device that drops readings is less reliable), then a lower CV. Ammeters with fewer than 3 valid readings are listed but not ranked.
- The report warns when there are fewer than 30 readings per ammeter, because spread statistics are noisy below that.
- Result of a run with 30 readings per ammeter: CIRCUTOR (CV 45.9%) was the most consistent, then ENTES (57.9%), then Greenlee (108%). These agree with the values expected from the ranges in the README (about 50%, 60% and several hundred percent). Greenlee's spread is heavy-tailed (V/R with R down to 0.1 ohm), so its CV from 30 readings understates the true spread, and the robust CV (82%) is much lower than its CV.
- Limitation: the emulators are random number generators, so their "consistency" reflects the width of each random range, not the quality of a real device. The method applies unchanged to real devices.
- `--reference` is meaningful only when every ammeter measures the same real current (real devices on one circuit). For the emulators, which draw independent random values, it was tested only to check that the report changes correctly: all three showed errors of 99% or more, which carries no meaning about their quality.

### Error simulation (`src/testing/fault_injection.py`)
- Failures are injected on the server side: a subclass of the emulator replaces `send_reply` and sometimes misbehaves. The real client and error handling are therefore tested end to end, with nothing mocked.
- Three failure types match the three ways a real device can fail: `timeout` (the reply arrives later than the client's timeout), `garbage` (the reply is not a number) and `no_reply` (the connection closes without a reply). The delay of a simulated timeout is always the client timeout plus 0.5 s, otherwise the late reply would still arrive in time.
- The failure pattern is reproducible with a seed. A private `random.Random` is used because the emulators reseed the global generator with the clock, and the seed is offset per ammeter so the three do not fail at the same readings.
- Switch on with `testing.simulation` in `config.yaml` or per run with `python cli.py run --simulate-failures RATE --seed N`. The simulation settings are saved with the run, and the report prints a note, so intentional failures are never mistaken for a faulty device. It requires `start_emulators: true` and fails with a clear error otherwise, because failures cannot be injected into devices that are already running.
- Sample run (15 readings at 5 Hz, failure rate 0.3, seed 1): 8 of 15 Greenlee readings failed (3 timeouts, 5 non-numeric), 4 of 15 ENTES and 5 of 15 CIRCUTOR; 17 of 45 in total (38%). Every failure was reported with its reason and excluded from the statistics. Success rates were 47%, 73% and 67%, so `evaluate` ranked ENTES first.
- Observation: for each ammeter the number of failed readings equalled the number of simulated failures, so a timed-out request does not make the following reading fail. The next request waits in the server's queue (about 0.5 s) and is still answered within the client timeout.
- Limitation: with 15 readings, 73% against 67% is a difference of one reading, so the ranking of ENTES and CIRCUTOR in this run is not statistically meaningful.

### Logging (`src/utils/logger.py`, `src/testing/test_framework.py`)
- Each `run` writes one text log file in `results/logs/` (the folder is set by `result_management.log_directory`). It records the start of the run and its notes, whether failure simulation is on, the settings of each ammeter, every failed reading with its position and reason, a one-line summary per ammeter, the id of the saved run, and the end of the run. The log is a second, human-readable record of a test; the JSON file in `results/runs/` is the complete data.
- The log is closed in a `finally` block, so the file is released even when a test crashes, and an unexpected error is logged before it is raised again. Validation happens before the log file is created, so a rejected request (unknown ammeter, bad settings) leaves no empty log file behind.
- Log files are regenerated on every run, so `results/logs/` is in `.gitignore`. The saved runs in `results/runs/` are the sample results.
- Limitation: failed readings are logged after all readings of an ammeter have been collected, so the time on a log line is when it was logged, not when the failure happened. The reading number gives the order, and the exact time of every reading is stored in the saved run.
- Sample: a run with 6 readings at 5 Hz, failure rate 0.5 and seed 2 logged 2 failed readings for Greenlee (4/6 valid), 5 for ENTES (1/6) and 4 for CIRCUTOR (2/6).
- Repository clean-up: the assignment contained compiled `__pycache__` files for Python 3.10-3.12 and no root `.gitignore`. A `.gitignore` was added (`venv/`, `__pycache__/`, `*.pyc`, `results/logs/`) and the cache files were removed from Git tracking.

### Charts (`src/testing/plots.py`)
- `python cli.py plot <run id>` draws three PNG charts from a saved run into `results/plots/`: `readings` (every reading over time, one panel per ammeter, with the median as a dashed line and failed readings marked with red crosses), `spread` (box plot of the valid readings) and `consistency` (CV and robust CV per ammeter, best first). Which charts are drawn, and where they are saved, is set in `analysis.visualization` in `config.yaml`; `--types` overrides it.
- matplotlib is the only library needed for this, and it is optional: it is imported only when a chart is requested, so tests, reports, saved runs and every other command work without it. Without it, `plot` prints one clear installation message.
- Design choices: the readings chart has one panel per ammeter, because the ranges differ by a factor of about 10,000 (CIRCUTOR ~0.03 A, ENTES ~70 A); the spread chart uses a logarithmic axis for the same reason and falls back to a linear axis if a reading is zero or negative. Failed readings leave a gap in the line (a line across a failure would suggest values that were never measured) and are marked along the bottom edge. Legends are placed outside the plot area so they cannot cover data, and the box plot has a caption explaining its symbols. The `Agg` backend draws into files, so charts look the same on every OS and need no display.
- A chart that cannot be drawn (for example `consistency` for a run with a single ammeter) is skipped with a reason, and the other charts are still saved.
- Sample charts for two saved runs are in `results/plots/`: a 30-reading run without failures, and the 15-reading run with simulated failures. In the first run, Greenlee's box plot shows four outliers above the box, and its mean (triangle) lies above its median; this matches its high CV (108%) against its robust CV (82%).
- Review: the first version drew a line across failed readings and had a legend covering data points; both were found by checking the images against the saved values and were fixed.

## Bugs found and fixed

| # | File | Problem | Fix | Why |
|---|------|---------|-----|-----|
| 1 | main.py | Ports 5001-5003 used instead of README ports 5000-5002 | Changed to 5000, 5001, 5002 | Match the documented configuration |
| 2 | main.py | Truncated commands (e.g. `MEASURE_GREENLEE`) | Use full commands from README | The emulator compares the request to its command exactly and silently ignores anything else |
| 3 | main.py | Request lines were commented out | Re-enabled them | Otherwise nothing is requested or printed |
| 4 | Circutor_Ammeter.py | Expected `MEASURE_CIRCUTOR -get_measurement -current`, which disagrees with README and config.yaml | Removed the `-current` suffix | Two documents agree on the shorter command, so the emulator was the outlier |
| 5 | base_ammeter.py | Server could fail to restart immediately ("Address already in use") on some systems | Added `SO_REUSEADDR` before `bind` | The OS briefly reserves a closed port (mainly Linux/macOS); this allows immediate reuse. Not reproducible on Windows, added for cross-platform compatibility |
| 6 | client.py | Value was only printed, never returned; no timeout or error handling | Function now returns a float (or None), has a timeout, and catches network and parsing errors | Later code needs the numbers; a dead emulator must not hang or crash a test |
| 7 | logger.py | `TestLogger` created a log folder and file name but never set a level or attached a file handler, so nothing was ever logged | Set the level, attached a file handler with a timestamped format, disabled propagation, and removed old handlers so repeated creation does not duplicate lines; added `close()` | A logger without a handler discards every message; handlers must be reset because `getLogger` returns the same object for the same name |
| 8 | base_ammeter.py | An exception while replying (for example the client had already disconnected after a timeout) could end the server thread, and the ammeter would silently disappear | Handling of each connection is wrapped in `try/except OSError`; the reply moved into an overridable `send_reply` method | One broken connection must not take a whole ammeter down; the hook lets failure simulation replace the reply |
| 9 | examples/run_tests.py | Called `run_test()` without the required ammeter name, and its last loop printed only a heading, never the results | Rewritten as a short working example using `framework.run(...)` and the report table | An example that crashes teaches nothing; it must be run as `python -m examples.run_tests` from the project root so that `src` can be imported |

## README inconsistencies
- README lists `src/testing/AmmeterTester.py`, but the repo contains `src/testing/test_framework.py`.
- README places `main.py` in `Ammeters/`, but its imports only work from the project root.
The README was rewritten to match the final project: it listed AmmeterTester.py (never existed) and main.py inside Ammeters/.