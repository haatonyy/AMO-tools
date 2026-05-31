#!/usr/bin/env python3
"""
run_no_save.py — Like run_exp.py, but writes nothing to disk.

For live monitoring, dry runs, and bench tuning where you want to see
the data flow but don't want to pollute the data folder.

Output: terminal only. No CSVs, no params.json, no log files, no folder
created. Hardware lifecycle (Arduino, K10CR1, Laser) is identical to
run_exp.py — opens, configures, sweeps, then closes everything cleanly
even on error.

Edit parameters in main() and run:
    python run_no_save.py
"""

import time
from datetime import datetime

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from exp.devices import config
from exp.devices.arduino import ArduinoADS1115
from exp.devices.k10cr1 import K10CR1
from exp.devices.laser import Laser


# --------------------------------------------------------------------------- #
#  Single sweep                                                                #
# --------------------------------------------------------------------------- #

def acquire_data(
    laser: Laser,
    arduino: ArduinoADS1115,
    stage: K10CR1 | None,
    channels: list[int],
    i_init_mA: float,
    i_final_mA: float,
    step_size_mA: float,
    step_delay_s: float,
    l2_position_deg: float | None,
    log_every_n_steps: int = 1,
) -> int:
    """
    Move λ/2 stage (if given), settle ADC, sweep laser current, print one
    line per step. Nothing written to disk.

    Returns total steps completed.
    """
    n_steps = int((i_final_mA - i_init_mA) / step_size_mA)

    # Move λ/2 stage if requested
    if l2_position_deg is not None and stage is not None:
        print(f"[acquire] Moving λ/2 stage to {l2_position_deg:.4f}°")
        stage.move_to(l2_position_deg)
        print(f"[acquire] λ/2 stage reached {stage.get_position():.4f}°")

    # ADC settle
    n_dummy = 6
    print(f"[acquire] ADC settling — {n_dummy} dummy reads on channels {channels}")
    arduino.reset_input_buffer()
    for _ in range(n_dummy):
        for c in channels:
            arduino.read_channel(c)
        time.sleep(0.1)

    # Sweep
    print(f"[acquire] Sweep: {i_init_mA} → {i_final_mA} mA ({n_steps} steps), channels = {channels}")
    print(f"  {'step':>5}  {'mA':>7}   " + "   ".join(f"ch{c}_V".rjust(10) for c in channels))

    for i in range(n_steps):
        laser.write_laser_command(b"LASer:INC", 1)
        time.sleep(step_delay_s)

        current_mA = i_init_mA + (i + 1) * step_size_mA
        readings   = [arduino.read_channel(c) for c in channels]

        if i % log_every_n_steps == 0:
            vals_str = "   ".join(f"{v:10.5f}" if v is not None else f"{'None':>10}" for v in readings)
            print(f"  {i+1:5d}  {current_mA:7.2f}   {vals_str}")

    print(f"[acquire] Done — {n_steps} steps completed (not saved)")
    return n_steps


# --------------------------------------------------------------------------- #
#  One sweep                                                                   #
# --------------------------------------------------------------------------- #

def run_single_sweep(
    laser: Laser,
    arduino: ArduinoADS1115,
    stage: K10CR1 | None,
    run_index: int,
    channels: list[int],
    i_init_mA: float,
    i_final_mA: float,
    step_size_mA: float,
    step_delay_s: float,
    l2_position_deg: float | None,
):
    """Run one current sweep. Saves nothing."""
    start_time = datetime.now()
    print(f"\n[run {run_index:02d}] Starting (no-save) at {start_time.strftime('%H:%M:%S')}")

    try:
        acquire_data(
            laser           = laser,
            arduino         = arduino,
            stage           = stage,
            channels        = channels,
            i_init_mA       = i_init_mA,
            i_final_mA      = i_final_mA,
            step_size_mA    = step_size_mA,
            step_delay_s    = step_delay_s,
            l2_position_deg = l2_position_deg,
        )
    finally:
        # Reset laser current for next sweep (5 s stabilize)
        try:
            laser.set_current_mA(i_init_mA)
            print(f"[run {run_index:02d}] Laser current reset to {i_init_mA} mA")
        except Exception as e:
            print(f"[run {run_index:02d}] Laser reset failed: {e}")
        dur = (datetime.now() - start_time).total_seconds()
        print(f"[run {run_index:02d}] Done in {dur:.1f} s")


