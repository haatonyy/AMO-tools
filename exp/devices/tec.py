# tec.py - a class to control the TEC

class TemperatureController:

    def __init__(
            self,
            port: str,
            init_R: float,
            name: str = None):
        
        self.port = port
        self.name = name

        self.Rmin_Ohm = 0.0
        self.Rmax_Ohm = 0.0

    def set_thermistor_R(R_Ohm: float):
        pass

    def set_Rmax(R_Ohm: float):
        pass

    def set_Rmin(R_Ohm: float):
        pass

    



    
    
    
    def write_command(self, command_root: bytes, value, print_setup: bool = False):
        """
        Send a value to a laser command register.

        Args:
            command_root: Command prefix as bytes, e.g. b'LASer:LDI'.
            value:        Numeric value to write.
            print_setup:  If True, query the register back and print the
                          readback in a clean one-line format.
        """
        command = command_root + bytes(f" {value}\n", "utf-8")

        ser = self.laser_serial
        ser.write(command)
        ser.read(len(command) - 1)          # consume echo

        if print_setup:
            ser.write(command_root + b"?\n")
            response = ser.readline().decode(errors="ignore").strip()
            # Device echoes the query then appends the value, e.g.
            # "LASer:LIMit:LDV?3.2". Strip the echoed prefix.
            readback = response.split("?", 1)[1] if "?" in response else response
            print(f"[laser] {command_root.decode()} = {readback}")
