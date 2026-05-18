# tec.py - a class to control the TEC

import serial
import config

class TemperatureController:

    def __init__(self, port: str, init_R: float, name: str = None):
        self.port = port
        self.name = name

        self.Rhigh = 0.0
        self.Rlow = 0.0
        self.R_Ohm = init_R

        self.tec_serial = serial.Serial(
            port,
            config.LASER_BAUD,
            timeout=1,
            stopbits=1,
            parity="N",
        )

    def set_thermistor_R(self, R_Ohm: float):
        self.R_Ohm = R_Ohm
        self.write_command(b"TEC:T", R_Ohm, print_setup=True)

    def set_Rhigh(self, R_Ohm: float):
        self.Rmax_Ohm = R_Ohm
        self.write_command(b"TEC:LIMit:THI", R_Ohm, print_setup=True)

    def set_Rmin(self, R_Ohm: float):
        self.Rmin_Ohm = R_Ohm
        self.write_command(b"TEC:LIMit:TLO", R_Ohm, print_setup=True)

    def set_step_size(self, step_size: int):
        pass

    def read_command(self, command_root: bytes, print_setup: bool = False):
        ser = self.tec_serial
        query = command_root + b"?\n"

        ser.write(query)

        # Read first line. This may be echo or echo+value.
        response = ser.readline().decode(errors="ignore").strip()

        # Case 1: response is like "TEC:T?10000"
        if "?" in response and response != query.decode(errors="ignore").strip():
            value = response.split("?", 1)[1]

        # Case 2: response is just echo, like "TEC:T?"
        else:
            response = ser.readline().decode(errors="ignore").strip()
            value = response.split("?", 1)[1] if "?" in response else response

        if print_setup:
            print(f"[tec] {command_root.decode()} = {value}")

        return value

    def write_command(self, command_root: bytes, value, print_setup: bool = False):
        command = command_root + bytes(f" {value}\n", "utf-8")

        ser = self.tec_serial
        ser.write(command)

        # consume echo
        ser.readline()

        if print_setup:
            self.read_command(command_root, print_setup=True)