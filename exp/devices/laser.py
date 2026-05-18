from . import config
import time
import serial


#A class use to control the Arroyo Laser controller
class Laser:

    def __init__(
        self,
        port=config.LASER3491_PORT,
        i_init_mA=config.I_INIT_mA,
        step_mA = config.LASER_STEP_mA,
        voltage_limit_V=config.LASER_VOLTAGE_LIMIT_V,
        current_limit_mA=config.LASER_CURRENT_LIMIT_mA,
        name="laser"):
        
        self.port = port
        self.name = name

        self.current_mA = i_init_mA
        self.voltage_limit_V = voltage_limit_V
        self.current_limit_mA = current_limit_mA        
        self.step_mA = step_mA
        
        self.laser_serial = serial.Serial(port,
                                      config.LASER_BAUD,
                                      timeout=1,
                                      stopbits=1,
                                      parity="N")
        
        # Set laser limits, and steps
        self.set_laser_limits(laser_voltage_limit_V=voltage_limit_V,
                            laser_current_limit_mA=current_limit_mA)
        self.set_step_mA(step_mA)
        
        # Set initial current
        self.set_current_mA(i_init_mA)

        


    def set_laser_limits(self,
                         laser_voltage_limit_V=config.LASER_VOLTAGE_LIMIT_V,
                         laser_current_limit_mA=config.LASER_CURRENT_LIMIT_mA):
        
        """Set laser safety limits"""

        # Set forward voltage limit
        self.write_command(b"LASer:LIMit:LDV",
                                 laser_voltage_limit_V,
                                 print_setup=True)
        self.voltage_limit_V = laser_voltage_limit_V
        
        # Set current limit
        self.write_command(b"LASer:LIMit:LDI",
                                 laser_current_limit_mA,
                                 print_setup=True)
        self.current_limit_mA = laser_current_limit_mA


    def set_step_mA(self,
                    laser_step=config.LASER_STEP_mA):
        """Set laser step size"""
        self.write_command(b"LASer:STEP",
                                 laser_step,
                                 print_setup=True)
        self.step_mA = laser_step


    def set_current_mA(self, i_mA: float):
        """Set laser current in miliAmperes"""
        #Has to have the form of ab.xy
        self.write_command(b"LASer:LDI", i_mA)
        print(f"[laser] Ramping to {i_mA} mA — waiting 5 s...")
        #Wait 5 second to stabilize the temperature
        time.sleep(5)

        self.current_mA = i_mA

    def increase_current_one_step(self, step_delay_s):
        self.write_command(b"LASer:INC", 1)
        time.sleep(step_delay_s)
    
    def get_current_mA(self):
        pass

    def close(self):
        """Close the underlying serial connection."""
        self.laser_serial.close()

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