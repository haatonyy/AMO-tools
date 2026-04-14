# utils.py — Low-level serial helpers and load data

import serial.tools.list_ports
import time
import numpy as np
import json


def list_available_ports():
    """Print all connected serial ports (excluding 'n/a' devices)."""
    ports = serial.tools.list_ports.comports()
    found = [p for p in ports if p.description != "n/a"]
    if not found:
        print("No serial ports found.")
        return

    for port in found:
        print(f"Device:      {port.device}")
        print(f"Name:        {port.name}")
        print(f"Description: {port.description}")
        print(f"HWID:        {port.hwid}")
        print("-" * 40)


def write_laser_command(ser, command_root: bytes, value, print_setup: bool = False):
    """
    Send a value to a laser command register.

    Args:
        ser:          Open serial.Serial for the laser.
        command_root: Command prefix as bytes, e.g. b'LASer:LDI'.
        value:        Numeric value to write.
        print_setup:  If True, query the register back and print the result.
    """
    command = command_root + bytes(f" {value}\n", "utf-8")
    ser.write(command)
    ser.read(len(command) - 1)          # consume echo

    if print_setup:
        ser.write(command_root + b"?\n")
        print(ser.readline())




def read_arduino_voltage(arduino_ser) -> float | None:
    """
    Request a voltage reading from the Arduino photodetector.

    Returns:
        Voltage as a float, or None if the response could not be parsed.
    """
    arduino_ser.write(b"READ\n")
    line = arduino_ser.readline().decode(errors="ignore").strip()
    try:
        return float(line)
    except ValueError:
        return None

# Gain codes for ADS1115:
#   0  → GAIN_TWOTHIRDS  ±6.144 V  (0.1875    mV/bit)
#   1  → GAIN_ONE        ±4.096 V  (0.125     mV/bit)
#   2  → GAIN_TWO        ±2.048 V  (0.0625    mV/bit)  ← default
#   4  → GAIN_FOUR       ±1.024 V  (0.03125   mV/bit)
#   8  → GAIN_EIGHT      ±0.512 V  (0.015625  mV/bit)
#  16  → GAIN_SIXTEEN    ±0.256 V  (0.0078125 mV/bit)
 
def set_arduino_gain(arduino_ser, gain_code: int):
    """
    Set the ADS1115 gain from Python.
 
    Args:
        arduino_ser: Open serial.Serial for the Arduino.
        gain_code:   One of 0, 1, 2, 4, 8, 16.
    """
    valid = {0, 1, 2, 4, 8, 16}
    if gain_code not in valid:
        raise ValueError(f"Invalid gain code {gain_code}. Must be one of {valid}")
    arduino_ser.write(f"GAIN {gain_code}\n".encode())
    response = arduino_ser.readline().decode(errors="ignore").strip()
    print(f"[arduino] Gain set: {response}")


def load_data(file:str, skiprows=1):
    data = np.loadtxt(file, delimiter=',', skiprows=skiprows)
    return data[:, 0], data[:,1]


def load_param(file:str):
    return json.load(open(file, 'r'))

    