# --------------------------------------------------------------------------- #
#  Full experiment                                                             #
# --------------------------------------------------------------------------- #

def run_experiment(
    laser_port: str = config.LASER3491_PORT,
    arduino_port: str = config.ARDUINO_PORT,
    kinesis_port: str = config.KINESIS_PORT,
    channels: list[int] | None = None,
    i_init_mA: float = config.I_INIT_mA,
    i_final_mA: float = config.I_FINAL_mA,
    step_size_mA: float = config.CURRENT_STEP_SIZE,
    step_delay_s: float = config.STEP_DELAY_S,
    l2_positions: float | list[float] | None = None,
    adc_gains: dict[int, int] = None,
):
    """
    Run one or more laser current sweeps without saving anything.

    Same hardware lifecycle as run_exp.run_experiment — opens, configures,
    sweeps, and closes everything cleanly even on error.

    Args:
        laser_port:    Arroyo 3491 serial port.
        arduino_port:  Arduino serial port.
        kinesis_port:  K10CR1 serial port (only opened if any l2 position given).
        channels:      ADS1115 channels to record per step. Default [1, 3].
        i_init_mA:     Sweep start current.
        i_final_mA:    Sweep end current.
        step_size_mA:  Current increment per step.
        step_delay_s:  Seconds between each laser increment.
        l2_positions:  Single position, list, or None (no stage movement).
        adc_gains:     Per-channel gain dict {channel: code}. Default uses
                       config.ADC_GAIN_DICT.
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

    # --- Normalize l2 positions ---
    if l2_positions is None:
        l2_list = [None]
    elif isinstance(l2_positions, (int, float)):
        l2_list = [float(l2_positions)]
    else:
        l2_list = [float(v) for v in l2_positions]

    run_start = datetime.now()

    print("=" * 70)
    print("  NO-SAVE MODE — terminal output only, nothing written to disk")
    print("=" * 70)
    print(f"[run] Plan: {len(l2_list)} sweep(s), channels = {channels}, "
          f"current {i_init_mA} → {i_final_mA} mA in {step_size_mA} mA steps")

    # Open hardware + run sweeps, with guaranteed cleanup on any error
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

        # Laser
        laser = Laser(port=laser_port, i_init_mA=i_init_mA)
        print(f"[run] 3491 Laser initialized on {laser_port} at {i_init_mA} mA")

        # One sweep per λ/2 position
        for idx, l2_deg in enumerate(l2_list, start=1):
            run_single_sweep(
                laser           = laser,
                arduino         = arduino,
                stage           = stage,
                run_index       = idx,
                channels        = channels,
                i_init_mA       = i_init_mA,
                i_final_mA      = i_final_mA,
                step_size_mA    = step_size_mA,
                step_delay_s    = step_delay_s,
                l2_position_deg = l2_deg,
            )

    finally:
        # Cleanup — each step independent so one failure doesn't block the others.
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
        print("[run] (no files were saved)")


# --------------------------------------------------------------------------- #
#  Entry point                                                                 #
# --------------------------------------------------------------------------- #

def main():
    # ====== EDIT THESE PARAMETERS ======================================== #
    channels            = [1, 3]

    # Laser sweep
    i_init_mA           = 72.0
    i_final_mA          = 74.0
    step_size_mA        = config.CURRENT_STEP_SIZE
    step_delay_s        = config.STEP_DELAY_S

    # Stage positions to visit (one full current sweep per position)
    l2_positions        = [30]
    # l2_positions      = [config.KINESIS_HIGH_3491_POWER_POS,
    #                      config.KINESIS_MID_3491_POWER_POS,
    #                      config.KINESIS_LOW_3491_POWER_POS]

    # Hardware
    laser_port          = config.LASER3491_PORT
    arduino_port        = config.ARDUINO_PORT
    kinesis_port        = config.KINESIS_PORT

    # Per-channel ADC gain: {channel: gain_code}. Valid codes: 0,1,2,4,8,16.
    adc_gains           = {1: 8, 3: 8}
    # ===================================================================== #

    run_experiment(
        laser_port   = laser_port,
        arduino_port = arduino_port,
        kinesis_port = kinesis_port,
        channels     = channels,
        i_init_mA    = i_init_mA,
        i_final_mA   = i_final_mA,
        step_size_mA = step_size_mA,
        step_delay_s = step_delay_s,
        l2_positions = l2_positions,
        adc_gains    = adc_gains,
    )


if __name__ == "__main__":
    main()