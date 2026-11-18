# Ammeter Testing Framework

A framework for testing current-measurement devices. It talks to three ammeter
emulators (Greenlee, ENTES, CIRCUTOR) through one common interface, takes
measurements with configurable timing, computes statistics, and archives every
test run so runs can be listed and compared later.

## Requirements
- Python 3.10 or newer (developed and tested on Python 3.13)
- One external library: PyYAML (used by the provided `src/utils/config.py`)

## Installation
```sh
python -m venv venv
venv\Scripts\activate          # Windows (PowerShell: venv\Scripts\Activate.ps1)
source venv/bin/activate       # Linux / macOS
pip install -r requirements.txt
```

Note: PyYAML had no prebuilt package for Python 3.15 when this was written.
If installation fails, use Python 3.13.

## Usage
Run all commands from the project root. The emulators are started
automatically (see `start_emulators` in `config/config.yaml`).

```sh
# Test all three ammeters: 10 readings at 2 Hz (defaults come from config.yaml)
python cli.py run

# Choose the settings yourself (any two of count / duration / frequency)
python cli.py run --count 20 --frequency 5
python cli.py run --duration 10 --frequency 2
python cli.py run --ammeters greenlee entes --count 5 --duration 5 --notes "my note"

# Work with saved results
python cli.py list
python cli.py show <run id>
python cli.py compare <run id A> <run id B>
python cli.py evaluate <run id>                  # rank the ammeters of a saved run
python cli.py evaluate <run id> --reference 10   # also compare against a known true current (A)

# Make readings fail on purpose to check error handling (the framework starts the emulators)
python cli.py run --count 15 --frequency 5 --simulate-failures 0.3 --seed 1

# Quick demo: start the emulators and request one reading from each
python main.py
```

Every `run` prints a statistics table (mean, median, standard deviation,
min, max, coefficient of variation) and saves the run as a JSON file in
`results/runs/`. Failed readings are excluded from the statistics and listed
with the reason.

### Using the framework from Python
```python
from src.testing.test_framework import AmmeterTestFramework

framework = AmmeterTestFramework()
outcome = framework.run(count=10, frequency=2, notes="example")
print(outcome["results"]["greenlee"]["stats"])
```

## Configuration (`config/config.yaml`)
| Setting | Meaning |
|---|---|
| `testing.start_emulators` | `true`: start the emulators automatically; `false`: use ammeters that are already running |
| `testing.host`, `testing.timeout_seconds` | where to connect and how long to wait for a reply |
| `testing.sampling.*` | default count / duration / frequency (any two are enough) |
| `testing.simulation.*` | failure simulation: `enabled`, `failure_rate` (0 to 1), `failure_types` (`timeout`, `garbage`, `no_reply`), `seed` (repeatable pattern); needs `start_emulators: true` |
| `ammeters.<name>.port`, `.command` | one block per ammeter; add a block to add an ammeter |
| `result_management.directory` | where saved runs are stored |

## Ammeter emulators
| Ammeter | Port | Command | Measurement |
|---|---|---|---|
| Greenlee | 5000 | `MEASURE_GREENLEE -get_measurement` | Ohm's law: I = V / R (V 1-10 V, R 0.1-100 ohm) |
| ENTES | 5001 | `MEASURE_ENTES -get_data` | Hall effect: I = B x K (B 0.01-0.1 T, K 500-2000) |
| CIRCUTOR | 5002 | `MEASURE_CIRCUTOR -get_measurement` | Rogowski coil: I = integral of V dt (10 samples) |

An emulator answers only when the request matches its command exactly; any
other request is silently ignored.

## Project structure
- `main.py`: quick demo that starts the emulators and requests one reading from each
- `cli.py`: command-line interface (`run`, `list`, `show`, `compare`, `evaluate`)
- `Ammeters/`: the emulators (`base_ammeter.py`, one file per brand) and `client.py`
- `config/config.yaml`: all settings
- `src/testing/`
  - `ammeter_client.py`: unified interface; every reading is a `Measurement`
  - `sampler.py`: sampling with configurable count/duration/frequency and drift-free timing
  - `analysis.py`: statistics
  - `result_store.py`: saving, loading, listing and comparing runs
  - `comparison.py`: precision and accuracy comparison, ranking of the ammeters
  - `fault_injection.py`: makes an emulator fail on purpose (timeout, garbage reply, no reply)
  - `report.py`: text tables
  - `test_framework.py`: `AmmeterTestFramework`, ties everything together
- `src/utils/`: `config.py`, `Utils.py`, `logger.py`
- `results/runs/`: sample test results (one JSON file per run)
- `DOCUMENTATION.md`: design decisions and the list of bugs fixed in the provided code