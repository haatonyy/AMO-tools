#!/usr/bin/env python3
"""
run_experiment.py — 3491 nm laser current-sweep experiment.

Supports a single l2_position_deg or a list of them. Each position runs a
full current sweep and saves its own numbered data/log file in the same folder.

Usage:
    python run_experiment.py
    python run_experiment.py --l2-pos 45.0
    python run_experiment.py --l2-pos 0 22.5 45 67.5 90
    python run_experiment.py --i-init 72.0 --i-final 74.0 --p852 2.4
"""

import argparse
import os
import serial
import sys
import time
from datetime import datetime

import config
import connections
import data_io
import utils
from k10cr1 import K10CR1
from science import get_laser_temperature


# --------------------------------------------------------------------------- #
#  Laser init                                                                  #
# --------------------------------------------------------------------------- #

def init_laser(laser_ser, log_path: str, i_init_mA: float = config.I_INIT_mA):
    """Set laser safety limits, step size, and ramp to the initial current."""
    utils.write_laser_command(laser_ser, b"LASer:LIMit:LDV", config.LASER_VOLTAGE_LIMIT_V, print_setup=True)
    utils.write_laser_command(laser_ser, b"LASer:LIMit:LDI", config.LASER_CURRENT_LIMIT_mA, print_setup=True)
    utils.write_laser_command(laser_ser, b"LASer:STEP",       config.LASER_STEP_mA,          print_setup=True)
    data_io.log_event(log_path, f"Laser limits set (LDV={config.LASER_VOLTAGE_LIMIT_V} V, LDI={config.LASER_CURRENT_LIMIT_mA} mA, STEP={config.LASER_STEP_mA})")

    utils.write_laser_command(laser_ser, b"LASer:LDI", i_init_mA)
    data_io.log_event(log_path, f"Laser current set to {i_init_mA} mA — waiting 5 s to stabilize")
    print(f"[laser] Ramping to {i_init_mA} mA — waiting 5 s...")
    time.sleep(5)
    data_io.log_event(log_path, "Laser stabilized")


# --------------------------------------------------------------------------- #
#  Single sweep                                                                #
# --------------------------------------------------------------------------- #

def acquire_data(
    laser_ser,
    arduino_ser,
    csv_path: str,
    log_path: str,
    i_init_mA: float = config.I_INIT_mA,
    i_final_mA: float = config.I_FINAL_mA,
    step_size: float = config.CURRENT_STEP_SIZE,
    step_delay_s: float = config.STEP_DELAY_S,
    log_every_n_steps: int = 20,
    l2_position_deg: float | None = None,
) -> int:
    """
    Move λ/2 stage (if given), settle ADC, sweep laser current, record voltage.
    Returns total steps completed.
    """
    n_steps = int((i_final_mA - i_init_mA) / step_size)
    data_io.write_csv_header(csv_path, ["current_mA", "voltage_V"])

    # Move λ/2 stage
    if l2_position_deg is not None:
        data_io.log_event(log_path, f"Moving λ/2 stage to {l2_position_deg:.4f}°")
        print(f"[acquire] Moving λ/2 stage to {l2_position_deg:.4f}°")
        with K10CR1(port=config.KINESIS_PORT, verbose=False) as stage:
            stage.move_to(l2_position_deg)
        data_io.log_event(log_path, f"λ/2 stage reached {l2_position_deg:.4f}°")

    # ADC settle
    n_dummy = 6
    data_io.log_event(log_path, f"ADC settling — {n_dummy} dummy reads")
    arduino_ser.reset_input_buffer()
    for _ in range(n_dummy):
        utils.read_arduino_voltage(arduino_ser)
        time.sleep(0.1)
    data_io.log_event(log_path, "ADC settled")

    # Sweep
    data_io.log_event(log_path, f"Sweep started — {i_init_mA} → {i_final_mA} mA, {n_steps} steps, {step_delay_s} s/step")
    print(f"[acquire] Sweep: {i_init_mA} → {i_final_mA} mA ({n_steps} steps)")

    for i in range(n_steps):
        laser_ser.write(b"LASer:INC 1\n")
        time.sleep(step_delay_s)

        current_mA = i_init_mA + (i + 1) * step_size
        voltage    = utils.read_arduino_voltage(arduino_ser)
        data_io.append_csv_row(csv_path, [f"{current_mA:.2f}", f"{voltage:.5f}" if voltage is not None else "None"])

        if i % log_every_n_steps == 0:
            print(f"  Step {i+1}/{n_steps}: {current_mA:.2f} mA,  {voltage} V")

    data_io.log_event(log_path, f"Sweep complete — {n_steps} steps written to {os.path.basename(csv_path)}")
    print(f"[acquire] Done — {n_steps} steps saved to {csv_path}")
    return n_steps


