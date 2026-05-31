#!/usr/bin/env python3
"""
run_calibration.py — Sweep the λ/2 (K10CR1) waveplate and record one or more
Arduino ADC channels.

Moves to start_deg, steps toward end_deg in move_to() increments, then returns
to start_deg when done.

Output:
    data/data-calibrated/<MMDDYYYY>/<MMDDYYYY>-<HHMMSS>/
        ├── data_01.csv     — first repeat: pos, ch{a}_V, ch{b}_V, ...
        ├── data_02.csv     — second repeat (if n_repeats > 1)
        ├── ...
        ├── params.json     — single, shared across repeats
        └── log.txt         — single, shared across repeats

Edit parameters in main() and run:
    python run_calibration.py
"""

import os
import time
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
PROJECT_ROOT = Path(__file__).resolve().parent.parent 

import exp.data_io as data_io
from exp.devices import config
from exp.devices.arduino import ArduinoADS1115
from exp.devices.k10cr1 import K10CR1
from exp.devices.laser import Laser
from exp.science import get_3491_laser_temp


# --------------------------------------------------------------------------- #
#  Sweep                                                                       #
# --------------------------------------------------------------------------- #

def sweep_and_record(
    stage: K10CR1,
    arduino: ArduinoADS1115,
    csv_path: str,
    log_path: str,
    start_deg: float,
    end_deg: float,
    step_deg: float,
    settle_s: float,
    channels: list[int],
    run_index: int = 1,
    n_repeats: int = 1,
) -> list[tuple]:
    """
    Move to start_deg, step toward end_deg with move_to(), record the
    requested ADC channels at each step.

    The laser is assumed to already be at its target current (set at
    construction in run_l2_scan); this function does not touch it.

    Args:
        run_index, n_repeats: used only for the print/log prefix so the user
                              can see "repeat 2/5" during multi-run scans.

    Returns list of (position_deg, ch_a_V, ch_b_V, ...) — one entry per
    channel in `channels`, in the order given.
    """
    n_steps     = int(abs(end_deg - start_deg) / step_deg)
    direction   = 1.0 if end_deg >= start_deg else -1.0
    signed_step = direction * abs(step_deg)

    tag = f"[repeat {run_index}/{n_repeats}] " if n_repeats > 1 else ""

    csv_columns = ["l2_pos_deg"] + [f"ch{c}_V" for c in channels]
    data_io.write_csv_header(csv_path, csv_columns)

    # Move to start
    data_io.log_event(log_path, f"{tag}Moving to start position: {start_deg}°")
    stage.move_to(start_deg)
    data_io.log_event(log_path, f"{tag}Reached start position: {stage.get_position():.4f}°")

    # ADC settle
    n_dummy = 5
    data_io.log_event(log_path, f"{tag}ADC settling — {n_dummy} dummy reads on channels {channels}")
    arduino.reset_input_buffer()
    for _ in range(n_dummy):
        for c in channels:
            arduino.read_channel(c)
        time.sleep(0.1)
    data_io.log_event(log_path, f"{tag}ADC settled")

    # Sweep
    data_io.log_event(log_path, f"{tag}Sweep started — {start_deg}° → {end_deg}°, {n_steps} steps of {signed_step:+.3f}°, settle={settle_s} s, channels={channels}")
    print(f"[scan_l2] {tag}Sweeping {start_deg}° → {end_deg}° ({n_steps} steps), channels = {channels}")

    results = []
    for i in range(n_steps):
        target = start_deg + (i + 1) * signed_step
        stage.move_to(target)
        if settle_s > 0:
            time.sleep(settle_s)

        pos      = stage.get_position()
        readings = [arduino.read_channel(c) for c in channels]

        row = [f"{pos:.4f}"] + [f"{v}" for v in readings]
        data_io.append_csv_row(csv_path, row)
        results.append((pos, *readings))

        ch_str = ",  ".join(f"ch{c} = {v} V" for c, v in zip(channels, readings))
        print(f"  {tag}Step {i+1:3d}/{n_steps}: pos = {pos:8.4f}°,  {ch_str}")

    data_io.log_event(log_path, f"{tag}Sweep complete — {n_steps} points written to {os.path.basename(csv_path)}")
    return results


