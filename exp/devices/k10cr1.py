# k10cr1.py — Thorlabs K10CR1 rotary stage driver (wraps pylablib KinesisMotor)
#
# Supports one or two K10CR1 units via a shared driver instance.
# Usage:
#   from devices.k10cr1 import K10CR1
#   stage = K10CR1(config.KINESIS_PORT)
#   stage.move_to(45.0)
#   print(stage.get_position())

import time
from pylablib.devices import Thorlabs

from . import config


class K10CR1:
    """
    Thin, friendly wrapper around pylablib's KinesisMotor for K10CR1 stages.

    Each instance controls one physical stage. Instantiate multiple objects
    for multiple stages (no NDSP server required for single-machine use).
    """

    STEPS_PER_DEG = 136533     # encoder steps per degree (K10CR1 spec)

    def __init__(
        self,
        port: str = config.KINESIS_PORT,
        initialize_to_home: bool = False,
        verbose: bool = True,
    ):
        """
        Open connection to the stage and optionally home it.

        Args:
            port:               Serial port (e.g. '/dev/ttyUSB5').
            initialize_to_home: If True, home the stage on startup.
            verbose:            Print settings and status on init.
        """
        self.port = port
        self.verbose = verbose

        self.motor = Thorlabs.KinesisMotor(port, scale=136533)
        time.sleep(0.5)

        if verbose:
            print(f"[K10CR1] Connected on {port}")
            self._print_scale_info()

        if initialize_to_home:
            print("[K10CR1] Homing...")
            self.home()

        self.print_status()

    # ----------------------------------------------------------------------- #
    #  Info / diagnostics                                                      #
    # ----------------------------------------------------------------------- #

    def _print_scale_info(self):
        scale       = self.motor.get_scale()
        scale_units = self.motor.get_scale_units()
        print(f"[K10CR1] Scale (pos, vel, accel): {scale}")
        print(f"[K10CR1] Scale units: {scale_units}")
        if scale_units == "step":
            print(f"[K10CR1] ** Step scale not autodetected — using {self.STEPS_PER_DEG} steps/deg")

    def print_full_settings(self):
        """Print the full pylablib settings dict for this stage."""
        print(self.motor.get_settings())

    def print_jog_parameters(self):
        print("[K10CR1] Jog params:", self.motor.get_jog_parameters())

    def print_status(self):
        print(f"[K10CR1:{self.port}] Status: {self.motor.get_status()}")

    def get_stage_name(self) -> str:
        """Return the stage model string (autodetected or user-supplied)."""
        return self.motor.get_stage()

    # ----------------------------------------------------------------------- #
    #  Position                                                                #
    # ----------------------------------------------------------------------- #

    def get_position(self) -> float:
        """Return current position in degrees (physical units)."""
        return float(self.motor.get_position())

    def is_moving(self) -> bool:
        return self.motor.is_moving()

    def wait_move(self):
        """Block until the current move finishes."""
        self.motor.wait_move()

    def wait_for_status(self, status: str):
        self.motor.wait_for_status(status=status, enabled=True)

    # ----------------------------------------------------------------------- #
    #  Motion                                                                  #
    # ----------------------------------------------------------------------- #

    def move_by(self, degrees: float):
        """
        Relative move by *degrees* and block until complete.

        Args:
            degrees: Angle to rotate (positive = clockwise, negative = CCW).
        """
        self.motor.move_by(degrees)
        self.motor.wait_move()
        if self.verbose:
            print(f"[K10CR1] Moved by {degrees}° → now at {self.get_position():.4f}°")

    def move_to(self, degrees: float):
        """
        Absolute move to *degrees* and block until complete.

        Args:
            degrees: Target angle in degrees.
        """
        self.motor.move_to(degrees)
        self.motor.wait_move()
        if self.verbose:
            print(f"[K10CR1] Moved to {degrees}° → position: {self.get_position():.4f}°")

    # ----------------------------------------------------------------------- #
    #  Homing                                                                  #
    # ----------------------------------------------------------------------- #

    def home(self):
        """
        Home the stage and block until complete.

        Uses force=True so homing always runs even if the stage thinks
        it is already homed.
        """
        self.motor.home(sync=True, force=True)
        self.motor.wait_for_home()
        print(f"[K10CR1] Homed. Position: {self.get_position():.4f}°")

    def is_homed(self) -> bool:
        return self.motor.is_homed()

    # ----------------------------------------------------------------------- #
    #  Context manager (with-statement support)                                #
    # ----------------------------------------------------------------------- #

    def close(self):
        """Release the serial connection."""
        self.motor.close()
        print(f"[K10CR1:{self.port}] Connection closed.")

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()


# --------------------------------------------------------------------------- #
#  Multi-stage factory (mirrors the original NDSP driver pattern)             #
# --------------------------------------------------------------------------- #

def open_stages(devices: list[tuple[str, dict]]) -> dict[str, K10CR1]:
    """
    Open multiple K10CR1 stages from a list of (name, kwargs) pairs.

    Args:
        devices: e.g. [("HWP", {"port": "/dev/ttyUSB5"}),
                        ("QWP", {"port": "/dev/ttyUSB6"})]

    Returns:
        dict mapping name → K10CR1 instance.

    Example:
        stages = open_stages([
            ("HWP", {"port": "/dev/ttyUSB5"}),
            ("QWP", {"port": "/dev/ttyUSB6"}),
        ])
        stages["HWP"].move_to(45.0)
    """
    stages = {}
    for name, kwargs in devices:
        print(f"[k10cr1] Opening stage '{name}' with {kwargs}")
        stages[name] = K10CR1(**kwargs)
    print("[k10cr1] All stages initialized.")
    return stages


def close_stages(stages: dict[str, K10CR1]):
    """Close all stages returned by open_stages()."""
    for name, stage in stages.items():
        print(f"[k10cr1] Closing '{name}'")
        stage.close()