def run_single_sweep(
    laser_ser,
    arduino_ser,
    laser_id: str,
    arduino_id: str,
    folder_name: str,
    run_index: int,
    experiment_message: str,
    i_init_mA: float,
    i_final_mA: float,
    p852_mW: float,
    l2_position_deg: float | None,
    adc_gain: int = config.ADC_GAIN,
):
    """Run one current sweep, saving to data_NN.csv, log_NN.txt, and params_NN.json."""
    csv_path   = os.path.join(folder_name, f"data_{run_index:02d}.csv")
    log_path   = os.path.join(folder_name, f"log_{run_index:02d}.txt")
    start_time = datetime.now()

    adc_range, adc_precision_mV = config.ADC_GAIN_TABLE[adc_gain]

    params = {
        "run_index":            run_index,
        "folder":               folder_name,
        "run_start":            start_time.strftime("%Y-%m-%d %H:%M:%S"),
        "experiment_message":   experiment_message or "(none)",
        "cell_temp":            config.CELL_T,
        "laser_id":             laser_id,
        "arduino_id":           arduino_id,
        "temp_3491":            get_laser_temperature(config.THERMISTOR_R),
        "i_init_mA":            i_init_mA,
        "i_final_mA":           i_final_mA,
        "current_step_mA":      config.CURRENT_STEP_SIZE,
        "step_delay_s":         config.STEP_DELAY_S,
        "p852_mW":              p852_mW,
        "l2_position_deg":      l2_position_deg,
        "adc_gain_code":        adc_gain,
        "adc_range":            adc_range,
        "adc_precision_mV_bit": adc_precision_mV,
        "data_file":            os.path.basename(csv_path),
        "log_file":             os.path.basename(log_path),
    }

    data_io.write_json_params(folder_name, params, filename=f"params_{run_index:02d}.json")

    data_io.log_open(
        log_path  = log_path,
        title     = "3491 nm CURRENT SWEEP EXPERIMENT",
        params    = {
            "Folder":               folder_name,
            "Laser device":         laser_id,
            "Arduino device":       arduino_id,
            "Experiment message":   experiment_message or "(none)",
            "Cell temperature":     f"{config.CELL_T} C",
            "3491 laser temperature": f"{get_laser_temperature(config.THERMISTOR_R):.3f} C",
            "3491 initial current": f"{i_init_mA} mA",
            "3491 final current":   f"{i_final_mA} mA",
            "Current step size":    f"{config.CURRENT_STEP_SIZE} mA",
            "Step delay":           f"{config.STEP_DELAY_S} s",
            "P852":                 f"{p852_mW} mW",
            "λ/2 position":         f"{l2_position_deg:.4f} deg" if l2_position_deg is not None else "not set",
            "ADC gain code":        adc_gain,
            "ADC range":            adc_range,
            "ADC precision":        f"{adc_precision_mV} mV/bit",
            "Data file":            os.path.basename(csv_path),
        },
        run_index = run_index,
    )

    print(f"\n[run {run_index:02d}] Starting — {os.path.basename(csv_path)} / {os.path.basename(log_path)}")

    try:
        data_io.log_event(log_path, f"ADC gain set to {adc_gain} ({adc_range}, {adc_precision_mV} mV/bit)")
        init_laser(laser_ser, log_path, i_init_mA)

        acquire_data(
            laser_ser       = laser_ser,
            arduino_ser     = arduino_ser,
            csv_path        = csv_path,
            log_path        = log_path,
            i_init_mA       = i_init_mA,
            i_final_mA      = i_final_mA,
            l2_position_deg = l2_position_deg,
        )

    finally:
        utils.write_laser_command(laser_ser, b"LASer:LDI", i_init_mA)
        data_io.log_event(log_path, f"Laser current reset to {i_init_mA} mA")
        data_io.log_close(log_path, start_time)
        print(f"[run {run_index:02d}] Done.")


# --------------------------------------------------------------------------- #
#  Full experiment                                                              #
# --------------------------------------------------------------------------- #