# --------------------------------------------------------------------------- #
#  Full scan                                                                   #
# --------------------------------------------------------------------------- #

def run_l2_scan(
    start_deg: float = 0.0,
    end_deg: float = 90.0,
    step_deg: float = 3.0,
    settle_s: float = 0.3,
    channels: list[int] | None = None,
    n_repeats: int = 1,
    laser_3491_port: str = config.LASER3491_PORT,
    laser_current_mA: float = config.I_INIT_mA,
    laser_thermistor_R: float = config.THERMISTOR_R,
    experiment_message: str = "calibrated",
    data_root: str = str(PROJECT_ROOT / "data" / "data-calibrated") ,
    arduino_port: str = config.ARDUINO_PORT,
    kinesis_port: str = config.KINESIS_PORT,
    adc_gains: dict[int, int] = None,
):
    """
    Full λ/2 scan: move to start, sweep to end, return to start when done.

    Drives the 3491 laser to `laser_current_mA` at startup, then sweeps the
    K10CR1 waveplate `n_repeats` times and records the requested Arduino
    ADC channels.

    Output:
        <data_root>/<MMDDYYYY>/<MMDDYYYY>-<HHMMSS>/
            ├── data_01.csv     ← first repeat
            ├── data_02.csv     ← second repeat (if n_repeats > 1)
            ├── ...
            ├── params.json     ← single, shared across repeats
            └── log.txt         ← single, shared across repeats

    Args:
        start_deg:           Absolute start angle (degrees).
        end_deg:             Absolute end angle (degrees).
        step_deg:            Step size in degrees (positive; direction inferred).
        settle_s:            Settle time after each move before reading voltage.
        channels:            ADS1115 channels to record at each step. Default
                             [1, 3]. Each channel becomes its own CSV column
                             named "ch{n}_V". Must be a subset of {0,1,2,3};
                             current Arduino firmware supports {1, 3}.
        n_repeats:           Number of times to repeat the full sweep, each
                             saved as data_{i:02d}.csv. Default 1.
        laser_3491_port:     Serial port for the Arroyo 3491 laser controller.
        laser_current_mA:    3491 laser drive current; the laser ramps to this
                             value at startup (with a ~5 s stabilization wait).
        laser_thermistor_R:  Measured thermistor resistance (Ω) used to derive
                             the laser temperature via `get_3491_laser_temp`.
                             Recorded in params.json/log alongside the derived
                             temperature.
        experiment_message:  Free-text label written to the log
                             (default: 'calibrated').
        data_root:           Top-level folder for output data
                             (default: 'data/data-calibrated').
        arduino_port:        Arduino serial port.
        kinesis_port:        K10CR1 serial port.
    """
    # --- Validate ---
    if channels is None:
        channels = [1, 3]
    if not channels:
        raise ValueError("`channels` must contain at least one channel.")
    invalid = [c for c in channels if c not in (0, 1, 2, 3)]
    if invalid:
        raise ValueError(f"Invalid channel(s) {invalid}. Must be from 0, 1, 2, 3.")
    if n_repeats < 1:
        raise ValueError(f"`n_repeats` must be >= 1, got {n_repeats}.")

    # --- Normalize adc_gains ---
    if adc_gains is None:
        adc_gains = dict(config.ADC_GAIN_DICT)
    missing = [c for c in channels if c not in adc_gains]
    if missing:
        raise ValueError(f"adc_gains missing entries for channels {missing}")
    valid_codes = set(config.ADC_GAIN_TABLE.keys())
    for c in channels:
        if adc_gains[c] not in valid_codes:
            raise ValueError(f"Invalid gain code {adc_gains[c]} for ch{c}. Valid: {sorted(valid_codes)}")
    gain_info_per_channel = {
        c: {"code":         adc_gains[c],
            "range":        config.ADC_GAIN_TABLE[adc_gains[c]][0],
            "precision_mV": config.ADC_GAIN_TABLE[adc_gains[c]][1]}
        for c in channels
    }

    start_time = datetime.now()
    n_steps    = int(abs(end_deg - start_deg) / step_deg)

    # 1. Create run folder: <data_root>/<MMDDYYYY>/<MMDDYYYY>-<HHMMSS>/
    date_str    = start_time.strftime("%m%d%Y")
    time_str    = start_time.strftime("%H%M%S")
    folder_name = os.path.join(data_root, date_str, f"{date_str}-{time_str}")
    os.makedirs(folder_name, exist_ok=True)

    log_path = os.path.join(folder_name, "log.txt")
    print(f"[scan_l2] Output folder: {folder_name}")

    # Derive temperature once from the thermistor reading
    laser_temperature_C = get_3491_laser_temp(laser_thermistor_R)

    # 2. Open log with header + params block
    params = {
        "Folder":             folder_name,
        "Date":               date_str,
        "Time":               time_str,
        "Arduino port":       arduino_port,
        "Kinesis port":       kinesis_port,
        "Laser 3491 port":    laser_3491_port,
        "Experiment message": experiment_message or "(none)",
        "Scan start":         f"{start_deg} deg",
        "Scan end":           f"{end_deg} deg",
        "Step size":          f"{step_deg} deg",
        "Steps":              n_steps,
        "Total sweep":        f"{n_steps * step_deg:.2f} deg",
        "Settle time":        f"{settle_s} s",
        "Channels":           channels,
        "Repeats":            n_repeats,
        "Laser current":      f"{laser_current_mA} mA",
        "Laser thermistor R": f"{laser_thermistor_R} Ohm",
        "Laser temperature":  f"{laser_temperature_C} C",
    }
    # Per-channel gain info
    for c in channels:
        info = gain_info_per_channel[c]
        params[f"ADC ch{c} gain"] = f"code {info['code']} ({info['range']}, {info['precision_mV']} mV/bit)"
    params["Data files"] = f"data_01.csv … data_{n_repeats:02d}.csv" if n_repeats > 1 else "data_01.csv"

    data_io.log_open(log_path, "λ/2 WAVEPLATE POSITION SCAN", params)

    # 3. Open hardware + sweep, with guaranteed cleanup on any error
    arduino    = None
    stage      = None
    laser_3491 = None
    try:
        #Arduino System
        arduino = ArduinoADS1115(port=arduino_port, adc_channels=channels)
        arduino.identify()
        data_io.log_event(log_path, f"Arduino verified: {config.ARDUINO_ID_EXPECTED}")
        arduino.set_adc_gain(adc_gains)
        arduino.start()
        data_io.log_event(log_path, f"Arduino START sent. Per-channel gains: {adc_gains}")

        #K10CR1 system
        stage = K10CR1(port=kinesis_port, verbose=False)
        data_io.log_event(log_path, f"K10CR1 connected on {kinesis_port}")

        #Laser system
        laser_3491 = Laser(port=laser_3491_port, i_init_mA=laser_current_mA)
        data_io.log_event(log_path, f"3491 Laser initialized on {laser_3491_port} at {laser_current_mA} mA")


        # 4. Write params.json (only after hardware checks out)
        data_io.write_json_params(folder_name, {
            "experiment_message":    experiment_message,
            "folder":                folder_name,
            "date":                  date_str,
            "time":                  time_str,
            "run_start":             start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "arduino_port":          arduino_port,
            "kinesis_port":          kinesis_port,
            "laser_3491_port":       laser_3491_port,
            "start_deg":             start_deg,
            "end_deg":               end_deg,
            "step_deg":              step_deg,
            "n_steps":               n_steps,
            "n_repeats":             n_repeats,
            "settle_s":              settle_s,
            "channels":              channels,
            "laser_current_mA":      laser_current_mA,
            "laser_thermistor_R_Ohm":laser_thermistor_R,
            "laser_temperature_C":   laser_temperature_C,
            "adc_gains":             {f"ch{c}": adc_gains[c] for c in channels},
            "adc_gain_info":         {f"ch{c}": gain_info_per_channel[c] for c in channels},
            "arduino_id":            config.ARDUINO_ID_EXPECTED,
        })

        # 5. Run the sweep n_repeats times, one CSV per repeat
        for i in range(1, n_repeats + 1):
            csv_path = os.path.join(folder_name, f"data_{i:02d}.csv")
            data_io.log_event(log_path, f"=== Repeat {i}/{n_repeats} starting → {os.path.basename(csv_path)} ===")
            sweep_and_record(
                stage     = stage,
                arduino   = arduino,
                csv_path  = csv_path,
                log_path  = log_path,
                start_deg = start_deg,
                end_deg   = end_deg,
                step_deg  = step_deg,
                settle_s  = settle_s,
                channels  = channels,
                run_index = i,
                n_repeats = n_repeats,
            )
            data_io.log_event(log_path, f"=== Repeat {i}/{n_repeats} complete ===")

    finally:
        # 6. Cleanup — runs even if open/identify/sweep failed.
        # Each step is independent so one failure doesn't block the others.

        if stage is not None:
            try:
                data_io.log_event(log_path, f"Returning to start position: {start_deg}°")
                stage.move_to(start_deg)
                data_io.log_event(log_path, f"Returned to {stage.get_position():.4f}°")
            except Exception as e:
                data_io.log_event(log_path, f"Stage return-to-start failed: {e}", level="ERROR")
            try:
                stage.close()
                data_io.log_event(log_path, "K10CR1 connection closed")
            except Exception as e:
                data_io.log_event(log_path, f"K10CR1 close failed: {e}", level="ERROR")

        if arduino is not None:
            try:
                arduino.stop()
            except Exception as e:
                data_io.log_event(log_path, f"Arduino STOP failed: {e}", level="ERROR")
            try:
                arduino.close()
                data_io.log_event(log_path, "Arduino connection closed")
            except Exception as e:
                data_io.log_event(log_path, f"Arduino close failed: {e}", level="ERROR")

        if laser_3491 is not None:
            try:
                laser_3491.close()
                data_io.log_event(log_path, "3491 Laser connection closed")
            except Exception as e:
                data_io.log_event(log_path, f"Laser close failed: {e}", level="ERROR")

        data_io.log_close(log_path, start_time)
        print(f"[scan_l2] Done. Files saved in {folder_name}")


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #

