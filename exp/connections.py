# connections.py — Device verification and serial port management

import time
import serial
import serial.tools.list_ports
import sys

import exp.devices.config as config


# --------------------------------------------------------------------------- #
#  Individual connection checks (quick open/close — safe to call before run)  #
# --------------------------------------------------------------------------- #

def check_laser_connection(port: str = config.LASER3491_PORT) -> bool:
    """
    Open the laser port briefly, query its identity, and close it.

    Returns:
        True if the correct laser is found, False otherwise.
    """
    try:
        with serial.Serial(port, config.LASER_BAUD, timeout=1, stopbits=1, parity="N") as ser:
            time.sleep(0.5)
            ser.write(b"*IDN?\n")
            laser_id = ser.readline().decode("utf-8").strip()
    except serial.SerialException as e:
        print(f"[Laser] Could not open port {port}: {e}")
        return False

    if config.LASER_ID_EXPECTED not in laser_id:
        print(f"[Laser] Wrong device! Found: {laser_id}")
        return False

    print(f"[Laser] OK — {laser_id}")
    return True


def check_arduino_connection(port: str = config.ARDUINO_PORT) -> bool:
    """
    Open the Arduino port briefly, query its identity, and close it.

    Returns:
        True if the correct Arduino is found, False otherwise.
    """
    try:
        with serial.Serial(port, config.ARDUINO_BAUD, timeout=1) as ser:
            time.sleep(1)
            ser.reset_input_buffer()
            ser.write(b"IDENTIFY\n")
            arduino_id = ser.readline().decode("utf-8").strip()
    except serial.SerialException as e:
        print(f"[Arduino] Could not open port {port}: {e}")
        return False

    if arduino_id != config.ARDUINO_ID_EXPECTED:
        print(f"[Arduino] Wrong device! Found: '{arduino_id}'")
        return False

    print(f"[Arduino] OK — {arduino_id}")
    return True


def check_kinesis_connection(port: str = config.KINESIS_PORT) -> bool:
    """
    Check that the port at *port* matches the expected K10CR1 stage by
    inspecting the OS-level port description and hardware ID — no serial
    communication needed.

    Checks:
        description : must contain "Kinesis K10CR1 Rotary Stage"
        hwid        : must contain "SER=55239734"

    Returns:
        True if both checks pass, False otherwise.
    """
    all_ports = {p.device: p for p in serial.tools.list_ports.comports()}

    if port not in all_ports:
        print(f"[Kinesis] Port {port} not found in system port list.")
        return False

    info = all_ports[port]

    desc_ok = "Kinesis K10CR1 Rotary Stage" in (info.description or "")
    hwid_ok = "SER=55239734" in (info.hwid or "")

    if not desc_ok:
        print(f"[Kinesis] Wrong description! Found: '{info.description}'")
    if not hwid_ok:
        print(f"[Kinesis] Wrong serial number in HWID! Found: '{info.hwid}'")

    if desc_ok and hwid_ok:
        print(f"[Kinesis] OK — {info.description} | {info.hwid}")
        return True

    return False


def verify_all_connections(
    laser_port: str = config.LASER3491_PORT,
    arduino_port: str = config.ARDUINO_PORT,
    kinesis_port: str = config.KINESIS_PORT,
) -> bool:
    """
    Run all three connection checks. Returns True only if every device passes.
    """
    laser_ok   = check_laser_connection(laser_port)
    arduino_ok = check_arduino_connection(arduino_port)
    kinesis_ok = check_kinesis_connection(kinesis_port)
    return laser_ok and arduino_ok and kinesis_ok


# --------------------------------------------------------------------------- #
#  Close live connections after an experiment run                              #
# --------------------------------------------------------------------------- #

def close_experiment_connections(laser_ser, arduino_ser):
    """Send STOP to Arduino and close both serial ports."""
    try:
        arduino_ser.write(b"STOP\n")
    finally:
        arduino_ser.close()
        laser_ser.close()
    print("[connections] Serial ports closed.")