def run_experiment(
    experiment_message: str = "",
    data_root: str | None = None,
    laser_port: str = config.LASER_PORT,
    arduino_port: str = config.ARDUINO_PORT,
    i_init_mA: float = config.I_INIT_mA,
    i_final_mA: float = config.I_FINAL_mA,
    p852_mW: float = 23.7,
    l2_position_deg: float | list[float] | None = None,
    adc_gain: int = config.ADC_GAIN,
):
    """
    Run one or more current sweeps, one per l2_position_deg value.

    All sweeps share the same -spec folder. Files are numbered:
        data_01.csv / log_01.txt / params_01.json, ...
    """
    # Normalize l2 positions into a list
    if l2_position_deg is None:
        l2_positions = [None]
    elif isinstance(l2_position_deg, (int, float)):
        l2_positions = [float(l2_position_deg)]
    else:
        l2_positions = [float(v) for v in l2_position_deg]

    run_start = datetime.now()

    # 1. Create shared -spec folder
    folder_name = data_io.create_run_folder(
        experiment_message=experiment_message,
        data_root=data_root,
    )
    print(f"[run] Output folder: {folder_name}")

    # 2. Verify connections
    if not connections.check_laser_connection(laser_port):
        sys.exit(1)
    if not connections.check_arduino_connection(arduino_port):
        sys.exit(1)

    # 3. Open serial ports (stay open for the whole experiment)
    try:
        laser_ser   = serial.Serial(laser_port,   config.LASER_BAUD,   timeout=1, stopbits=1, parity="N")
        arduino_ser = serial.Serial(arduino_port, config.ARDUINO_BAUD, timeout=1)
        time.sleep(config.ARDUINO_BOOT_S)
        arduino_ser.reset_input_buffer()
        arduino_ser.write(b"START\n")
        utils.set_arduino_gain(arduino_ser, adc_gain)
        print(f"[run] Serial ports open — Arduino START sent, gain set to {adc_gain}")
    except serial.SerialException as e:
        print(f"[run] Failed to open serial ports: {e}")
        sys.exit(1)

    laser_id   = config.LASER_ID_EXPECTED
    arduino_id = config.ARDUINO_ID_EXPECTED

    try:
        for idx, l2_deg in enumerate(l2_positions, start=1):
            run_single_sweep(
                laser_ser          = laser_ser,
                arduino_ser        = arduino_ser,
                laser_id           = laser_id,
                arduino_id         = arduino_id,
                folder_name        = folder_name,
                run_index          = idx,
                experiment_message = experiment_message,
                i_init_mA          = i_init_mA,
                i_final_mA         = i_final_mA,
                p852_mW            = p852_mW,
                l2_position_deg    = l2_deg,
                adc_gain           = adc_gain,
            )

    finally:
        connections.close_experiment_connections(laser_ser, arduino_ser)
        total_s = int((datetime.now() - run_start).total_seconds())
        print(f"\n[run] All done — {len(l2_positions)} sweep(s) in {total_s // 60}m {total_s % 60}s")
        print(f"[run] Files in {folder_name}")


# --------------------------------------------------------------------------- #
#  CLI                                                                         #
# --------------------------------------------------------------------------- #

def _parse_args():
    parser = argparse.ArgumentParser(description="3491 nm laser current-sweep data acquisition")
    parser.add_argument("--message", "-m", default="",       help="Experiment description")
    parser.add_argument("--data-folder", "-d", default=None, dest="data_root",
                        help="Top-level output folder (default: current directory)")
    parser.add_argument("--laser-port",   default=config.LASER_PORT,
                        help=f"Laser serial port (default: {config.LASER_PORT})")
    parser.add_argument("--arduino-port", default=config.ARDUINO_PORT,
                        help=f"Arduino serial port (default: {config.ARDUINO_PORT})")
    parser.add_argument("--i-init",  type=float, default=config.I_INIT_mA,
                        help=f"Start current in mA (default: {config.I_INIT_mA})")
    parser.add_argument("--i-final", type=float, default=config.I_FINAL_mA,
                        help=f"End current in mA (default: {config.I_FINAL_mA})")
    parser.add_argument("--p852",    type=float, default=23.7,
                        help="852 nm reference power in mW (default: 23.7)")
    parser.add_argument("--l2-pos",  type=float, nargs="*", default=None,
                        dest="l2_position_deg",
                        help="λ/2 position(s) in degrees — pass one or many: --l2-pos 0 22.5 45 90")
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    run_experiment(
        experiment_message = "Experiment but scanning large numbers of l2_position_deg",
        data_root          = args.data_root,
        laser_port         = args.laser_port,
        arduino_port       = args.arduino_port,
        i_init_mA          = 72,
        i_final_mA         = 74,
        p852_mW            = 7.327,
        l2_position_deg    = [0 + 0.5*i for i in range(54)]
        #[config.KINESIS_HIGH_3491_POWER_POS, config.KINESIS_MID_3491_POWER_POS, config.KINESIS_LOW_3491_POWER_POS, 35.5]
    )