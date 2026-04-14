# data_io.py — Folder creation, CSV writing, HST-style event logging, JSON params

import csv
import json
import os
from datetime import datetime


# --------------------------------------------------------------------------- #
#  Folder                                                                      #
# --------------------------------------------------------------------------- #

def create_run_folder(
    experiment_message: str = "",
    data_root: str | None = None,
    suffix: str = "spec",
) -> str:
    """
    Create a timestamped folder inside a date-named parent.

    Structure:  <data_root>/<MMDDYYYY>/<MMDDYYYY-HHMMSS>-{suffix}[-background]/

    Args:
        experiment_message: If it contains 'Background File', '-background' is appended.
        data_root:          Override the top-level directory (default: cwd).
        suffix:             Folder suffix — 'spec' for current sweeps, 'scan' for l2 scans.
    """
    now      = datetime.now()
    date_str = now.strftime("%m%d%Y")
    time_str = now.strftime("%H%M%S")

    parent = os.path.join(data_root, date_str) if data_root else date_str
    os.makedirs(parent, exist_ok=True)

    run_name = f"{date_str}-{time_str}-{suffix}"
    if "Background File" in experiment_message:
        run_name += "-background"

    folder_name = os.path.join(parent, run_name)
    os.makedirs(folder_name, exist_ok=True)
    return folder_name


# --------------------------------------------------------------------------- #
#  HST-style event log                                                         #
# --------------------------------------------------------------------------- #

_WIDTH = 80

def log_open(log_path: str, title: str, params: dict, run_index: int | None = None):
    """
    Write the opening block of a log file:  header banner + parameters table.

    Args:
        log_path:   Path to the log file (will be created/overwritten).
        title:      One-line experiment title shown in the banner.
        params:     Dict of parameter names → values printed in the params block.
        run_index:  If this is one of several sweeps, show the run number.
    """
    now = datetime.now()
    with open(log_path, "w") as f:
        f.write("=" * _WIDTH + "\n")
        f.write(f"  {title}\n")
        if run_index is not None:
            f.write(f"  Run {run_index}\n")
        f.write("=" * _WIDTH + "\n")
        f.write("\n")
        f.write("  PARAMETERS\n")
        f.write("  " + "-" * (_WIDTH - 2) + "\n")
        for k, v in params.items():
            f.write(f"  {k:<28} {v}\n")
        f.write("\n")
        f.write("  " + "-" * (_WIDTH - 2) + "\n")
        f.write("  EVENT LOG\n")
        f.write("  " + "-" * (_WIDTH - 2) + "\n")
    log_event(log_path, f"Log opened — {now.strftime('%Y-%m-%d %H:%M:%S')}")


def log_event(log_path: str, message: str, level: str = "INFO"):
    """
    Append one timestamped event line to the log.

    Format:   2026-04-08 15:30:52  [INFO]   Message text here
    """
    ts = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a") as f:
        f.write(f"  {ts}  [{level:<5}]  {message}\n")


def log_close(log_path: str, start_time: datetime, status: str = "SUCCESS"):
    """Write the closing banner with total run time and status."""
    end_time      = datetime.now()
    total_seconds = int((end_time - start_time).total_seconds())
    duration_str  = f"{total_seconds // 60}m {total_seconds % 60}s"

    with open(log_path, "a") as f:
        f.write("\n")
        f.write("  " + "-" * (_WIDTH - 2) + "\n")
        log_event(log_path, f"End time     : {end_time.strftime('%Y-%m-%d %H:%M:%S')}")
        log_event(log_path, f"Total runtime: {duration_str}")
        log_event(log_path, f"Status       : {status}")
        f.write("=" * _WIDTH + "\n")


# --------------------------------------------------------------------------- #
#  JSON params                                                                 #
# --------------------------------------------------------------------------- #

def write_json_params(folder_name: str, params: dict, filename: str = "params.json"):
    """Write experiment parameters to a JSON file inside folder_name."""
    path = os.path.join(folder_name, filename)
    with open(path, "w") as f:
        json.dump(params, f, indent=4, default=str)
    print(f"[data_io] {filename} → {path}")


def read_json_params(folder_name: str) -> dict:
    """Load and return params.json from a run folder."""
    path = os.path.join(folder_name, "params.json")
    with open(path) as f:
        return json.load(f)


# --------------------------------------------------------------------------- #
#  CSV                                                                         #
# --------------------------------------------------------------------------- #

def write_csv_header(csv_path: str, columns: list[str]):
    """Create (or overwrite) a CSV and write the header row."""
    with open(csv_path, "w", newline="") as f:
        csv.writer(f).writerow(columns)


def append_csv_row(csv_path: str, row: list):
    """Append one data row to an existing CSV."""
    with open(csv_path, "a", newline="") as f:
        csv.writer(f).writerow(row)