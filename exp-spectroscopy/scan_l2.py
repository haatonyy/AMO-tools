#!/usr/bin/env python3
"""
scan_l2.py — Sweep the λ/2 (K10CR1) waveplate and record photodetector voltage.

Moves to start_deg, steps toward end_deg in move_to() increments, then returns
to start_deg when done. Folder is named {MMDDYYYY}-{HHMMSS}-scan.

Usage:
    python scan_l2.py
    python scan_l2.py --start 0 --end 90 --step 3
    python scan_l2.py --start 10 --end 60 --step 1.5 --data-folder /my/data
"""

import argparse
import os
import time
from datetime import datetime

import serial

import config
import data_io
import utils
from k10cr1 import K10CR1


# --------------------------------------------------------------------------- #
#  Helpers                                                                     #
# --------------------------------------------------------------------------- #

def open_arduino(arduino_port: str, log_path: str):
    """Open the Arduino, verify identity, send START, and log the event."""
    arduino_ser = serial.Serial(arduino_port, config.ARDUINO_BAUD, timeout=1)
    time.sleep(1)
    arduino_ser.reset_input_buffer()
    arduino_ser.write(b"IDENTIFY\n")
    arduino_id = arduino_ser.readline().decode("utf-8").strip()
    if arduino_id != config.ARDUINO_ID_EXPECTED:
        arduino_ser.close()
        raise RuntimeError(f"[scan_l2] Wrong Arduino! Found: '{arduino_id}'")
    arduino_ser.write(b"START\n")
    data_io.log_event(log_path, f"Arduino connected: {arduino_id} — START sent")
    return arduino_ser


def sweep_and_record(
    stage: K10CR1,
    arduino_ser,
    csv_path: str,
    log_path: str,
    start_deg: float,
    end_deg: float,
    step_deg: float,
    settle_s: float,
) -> list[tuple[float, float]]:
    """
    Move to start_deg, step toward end_deg with move_to(), record voltage each step.
    Returns list of (position_deg, voltage_V).
    """
    n_steps     = int(abs(end_deg - start_deg) / step_deg)
    direction   = 1.0 if end_deg >= start_deg else -1.0
    signed_step = direction * abs(step_deg)

    data_io.write_csv_header(csv_path, ["l2_pos_deg", "voltage_V"])

    # Move to start
    data_io.log_event(log_path, f"Moving to start position: {start_deg}°")
    stage.move_to(start_deg)
    data_io.log_event(log_path, f"Reached start position: {stage.get_position():.4f}°")

    # ADC settle
    n_dummy = 5
    data_io.log_event(log_path, f"ADC settling — {n_dummy} dummy reads")
    arduino_ser.reset_input_buffer()
    for _ in range(n_dummy):
        utils.read_arduino_voltage(arduino_ser)
        time.sleep(0.1)
    data_io.log_event(log_path, "ADC settled")

    # Sweep
    data_io.log_event(log_path, f"Sweep started — {start_deg}° → {end_deg}°, {n_steps} steps of {signed_step:+.3f}°, settle={settle_s} s")
    print(f"[scan_l2] Sweeping {start_deg}° → {end_deg}° ({n_steps} steps)")

    results = []
    for i in range(n_steps):
        target  = start_deg + (i + 1) * signed_step
        stage.move_to(target)
        if settle_s > 0:
            time.sleep(settle_s)

        pos     = stage.get_position()
        voltage = utils.read_arduino_voltage(arduino_ser)

        data_io.append_csv_row(csv_path, [f"{pos:.4f}", f"{voltage}"])
        results.append((pos, voltage))

        print(f"  Step {i+1:3d}/{n_steps}: pos = {pos:8.4f}°,  voltage = {voltage} V")

    data_io.log_event(log_path, f"Sweep complete — {n_steps} points written to {os.path.basename(csv_path)}")
    return results


# --------------------------------------------------------------------------- #
#  Full scan                                                                   #
# --------------------------------------------------------------------------- #

