# config.py — Hardware constants and experiment defaults

# --- Serial Ports ---
LASER3491_PORT   = "/dev/ttyUSB1"
ARDUINO_PORT = "/dev/ttyACM1"
KINESIS3491_PORT = "/dev/ttyUSB0"
KINESIS852_PORT = "/dev/ttyUSB0"


# --- Device Identity Strings ---
LASER_ID_EXPECTED   = "Arroyo 4205-DR 110802133"
ARDUINO_ID_EXPECTED = "3491_PD_01"

# --- Serial Settings ---
LASER_BAUD   = 38400
ARDUINO_BAUD = 9600
KINESIS_BAUD = 115200

# --- Vacuum Cell Parameters ---
CELL_T = 59.9

# --- Laser Parameters ---
THERMISTOR_T0 = 25
THERMISTOR_R0 = 10000
THERMISTOR_B =  3390
THERMISTOR_R = 8.37e3
LASER_VOLTAGE_LIMIT_V = 3.2     # LASer:LIMit:LDV
LASER_CURRENT_LIMIT_mA = 100    # LASer:LIMit:LDI
LASER_STEP_mA = 1               # LASer:STEP (1 = 0.01 mA per INC command)

I_INIT_mA  = 72.0               # Starting current
I_FINAL_mA = 74.0               # Ending current
CURRENT_STEP_SIZE = 0.01        # mA per step

# --- Timing ---
STEP_DELAY_S     = 1.5          # Pause between steps (seconds)
ARDUINO_BOOT_S   = 1            # Wait after opening Arduino serial

# --- Kinesis Rotary Stage ---
#KINESIS_STEPS_PER_DEG = 136533
#KINESIS_HIGH_3491_POWER_POS = -4.0 #0.78-0.79V
#KINESIS_MID_3491_POWER_POS = 18.5 #0.4
#KINESIS_LOW_3491_POWER_POS = 31.5 #0.08V

# --- ADS1115 ADC ---
# Gain code → (range_str, precision_mV_per_bit)
ADC_GAIN_TABLE = {
    0:  ("±6.144 V", 0.1875),
    1:  ("±4.096 V", 0.125),
    2:  ("±2.048 V", 0.0625),
    4:  ("±1.024 V", 0.03125),
    8:  ("±0.512 V", 0.015625),
    16: ("±0.256 V", 0.0078125),
}

ADC_GAIN_DICT = {
    0: 1,   #channel 0
    1: 1,   #channel 1
    2: 1,   #channel 2
    3: 1    #channel 3
}   # default: all channels at GAIN_ONE (±4.096 V, 0.125 mV/bit)