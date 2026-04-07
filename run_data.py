import os
import serial
import time
import csv
from datetime import datetime
import sys


###TODO: MAKE THIS FILES WORK

experiment_message = "3491 attenuated, P852=1.770, I852=95.6mA"
I_init_mA = 72
I_final_mA=74
steps_range = int((I_final_mA- I_init_mA)/0.01)

laser_port = "/dev/ttyUSB0"
arduino_port = "/dev/ttyACM1"





def write_value(ser, command_root, value, print_setup=False):
    command = command_root + bytes(" {value}\n".format(value=value), "utf-8")
    #print(command)
    ser.write(command)
    ser.read(len(command)-1)
    if print_setup==True:
        ser.write(command_root+b"?\n")
        print(ser.readline())

def get_voltage(arduino_ser):
    arduino_ser.write(b"READ\n")
    line = arduino_ser.readline().decode(errors="ignore").strip()
    try:
        voltage = float(line)
    except:
        return None
    #print(f"Received from Arduino: {line}")
    return voltage


def create_data_folder():
    # --- 1. GENERATE DYNAMIC FOLDER NAME ---
    start_time = datetime.now()
    date_str = start_time.strftime("%m%d%Y")    # 04052026
    time_str = start_time.strftime("%H%M%S")    # 15:53:04 -> 155304
    base_name = f"{date_str}-{time_str}"

    run_id = 1
    #create parent folder
    parent_folder=date_str
    if not os.path.exists(parent_folder):
        os.makedirs(parent_folder)
    folder_name = f"{parent_folder}/{base_name}-{run_id:02d}"
    # Increment ID if folder exists
    while os.path.exists(folder_name):
        run_id += 1
        folder_name = f"{parent_folder}/{base_name}-{run_id:02d}"

    os.makedirs(folder_name)
    csv_path = os.path.join(folder_name, "data.csv")
    log_path = os.path.join(folder_name, "log.txt")
    return csv_path, log_path


def hardware_initialization():
    # --- 2. HARDWARE INITIALIZATION AND ID CHECK ---
    try:
        laser_ser = serial.Serial(laser_port, 38400, timeout=1, stopbits=1, parity="N")
        arduino_ser = serial.Serial(arduino_port, 9600, timeout=1)
        time.sleep(2) # Wait for Arduino reset
    except Exception as e:
        print(f"Error opening serial ports: {e}")
        sys.exit()
    # Check Laser ID
    laser_ser.write(b'*IDN?\n')
    laser_id = laser_ser.readline().decode('utf-8').strip()
    if "Arroyo 4205-DR 110802133" not in laser_id:
        print(f"Wrong Laser! Found: {laser_id}")
        laser_ser.close()
        arduino_ser.close()
        sys.exit()

    # Check Arduino ID
    arduino_ser.reset_input_buffer()
    arduino_ser.write(b"IDENTIFY\n")
    arduino_id = arduino_ser.readline().decode('utf-8').strip()

    if arduino_id != "3491_PD_01":
        print(f"Wrong Arduino! Found: '{arduino_id}'")
        laser_ser.close()
        arduino_ser.close()
        sys.exit()

    arduino_ser.write(b"START\n")
    print(f"Verification Successful: {arduino_id} connected.")

def laser_initialization(): 
    # --- 4. LASER INITIALIZATION ---
    #set the limits for the laser
    write_value(laser_ser, b'LASer:LIMit:LDV', 3.2, print_setup=True )
    write_value(laser_ser, b'LASer:LIMit:LDI', 100, print_setup=True)
    write_value(laser_ser, b"LASer:STEP", 1, print_setup=True)
    print("3491nm Laser Limits Is Set!")

    write_value(laser_ser, b'LASer:LDI', I_init_mA)
    time.sleep(5)
    print("3491nm Laser is initialized")








# --- 5. Log Initial file ---
with open(log_path, "w") as log:
    log.write(f"EXPERIMENT LOG\n")
    log.write(f"Folder: {folder_name}\n")
    log.write(f"Start Time: {start_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.write(f"Laser Device: {laser_id}\n")
    log.write(f"Arduino Device: {arduino_id}\n")
    log.write(f"Experiment Message: {experiment_message}\n")
    log.write("-" * 30 + "\n")

with open(log_path, "a") as log:
    log.write(f"EXPERIMENT PARAMETERS\n")
    log.write(f"3491 Initial Current: {I_init_mA} mA\n")
    log.write(f"3491 Final Current: {I_final_mA} mA\n")

# --- 5. DATA ACQUISITION ---
with open(csv_path, "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["current_mA", "voltage_V"])
    
    arduino_ser.reset_input_buffer()
    
    for i in range(steps_range):    
        laser_ser.write(b"LASer:INC 1\n")
        time.sleep(0.8)
        current_mA = I_init_mA + (i+1) * 0.01
        voltage = get_voltage(arduino_ser)
        
        writer.writerow([f"{current_mA:.2f}", f"{voltage}"])
        if i % 20 == 0:
            print(f"Step {i}/{steps_range}: {current_mA:.2f}mA, {voltage}V")

# --- 6. FINALIZE & LOG END TIME ---
end_time = datetime.now()
duration = end_time - start_time  # Result is a timedelta object

# Format the duration for the log
total_seconds = int(duration.total_seconds())
minutes = total_seconds // 60
seconds = total_seconds % 60
duration_str = f"{minutes}m {seconds}s"
write_value(laser_ser, b'LASer:LDI', I_init_mA) # Reset laser

with open(log_path, "a") as log:
    log.write(f"End Time: {end_time.strftime('%Y-%m-%d %H:%M:%S')}\n")
    log.write(f"Total Run Time: {duration_str}\n")
    log.write(f"Status: Completed Successfully\n")

arduino_ser.write(b"STOP\n")
arduino_ser.close()
laser_ser.close()
print(f"Done. Files saved in {folder_name}")


def __main__():
    pass