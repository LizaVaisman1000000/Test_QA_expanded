import json
import os
import platform
import sys
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Dict, List

from src.testing.ammeter_client import Measurement
from src.testing.analysis import analyze

COMPARED_METRICS = ("mean", "median", "std_dev", "cv_percent")


class ResultStore:
    """Saves each test run as one JSON file and brings it back later."""

    def __init__(self, directory: str = "results/runs"):
        self.directory = directory

    @classmethod
    def from_config(cls, config: dict) -> "ResultStore":
        return cls(config["result_management"]["directory"])

    def _path(self, run_id: str) -> str:
        # Reject anything that is not a plain file name, so a run id such as
        # "../secret" can never reach outside the results folder.
        if not run_id or run_id != os.path.basename(run_id):
            raise ValueError(f"Invalid run id: {run_id!r}")
        return os.path.join(self.directory, f"{run_id}.json")

    def save_run(self, results: Dict[str, List[Measurement]], settings: dict,
                 notes: str = "") -> str:
        """Save one run (the readings of one or more ammeters). Returns its unique id."""
        now = datetime.now()
        # Timestamp makes ids sortable and readable; the random suffix keeps two
        # runs started in the same second apart.
        
        # Microseconds (%f) make ids sort in true creation order, even for two runs in
        # the same second. The random suffix still guarantees uniqueness if two
        # processes ever save at the exact same microsecond.
        run_id = now.strftime("%Y%m%d_%H%M%S_%f") + "_" + uuid.uuid4().hex[:6]
        record = {
            "run_id": run_id,
            "created_at": now.isoformat(timespec="seconds"),
            "metadata": {
                "python_version": sys.version.split()[0],
                "platform": platform.platform(),
                "notes": notes,
            },
            "settings": settings,
            "ammeters": {
                name: {
                    # Statistics are stored too, so old runs can be compared
                    # without recomputing; raw readings are kept so they can
                    # be re-analyzed or plotted later.
                    "stats": asdict(analyze(measurements)),
                    "measurements": [asdict(m) for m in measurements],
                }
                for name, measurements in results.items()
            },
        }
        os.makedirs(self.directory, exist_ok=True)
        path = self._path(run_id)
        # Write to a temporary file first, then rename: a crash mid-write
        # cannot leave a half-written (corrupt) result file behind.
        tmp_path = path + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as f:
            json.dump(record, f, indent=2)
        os.replace(tmp_path, path)
        return run_id

    def load_run(self, run_id: str) -> dict:
        path = self._path(run_id)
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            raise ValueError(f"No saved run with id '{run_id}'") from None
        except json.JSONDecodeError as e:
            raise ValueError(f"Saved run '{run_id}' is corrupt: {e}") from None

    def list_runs(self) -> List[dict]:
        """Short summary of every saved run, oldest first."""
        if not os.path.isdir(self.directory):
            return []
        summaries = []
        for file_name in sorted(os.listdir(self.directory)):
            if not file_name.endswith(".json"):
                continue
            try:
                run = self.load_run(file_name[:-5])
            except ValueError as e:
                # One damaged file must not hide all the other runs.
                print(f"Skipping {file_name}: {e}")
                continue
            summaries.append({
                "run_id": run["run_id"],
                "created_at": run["created_at"],
                "ammeters": {name: data["stats"]["mean"]
                             for name, data in run["ammeters"].items()},
            })
        return summaries

    def compare_runs(self, run_id_a: str, run_id_b: str) -> dict:
        """Compare the ammeters that appear in both runs, metric by metric."""
        a, b = self.load_run(run_id_a), self.load_run(run_id_b)
        common = [name for name in a["ammeters"] if name in b["ammeters"]]
        if not common:
            raise ValueError("The two runs have no ammeter in common")
        comparison = {}
        for name in common:
            stats_a, stats_b = a["ammeters"][name]["stats"], b["ammeters"][name]["stats"]
            rows = {}
            for metric in COMPARED_METRICS:
                va, vb = stats_a[metric], stats_b[metric]
                change = None
                if va not in (None, 0) and vb is not None:
                    change = (vb - va) / abs(va) * 100
                rows[metric] = {"a": va, "b": vb, "change_percent": change}
            comparison[name] = rows
        return comparison