def run_l2_scan(
    start_deg: float = 0.0,
    end_deg: float = 90.0,
    step_deg: float = 3.0,
    settle_s: float = 0.3,
    experiment_message: str = "",
    data_root: str | None = None,
    arduino_port: str = config.ARDUINO_PORT,
    kinesis_port: str = config.KINESIS_PORT,
    adc_gain: int = config.ADC_GAIN,
):
    """
    Full λ/2 scan: move to start, sweep to end, return to start when done.

    Args:
        start_deg:          Absolute start angle (degrees).
        end_deg:            Absolute end angle (degrees).
        step_deg:           Step size in degrees (positive; direction inferred).
        settle_s:           Settle time after each move before reading voltage.
        experiment_message: Free-text label written to the log.
        data_root:          Top-level folder for output data.
        arduino_port:       Arduino serial port.
        kinesis_port:       K10CR1 serial port.
    """
    start_time = datetime.now()
    n_steps    = int(abs(end_deg - start_deg) / step_deg)

    # 1. Create -scan folder
    folder_name = data_io.create_run_folder(
        experiment_message=experiment_message,
        data_root=data_root,
        suffix="scan",
    )
    csv_path = os.path.join(folder_name, "data.csv")
    log_path = os.path.join(folder_name, "log.txt")
    print(f"[scan_l2] Output folder: {folder_name}")

    adc_range, adc_precision_mV = config.ADC_GAIN_TABLE[adc_gain]

    # 2. Open log with header + params block
    params = {
        "Folder":             folder_name,
        "Arduino port":       arduino_port,
        "Kinesis port":       kinesis_port,
        "Experiment message": experiment_message or "(none)",
        "Scan start":         f"{start_deg} deg",
        "Scan end":           f"{end_deg} deg",
        "Step size":          f"{step_deg} deg",
        "Steps":              n_steps,
        "Total sweep":        f"{n_steps * step_deg:.2f} deg",
        "Settle time":        f"{settle_s} s",
        "ADC gain code":      adc_gain,
        "ADC range":          adc_range,
        "ADC precision":      f"{adc_precision_mV} mV/bit",
        "Data file":          "data.csv",
    }
    data_io.log_open(log_path, "λ/2 WAVEPLATE POSITION SCAN", params)

    # 3. Open hardware
    arduino_ser = open_arduino(arduino_port, log_path)
    stage       = K10CR1(port=kinesis_port, verbose=False)
    data_io.log_event(log_path, f"K10CR1 connected on {kinesis_port}")

    # 4. Write params.json
    data_io.write_json_params(folder_name, {
        "experiment_message":   experiment_message,
        "folder":               folder_name,
        "run_start":            start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "arduino_port":         arduino_port,
        "kinesis_port":         kinesis_port,
        "start_deg":            start_deg,
        "end_deg":              end_deg,
        "step_deg":             step_deg,
        "n_steps":              n_steps,
        "settle_s":             settle_s,
        "adc_gain_code":        adc_gain,
        "adc_range":            adc_range,
        "adc_precision_mV_bit": adc_precision_mV,
        "arduino_id":           config.ARDUINO_ID_EXPECTED,
    })

    try:
        # 5. Sweep
        sweep_and_record(
            stage       = stage,
            arduino_ser = arduino_ser,
            csv_path    = csv_path,
            log_path    = log_path,
            start_deg   = start_deg,
            end_deg     = end_deg,
            step_deg    = step_deg,
            settle_s    = settle_s,
        )

    finally:
        # 6. Return to start and close
        data_io.log_event(log_path, f"Returning to start position: {start_deg}°")
        stage.move_to(start_deg)
        data_io.log_event(log_path, f"Returned to {stage.get_position():.4f}°")

        arduino_ser.write(b"STOP\n")
        arduino_ser.close()
        stage.close()
        data_io.log_event(log_path, "Arduino STOP sent — hardware closed")

        data_io.log_close(log_path, start_time)
        print(f"[scan_l2] Done. Files saved in {folder_name}")


# --------------------------------------------------------------------------- #
#  CLI                                                                         #
# --------------------------------------------------------------------------- #

def _parse_args():
    parser = argparse.ArgumentParser(
        description="Sweep K10CR1 λ/2 waveplate and record photodetector voltage"
    )
    parser.add_argument("--start",    type=float, default=0.0,
                        help="Scan start angle in degrees (default: 0)")
    parser.add_argument("--end",      type=float, default=90.0,
                        help="Scan end angle in degrees (default: 90)")
    parser.add_argument("--step",     type=float, default=3.0,
                        help="Step size in degrees (default: 3.0)")
    parser.add_argument("--settle",   type=float, default=0.3,
                        help="Settle time in seconds after each move (default: 0.3)")
    parser.add_argument("--message", "-m", default="",
                        help="Experiment description")
    parser.add_argument("--data-folder", "-d", default=None, dest="data_root",
                        help="Top-level output folder (default: current directory)")
    parser.add_argument("--arduino-port", default=config.ARDUINO_PORT,
                        help=f"Arduino port (default: {config.ARDUINO_PORT})")
    parser.add_argument("--kinesis-port", default=config.KINESIS_PORT,
                        help=f"K10CR1 port (default: {config.KINESIS_PORT})")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_l2_scan(
        start_deg          = args.start,
        end_deg            = args.end,
        step_deg           = args.step,
        settle_s           = args.settle,
        experiment_message = args.message,
        data_root          = args.data_root,
        arduino_port       = args.arduino_port,
        kinesis_port       = args.kinesis_port,
    )