def main():
    # ====== EDIT THESE PARAMETERS ======================================== #
    start_deg           = 0.0
    end_deg             = 90.0
    step_deg            = 3.0
    settle_s            = 0.1
    channels            = [1, 3]
    n_repeats           = 1                    # number of full sweeps; data_01.csv … data_NN.csv
    laser_current_mA    = 80.00      # 3491 laser drive current
    laser_thermistor_R  = config.THERMISTOR_R    # thermistor R for temperature derivation
    experiment_message  = "calibrated"
    data_root           = str(PROJECT_ROOT / "data" / "data-calibrated") 
    arduino_port        = config.ARDUINO_PORT
    kinesis_port        = config.KINESIS_PORT
    laser_3491_port     = config.LASER3491_PORT
    # Per-channel gain: dict of {channel: gain_code}. Valid codes: 0,1,2,4,8,16.
    # Example: {1: 1, 3: 4} → ch1 at GAIN_ONE (±4.096V), ch3 at GAIN_FOUR (±1.024V)
    #ADC_GAIN_TABLE = {
    #0:  ("±6.144 V", 0.1875),
    #1:  ("±4.096 V", 0.125),
    #2:  ("±2.048 V", 0.0625),
    #4:  ("±1.024 V", 0.03125),
    #8:  ("±0.512 V", 0.015625),
    #16: ("±0.256 V", 0.0078125),
    #}
    adc_gains           = {1: 1, 3: 8}
    # ===================================================================== #

    run_l2_scan(
        start_deg           = start_deg,
        end_deg             = end_deg,
        step_deg            = step_deg,
        settle_s            = settle_s,
        channels            = channels,
        n_repeats           = n_repeats,
        laser_current_mA    = laser_current_mA,
        laser_thermistor_R  = laser_thermistor_R,
        experiment_message  = experiment_message,
        data_root           = data_root,
        arduino_port        = arduino_port,
        kinesis_port        = kinesis_port,
        laser_3491_port     = laser_3491_port,
        adc_gains           = adc_gains,
    )


if __name__ == "__main__":
    main()