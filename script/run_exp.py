#!/usr/bin/env python3
"""
run_exp.py — 3491 nm laser current-sweep experiment.

For each λ/2 position in `l2_positions`, runs a full laser current sweep
(i_init_mA → i_final_mA) and records the requested Arduino ADC channels
per step.

Output:
    data/data-experiment/<MMDDYYYY>/<MMDDYYYY>-<HHMMSS>/
        ├── data_01.csv         — current_mA, ch{a}_V, ch{b}_V, ...
        ├── params_01.json
        ├── log_01.txt
        ├── data_02.csv
        ├── params_02.json
        ├── log_02.txt
        ...

Edit parameters in main() and run:
    python run_experiment.py
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
#  Single sweep                                                                #
# --------------------------------------------------------------------------- #

def acquire_data(
    laser: Laser,
    arduino: ArduinoADS1115,
    stage: K10CR1 | None,
    csv_path: str,
    log_path: str,
    channels: list[int],
    i_init_mA: float,
    i_final_mA: float,
    step_size_mA: float,
    step_delay_s: float,
    l2_position_deg: float | None,
    log_every_n_steps: int = 20,
) -> int:
    """
    Move λ/2 stage to position (if given), settle ADC, sweep laser current,
    record one row per step containing the requested ADC channels.

    Returns total steps completed.
    """
    n_steps = int((i_final_mA - i_init_mA) / step_size_mA)

    csv_columns = ["current_mA"] + [f"ch{c}_V" for c in channels]
    data_io.write_csv_header(csv_path, csv_columns)

    # Move λ/2 stage if requested
    if l2_position_deg is not None and stage is not None:
        data_io.log_event(log_path, f"Moving λ/2 stage to {l2_position_deg:.4f}°")
        print(f"[acquire] Moving λ/2 stage to {l2_position_deg:.4f}°")
        stage.move_to(l2_position_deg)
        data_io.log_event(log_path, f"λ/2 stage reached {stage.get_position():.4f}°")

    # ADC settle
    n_dummy = 6
    data_io.log_event(log_path, f"ADC settling — {n_dummy} dummy reads on channels {channels}")
    arduino.reset_input_buffer()
    for _ in range(n_dummy):
        for c in channels:
            arduino.read_channel(c)
        time.sleep(0.1)
    data_io.log_event(log_path, "ADC settled")

    # Sweep
    data_io.log_event(log_path, f"Sweep started — {i_init_mA} → {i_final_mA} mA, {n_steps} steps of {step_size_mA} mA, {step_delay_s} s/step, channels={channels}")
    print(f"[acquire] Sweep: {i_init_mA} → {i_final_mA} mA ({n_steps} steps), channels = {channels}")

    for i in range(n_steps):
        # Step the laser current by one increment (size = LASer:STEP × 0.01 mA)
        laser.increase_current_one_step(step_delay_s)
        #laser.write_laser_command(b"LASer:INC", 1)
        #time.sleep(step_delay_s)

        current_mA = i_init_mA + (i + 1) * step_size_mA
        readings   = [arduino.read_channel(c) for c in channels]

        row = [f"{current_mA:.2f}"] + [f"{v:.5f}" if v is not None else "" for v in readings]
        data_io.append_csv_row(csv_path, row)

        if i % log_every_n_steps == 0:
            ch_str = ",  ".join(f"ch{c} = {v} V" for c, v in zip(channels, readings))
            print(f"  Step {i+1:4d}/{n_steps}: {current_mA:6.2f} mA,  {ch_str}")

    data_io.log_event(log_path, f"Sweep complete — {n_steps} steps written to {os.path.basename(csv_path)}")
    print(f"[acquire] Done — {n_steps} steps saved to {csv_path}")
    return n_steps


# --------------------------------------------------------------------------- #
#  One sweep + its own log/params/data files                                   #
# --------------------------------------------------------------------------- #

def run_single_sweep(
    laser: Laser,
    arduino: ArduinoADS1115,
    stage: K10CR1 | None,
    folder_name: str,
    run_index: int,
    experiment_message: str,
    channels: list[int],
    i_init_mA: float,
    i_final_mA: float,
    step_size_mA: float,
    step_delay_s: float,
    pi852_mW: float,
    pf852_mW: float,
    l2_position_deg: float | None,
    laser_thermistor_R: float,
    adc_gains: dict[int, int],
):
    """Run one current sweep, saving to data_NN.csv, log_NN.txt, params_NN.json."""
    csv_path   = os.path.join(folder_name, f"data_{run_index:02d}.csv")
    log_path   = os.path.join(folder_name, f"log_{run_index:02d}.txt")
    start_time = datetime.now()

    gain_info_per_channel = {
        c: {"code":         adc_gains[c],
            "range":        config.ADC_GAIN_TABLE[adc_gains[c]][0],
            "precision_mV": config.ADC_GAIN_TABLE[adc_gains[c]][1]}
        for c in channels
    }
    laser_temperature_C = get_3491_laser_temp(laser_thermistor_R)

    # params.json
    data_io.write_json_params(
        folder_name,
        {
            "run_index":             run_index,
            "folder":                folder_name,
            "run_start":             start_time.strftime("%Y-%m-%d %H:%M:%S"),
            "experiment_message":    experiment_message or "(none)",
            "laser_id":              config.LASER_ID_EXPECTED,
            "arduino_id":            config.ARDUINO_ID_EXPECTED,
            "cell_temp_C":           config.CELL_T,
            "laser_thermistor_R_Ohm":laser_thermistor_R,
            "laser_temperature_C":   laser_temperature_C,
            "channels":              channels,
            "i_init_mA":             i_init_mA,
            "i_final_mA":            i_final_mA,
            "current_step_mA":       step_size_mA,
            "step_delay_s":          step_delay_s,
            "pi852_mW":              pi852_mW,
            "pf852_mW":              pf852_mW,
            "l2_position_deg":       l2_position_deg,
            "adc_gains":             {f"ch{c}": adc_gains[c] for c in channels},
            "adc_gain_info":         {f"ch{c}": gain_info_per_channel[c] for c in channels},
            "data_file":             os.path.basename(csv_path),
            "log_file":              os.path.basename(log_path),
        },
        filename=f"params_{run_index:02d}.json",
    )

    # log header — build per-channel gain lines into the params dict
    log_params = {
        "Folder":                 folder_name,
        "Laser device":           config.LASER_ID_EXPECTED,
        "Arduino device":         config.ARDUINO_ID_EXPECTED,
        "Experiment message":     experiment_message or "(none)",
        "Cell temperature":       f"{config.CELL_T} C",
        "Laser thermistor R":     f"{laser_thermistor_R} Ohm",
        "3491 laser temperature": f"{laser_temperature_C:.3f} C",
        "Channels":               channels,
        "3491 initial current":   f"{i_init_mA} mA",
        "3491 final current":     f"{i_final_mA} mA",
        "Current step size":      f"{step_size_mA} mA",
        "Step delay":             f"{step_delay_s} s",
        "P852_in":                f"{pi852_mW} mW",
        "P852_out":               f"{pf852_mW} mW",
        "λ/2 position":           f"{l2_position_deg:.4f} deg" if l2_position_deg is not None else "not set",
    }
    for c in channels:
        info = gain_info_per_channel[c]
        log_params[f"ADC ch{c} gain"] = f"code {info['code']} ({info['range']}, {info['precision_mV']} mV/bit)"
    log_params["Data file"] = os.path.basename(csv_path)

    data_io.log_open(
        log_path  = log_path,
        title     = "3491 nm CURRENT SWEEP EXPERIMENT",
        params    = log_params,
        run_index = run_index,
    )

    print(f"\n[run {run_index:02d}] Starting — {os.path.basename(csv_path)} / {os.path.basename(log_path)}")

    try:
        acquire_data(
            laser           = laser,
            arduino         = arduino,
            stage           = stage,
            csv_path        = csv_path,
            log_path        = log_path,
            channels        = channels,
            i_init_mA       = i_init_mA,
            i_final_mA      = i_final_mA,
            step_size_mA    = step_size_mA,
            step_delay_s    = step_delay_s,
            l2_position_deg = l2_position_deg,
        )
    finally:
        # Reset laser to initial current for the next sweep (5 s stabilize)
        try:
            laser.set_current_mA(i_init_mA)
            data_io.log_event(log_path, f"Laser current reset to {i_init_mA} mA")
        except Exception as e:
            data_io.log_event(log_path, f"Laser reset failed: {e}", level="ERROR")
        data_io.log_close(log_path, start_time)
        print(f"[run {run_index:02d}] Done.")


# --------------------------------------------------------------------------- #
#  Full experiment                                                             #
# --------------------------------------------------------------------------- #

def run_experiment(
    experiment_message: str = "",
    data_root: str = str(PROJECT_ROOT / "data" / "data-experiment") ,
    laser_port: str = config.LASER3491_PORT,
    arduino_port: str = config.ARDUINO_PORT,
    kinesis_port: str = config.KINESIS_PORT,
    channels: list[int] | None = None,
    i_init_mA: float = config.I_INIT_mA,
    i_final_mA: float = config.I_FINAL_mA,
    step_size_mA: float = config.CURRENT_STEP_SIZE,
    step_delay_s: float = config.STEP_DELAY_S,
    pi852_mW: float = 27.7,
    pf852_mW: float = 1.0,
    l2_positions: float | list[float] | None = None,
    laser_thermistor_R: float = config.THERMISTOR_R,
    adc_gains: dict[int, int] = None,
):
    """
    Run one or more laser current sweeps, one per λ/2 stage position.

    All sweeps share the same output folder; files are numbered
    data_NN.csv / params_NN.json / log_NN.txt.

    Output: <data_root>/<MMDDYYYY>/<MMDDYYYY>-<HHMMSS>/

    Args:
        experiment_message:  Free-text label written to each per-sweep log.
        data_root:           Top-level folder (default: 'data/data-experiment').
        laser_port:          Arroyo 3491 serial port.
        arduino_port:        Arduino serial port.
        kinesis_port:        K10CR1 serial port (only opened if any l2 position is given).
        channels:            ADS1115 channels to record per step. Default [1, 3].
        i_init_mA:           Sweep start current (also the "rest" current between sweeps).
        i_final_mA:          Sweep end current.
        step_size_mA:        Current increment per step. Must match the Arroyo's
                             LASer:STEP setting (config.LASER_STEP_mA × 0.01 mA),
                             otherwise the recorded current and the actual current
                             will drift apart.
        step_delay_s:        Seconds between each laser increment.
        p852_mW:             852 nm reference power, recorded as metadata only.
        l2_positions:        Single position, list, or None (no stage movement).
        laser_thermistor_R:  Thermistor resistance (Ω); fed through `get_3491_laser_temp`.
        adc_gains:           Per-channel ADS1115 gain. dict of {channel: code}.
                             Default uses config.ADC_GAIN_DICT. Valid codes:
                             0, 1, 2, 4, 8, 16.
    """
    # --- Validate channels ---
    if channels is None:
        channels = [1, 3]
    if not channels:
        raise ValueError("`channels` must contain at least one channel.")
    invalid = [c for c in channels if c not in (0, 1, 2, 3)]
    if invalid:
        raise ValueError(f"Invalid channel(s) {invalid}. Must be from 0, 1, 2, 3.")

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

    # --- Normalize l2 positions into a list ---
    if l2_positions is None:
        l2_list = [None]
    elif isinstance(l2_positions, (int, float)):
        l2_list = [float(l2_positions)]
    else:
        l2_list = [float(v) for v in l2_positions]

    run_start = datetime.now()

    # 1. Create run folder
    date_str    = run_start.strftime("%m%d%Y")
    time_str    = run_start.strftime("%H%M%S")
    folder_name = os.path.join(data_root, date_str, f"{date_str}-{time_str}")
    os.makedirs(folder_name, exist_ok=True)
    print(f"[run] Output folder: {folder_name}")
    print(f"[run] Plan: {len(l2_list)} sweep(s), channels = {channels}, "
          f"current {i_init_mA} → {i_final_mA} mA in {step_size_mA} mA steps")

    # 2. Open hardware + run sweeps, with guaranteed cleanup on any error
    arduino = None
    stage   = None
    laser   = None
    try:
        # Arduino
        arduino = ArduinoADS1115(port=arduino_port, adc_channels=channels)
        arduino.identify()
        arduino.set_adc_gain(adc_gains)
        arduino.start()
        print(f"[run] Arduino START sent. Per-channel gains: {adc_gains}")

        # K10CR1 (only if we'll actually move it)
        if any(p is not None for p in l2_list):
            stage = K10CR1(port=kinesis_port, verbose=False)
            print(f"[run] K10CR1 connected on {kinesis_port}")

        # Laser (sets limits, step, and ramps to i_init_mA with a 5 s stabilize)
        laser = Laser(port=laser_port, i_init_mA=i_init_mA)
        print(f"[run] 3491 Laser initialized on {laser_port} at {i_init_mA} mA")

        # 3. One sweep per λ/2 position
        for idx, l2_deg in enumerate(l2_list, start=1):
            run_single_sweep(
                laser              = laser,
                arduino            = arduino,
                stage              = stage,
                folder_name        = folder_name,
                run_index          = idx,
                experiment_message = experiment_message,
                channels           = channels,
                i_init_mA          = i_init_mA,
                i_final_mA         = i_final_mA,
                step_size_mA       = step_size_mA,
                step_delay_s       = step_delay_s,
                pi852_mW           = pi852_mW,
                pf852_mW           = pf852_mW,
                l2_position_deg    = l2_deg,
                laser_thermistor_R = laser_thermistor_R,
                adc_gains          = adc_gains,
            )

    finally:
        # 4. Cleanup — each step independent so one failure doesn't block the others.
        if stage is not None:
            try:
                stage.close()
                print("[run] K10CR1 connection closed")
            except Exception as e:
                print(f"[run] K10CR1 close failed: {e}")

        if arduino is not None:
            try:
                arduino.stop()
            except Exception as e:
                print(f"[run] Arduino STOP failed: {e}")
            try:
                arduino.close()
                print("[run] Arduino connection closed")
            except Exception as e:
                print(f"[run] Arduino close failed: {e}")

        if laser is not None:
            try:
                laser.close()
                print("[run] 3491 Laser connection closed")
            except Exception as e:
                print(f"[run] Laser close failed: {e}")

        total_s = int((datetime.now() - run_start).total_seconds())
        print(f"\n[run] All done — {len(l2_list)} sweep(s) in {total_s // 60}m {total_s % 60}s")
        print(f"[run] Files in {folder_name}")


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #

def main():
    # ====== EDIT THESE PARAMETERS ======================================== #
    experiment_message  = "Experiment scanning multiple l2_position_deg values"
    data_root           = str(PROJECT_ROOT / "data" / "data-experiment") 
    channels            = [1, 3]

    # Laser sweep
    i_init_mA           = 72.0
    i_final_mA          = 74.0
    step_size_mA        = config.CURRENT_STEP_SIZE
    #step_delay_s        = config.STEP_DELAY_S
    step_delay_s = 2

    # Stage positions to visit (one full current sweep per position)
    l2_positions        = [21, 25, 30, 35, 40, 45, 50, 55]
    # l2_positions        = [40] * 1    # 30.0, 30.2, ..., 34.0
    # l2_positions      = [config.KINESIS_HIGH_3491_POWER_POS,
    #                      config.KINESIS_MID_3491_POWER_POS,
    #                      config.KINESIS_LOW_3491_POWER_POS]

    # Metadata
    pi852_mW            = 17.3
    pf852_mW            = 0.123
    laser_thermistor_R  = config.THERMISTOR_R

    # Hardware
    laser_port          = config.LASER3491_PORT
    arduino_port        = config.ARDUINO_PORT
    kinesis_port        = config.KINESIS_PORT
    # Per-channel ADC gain: {channel: gain_code}. Valid codes: 0,1,2,4,8,16.
    # Gain code → (range_str, precision_mV_per_bit)
    #ADC_GAIN_TABLE = {
    #0:  ("±6.144 V", 0.1875),
    #1:  ("±4.096 V", 0.125),
    #2:  ("±2.048 V", 0.0625),
    #4:  ("±1.024 V", 0.03125),
    #8:  ("±0.512 V", 0.015625),
    #16: ("±0.256 V", 0.0078125),
    #}
    adc_gains           = {1: 16, 3: 16}
    # ===================================================================== #

    run_experiment(
        experiment_message = experiment_message,
        data_root          = data_root,
        laser_port         = laser_port,
        arduino_port       = arduino_port,
        kinesis_port       = kinesis_port,
        channels           = channels,
        i_init_mA          = i_init_mA,
        i_final_mA         = i_final_mA,
        step_size_mA       = step_size_mA,
        step_delay_s       = step_delay_s,
        pi852_mW           = pi852_mW,
        pf852_mW           = pf852_mW,
        l2_positions       = l2_positions,
        laser_thermistor_R = laser_thermistor_R,
        adc_gains          = adc_gains,
    )


if __name__ == "__main__":
    main()