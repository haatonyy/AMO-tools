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




def load_data(file:str, skiprows=1):
    data = np.loadtxt(file, delimiter=',', skiprows=skiprows)
    return data[:, 0], data[:,1]


def load_param(file:str):
    return json.load(open(file, 'r'))