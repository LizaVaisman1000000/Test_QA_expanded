import threading
import time
from socket import create_connection
from typing import Dict, List, Optional

from Ammeters.Circutor_Ammeter import CircutorAmmeter
from Ammeters.Entes_Ammeter import EntesAmmeter
from Ammeters.Greenlee_Ammeter import GreenleeAmmeter
from src.testing.ammeter_client import AmmeterClient
from src.testing.analysis import analyze
from src.testing.fault_injection import FAILURE_TYPES, make_faulty
from src.testing.result_store import ResultStore
from src.testing.sampler import resolve_sampling_plan, collect_samples
from src.utils.config import load_config

# Emulator classes, by the name used in config.yaml. Only needed when the
# framework starts the emulators itself (start_emulators: true).
EMULATORS = {
    "greenlee": GreenleeAmmeter,
    "entes": EntesAmmeter,
    "circutor": CircutorAmmeter,
}


class AmmeterTestFramework:
    """One entry point that runs a complete test: start, sample, analyze, save."""

    def __init__(self, config_path: str = "config/config.yaml"):
        self.config = load_config(config_path)
        self.store = ResultStore.from_config(self.config)
        self._started = set()   # emulators this framework already started

    # ---- setup helpers -------------------------------------------------

    def _plan(self, count, duration, frequency):
        """Sampling settings: explicit arguments win; otherwise config.yaml is used.

        Arguments and config are never mixed. Mixing could produce settings that
        contradict each other (e.g. config count 10 with an argument duration of 10 s).
        """
        if count is None and duration is None and frequency is None:
            sampling = self.config["testing"]["sampling"]
            count = sampling["measurements_count"]
            duration = sampling["total_duration_seconds"]
            frequency = sampling["sampling_frequency_hz"]
        return resolve_sampling_plan(count, duration, frequency)

    def _simulation_settings(self) -> Optional[dict]:
        """Failure-simulation settings from config.yaml, or None when switched off."""
        simulation = self.config["testing"].get("simulation") or {}
        if not simulation.get("enabled"):
            return None
        if not self.config["testing"]["start_emulators"]:
            # Failures are injected into emulators we start ourselves; they cannot
            # be injected into devices that are already running. Fail loudly
            # instead of silently running a test with no simulation.
            raise ValueError("Failure simulation needs start_emulators: true")
        return simulation

    def _wait_until_ready(self, port: int, timeout: float = 5.0):
        """Wait until the emulator accepts connections, instead of sleeping a fixed time.

        Faster than a fixed sleep when the server starts quickly, and it fails
        with a clear message when the server never starts.
        """
        host = self.config["testing"]["host"]
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            try:
                # Short per-attempt timeout: on Windows, connecting to a closed
                # port can otherwise block for about 2 seconds.
                create_connection((host, port), timeout=0.5).close()
                return
            except OSError:
                time.sleep(0.1)
        raise RuntimeError(f"Ammeter on port {port} did not start within {timeout}s")

    def _ensure_emulator(self, name: str):
        if not self.config["testing"]["start_emulators"] or name in self._started:
            return
        emulator_class = EMULATORS.get(name)
        if emulator_class is None:
            raise ValueError(f"No emulator available for '{name}'. "
                             f"Set start_emulators: false to test real devices.")

        simulation = self._simulation_settings()
        if simulation:
            seed = simulation.get("seed")
            emulator_class = make_faulty(
                emulator_class,
                failure_rate=simulation["failure_rate"],
                failure_types=simulation.get("failure_types") or FAILURE_TYPES,
                # A "timeout" failure must outlast the client's timeout, or the
                # client would still receive the reply and nothing would fail.
                delay_seconds=self.config["testing"]["timeout_seconds"] + 0.5,
                # Offset the seed per ammeter, so they do not all fail at the
                # same readings, while each one stays repeatable.
                seed=None if seed is None else seed + list(EMULATORS).index(name))

        port = self.config["ammeters"][name]["port"]
        # daemon=True: the emulator stops when the program ends.
        threading.Thread(target=emulator_class(port).start_server, daemon=True).start()
        self._wait_until_ready(port)
        self._started.add(name)

    # ---- running tests -------------------------------------------------

    def run_test(self, ammeter_type: str, count: Optional[int] = None,
                 duration: Optional[float] = None,
                 frequency: Optional[float] = None) -> Dict:
        """Test one ammeter. Returns its settings, raw readings and statistics."""
        # Validate everything BEFORE starting anything, so a typo in the name
        # or the settings fails immediately and not after a long wait.
        client = AmmeterClient.from_config(ammeter_type, self.config)
        count, interval = self._plan(count, duration, frequency)
        simulation = self._simulation_settings()

        self._ensure_emulator(ammeter_type)
        measurements = collect_samples(client, count, interval)
        return {
            "ammeter": ammeter_type,
            "settings": {
                "measurements_count": count,
                "interval_seconds": interval,
                "sampling_frequency_hz": 1.0 / interval,
                "duration_seconds": count * interval,
                "timeout_seconds": client.timeout,
                # Saved with the run, so failed readings in an old result are
                # never mistaken for real device faults.
                "simulation": simulation,
            },
            "measurements": measurements,
            "stats": analyze(measurements),
        }

    def run(self, ammeters: Optional[List[str]] = None, count: Optional[int] = None,
            duration: Optional[float] = None, frequency: Optional[float] = None,
            save: bool = True, notes: str = "") -> Dict:
        """Test several ammeters (all configured ones by default) and save one run.

        Ammeters are tested one after another, so the total time is roughly
        (number of ammeters x duration).
        """
        names = list(ammeters) if ammeters else list(self.config["ammeters"])
        for name in names:   # validate all names first, before any waiting
            AmmeterClient.from_config(name, self.config)
        results = {name: self.run_test(name, count, duration, frequency) for name in names}

        run_id = None
        if save:
            settings = next(iter(results.values()))["settings"]
            run_id = self.store.save_run(
                {name: r["measurements"] for name, r in results.items()},
                settings, notes)
        return {"run_id": run_id, "results": results}