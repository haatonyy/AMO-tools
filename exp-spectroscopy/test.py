#!/usr/bin/env python3
"""
test_l2_repeatability.py — Test whether the K10CR1 returns to the same position
                            and gives consistent voltage readings after jogging away.

For each trial:
    1. Move to target_deg, take a voltage reading
    2. Jog away by jog_deg for jog_s seconds
    3. Move back to target_deg, take a voltage reading
    4. Repeat n_trials times

Results are printed to console and saved to a CSV.

Usage:
    python test_l2_repeatability.py
    python test_l2_repeatability.py --target 45 --jog-deg 20 --trials 10
"""

import argparse
import time
from datetime import datetime

import serial

import config
import data_io
import utils
from k10cr1 import K10CR1


N_DUMMY_READS  = 6      # ADC settle reads before each real measurement
DUMMY_DELAY_S  = 0.1    # seconds between dummy reads


def settle_and_read(arduino_ser) -> float | None:
    """Flush dummy reads, then return one real voltage measurement."""
    arduino_ser.reset_input_buffer()
    for _ in range(N_DUMMY_READS):
        utils.read_arduino_voltage(arduino_ser)
        time.sleep(DUMMY_DELAY_S)
    return utils.read_arduino_voltage(arduino_ser)


def run_repeatability_test(
    target_deg: float = 45.0,
    jog_deg: float = 20.0,
    jog_s: float = 5.0,
    n_trials: int = 5,
    data_root: str | None = None,
    arduino_port: str = config.ARDUINO_PORT,
    kinesis_port: str = config.KINESIS_PORT,
):
    """
    Repeatability test: move to target, read, jog away, return, read — n times.

    Args:
        target_deg:   Absolute position to test (degrees).
        jog_deg:      How far to jog away between measurements (degrees).
        jog_s:        How long to wait at the jogged position (seconds).
        n_trials:     Number of go-away-and-return cycles.
        data_root:    Top-level folder for output data.
        arduino_port: Arduino serial port.
        kinesis_port: K10CR1 serial port.
    """
    start_time = datetime.now()

    # Output folder + CSV
    folder_name, csv_path, log_path = data_io.create_run_folder(
        experiment_message="l2_repeatability_test",
        data_root=data_root,
    )
    data_io.write_csv_header(csv_path, ["trial", "event", "stage_pos_deg", "voltage_V", "elapsed_s"])
    print(f"[repeat] Output folder: {folder_name}")

    # Open hardware
    arduino_ser = serial.Serial(arduino_port, config.ARDUINO_BAUD, timeout=1)
    time.sleep(1)
    arduino_ser.reset_input_buffer()
    arduino_ser.write(b"START\n")

    stage = K10CR1(port=kinesis_port, verbose=False)

    print(f"\n[repeat] Config: target={target_deg}°  jog={jog_deg}°  wait={jog_s}s  trials={n_trials}")
    print(f"[repeat] Moving to target position: {target_deg}°")
    stage.move_to(target_deg)

    def record(trial: int, event: str):
        """Settle ADC, read voltage, log and print the result."""
        voltage = settle_and_read(arduino_ser)
        pos     = stage.get_position()
        elapsed = (datetime.now() - start_time).total_seconds()
        data_io.append_csv_row(csv_path, [trial, event, f"{pos:.4f}", f"{voltage}", f"{elapsed:.2f}"])
        print(f"  Trial {trial:2d} | {event:<12s} | pos = {pos:8.4f}°  voltage = {voltage} V")
        return voltage

    readings_before = []
    readings_after  = []

    try:
        for trial in range(1, n_trials + 1):
            print(f"\n--- Trial {trial}/{n_trials} ---")

            # 1. At target — take measurement
            v_before = record(trial, "at_target")
            readings_before.append(v_before)

            # 2. Jog away
            print(f"  Jogging away by {jog_deg}°...")
            stage.move_by(jog_deg)
            print(f"  Waiting {jog_s} s at jogged position ({stage.get_position():.4f}°)...")
            time.sleep(jog_s)

            # 3. Return to target
            print(f"  Returning to {target_deg}°...")
            stage.move_to(target_deg)

            # 4. Take measurement after return
            v_after = record(trial, "returned")
            readings_after.append(v_after)

    finally:
        # Summary
        print("\n" + "=" * 50)
        print("REPEATABILITY SUMMARY")
        print("=" * 50)
        print(f"{'Trial':>6}  {'Before':>10}  {'After':>10}  {'Δ':>10}")
        print("-" * 50)
        for i, (vb, va) in enumerate(zip(readings_before, readings_after), 1):
            delta = (va - vb) if (vb is not None and va is not None) else None
            vb_s  = f"{vb:.6f}" if vb  is not None else "  None  "
            va_s  = f"{va:.6f}" if va  is not None else "  None  "
            d_s   = f"{delta:+.6f}" if delta is not None else "  None  "
            print(f"  {i:>4}  {vb_s:>10}  {va_s:>10}  {d_s:>10}")

        valid_after = [v for v in readings_after if v is not None]
        if len(valid_after) > 1:
            mean = sum(valid_after) / len(valid_after)
            std  = (sum((v - mean) ** 2 for v in valid_after) / len(valid_after)) ** 0.5
            print("-" * 50)
            print(f"  Returned readings — mean: {mean:.6f} V   std: {std:.6f} V   ({len(valid_after)} trials)")

        # Write summary to log
        end_time   = datetime.now()
        duration_s = int((end_time - start_time).total_seconds())
        with open(log_path, "w") as log:
            log.write("L/2 REPEATABILITY TEST LOG\n")
            log.write(f"Start Time:    {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log.write(f"End Time:      {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            log.write(f"Duration:      {duration_s // 60}m {duration_s % 60}s\n")
            log.write("-" * 40 + "\n")
            log.write(f"Target:        {target_deg} deg\n")
            log.write(f"Jog distance:  {jog_deg} deg\n")
            log.write(f"Jog wait:      {jog_s} s\n")
            log.write(f"Trials:        {n_trials}\n")
            if len(valid_after) > 1:
                log.write(f"Return mean:   {mean:.6f} V\n")
                log.write(f"Return std:    {std:.6f} V\n")

        arduino_ser.write(b"STOP\n")
        arduino_ser.close()
        stage.close()
        print(f"\n[repeat] Done. Files saved in {folder_name}")


# --------------------------------------------------------------------------- #
#  CLI                                                                         #
# --------------------------------------------------------------------------- #

def _parse_args():
    parser = argparse.ArgumentParser(
        description="Test K10CR1 position repeatability with voltage measurements"
    )
    parser.add_argument("--target",   type=float, default=0.0,
                        help="Target position to test in degrees (default: 45)")
    parser.add_argument("--jog-deg",  type=float, default=20.0,
                        help="Degrees to jog away between trials (default: 20)")
    parser.add_argument("--jog-s",    type=float, default=10,
                        help="Seconds to wait at jogged position (default: 5)")
    parser.add_argument("--trials",   type=int,   default=20,
                        help="Number of go-and-return cycles (default: 5)")
    parser.add_argument("--data-folder", "-d", default=None, dest="data_root",
                        help="Top-level output folder (default: current directory)")
    parser.add_argument("--arduino-port", default=config.ARDUINO_PORT,
                        help=f"Arduino port (default: {config.ARDUINO_PORT})")
    parser.add_argument("--kinesis-port", default=config.KINESIS_PORT,
                        help=f"K10CR1 port (default: {config.KINESIS_PORT})")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_repeatability_test(
        target_deg   = args.target,
        jog_deg      = args.jog_deg,
        jog_s        = args.jog_s,
        n_trials     = args.trials,
        data_root    = args.data_root,
        arduino_port = args.arduino_port,
        kinesis_port = args.kinesis_port,
    )