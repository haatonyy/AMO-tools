time.sleep(1)
laser_ser = serial.Serial(laser_port, 38400, timeout=1, stopbits=1, parity="N")

#check if we are connected to the right device
laser_ser.write(b'*IDN?\n')
ser_no = laser_ser.readline()
if ser_no != b'*IDN?Arroyo 4205-DR 110802133 v2.01a 211\n':
    print("Wrong laser device")
    laser_ser.close()

#set the limits for the laser
write_value(laser_ser, b'LASer:LIMit:LDV', 3.2, print_setup=True )
write_value(laser_ser, b'LASer:LIMit:LDI', 100, print_setup=True)
write_value(laser_ser, b"LASer:STEP", 1, print_setup=True)
print("Laser setup complete")

#set the initial current to 72 mA, after that wait for 10s for the laser's temperature to stabilize
I_init_mA = 71
write_value(laser_ser, b'LASer:LDI', I_init_mA)
time.sleep(5)

I_final_mA=74
steps_range = int((I_final_mA- I_init_mA)/0.01)
print("Laser initialized")



#open the serial connection to the arduino and reset the input buffer
#check if you are open the right Arduino
arduino_ser = serial.Serial(arduino_port, 9600, timeout=1)
time.sleep(2)
arduino_ser.reset_input_buffer()
arduino_ser.write(b"IDENTIFY\n")
arduino_id = arduino_ser.readline().decode('utf-8').strip()
if arduino_id == "3491_PD_01":
    #wait for 2 seconds for the connection to be established
    #throw away the first reading
    print(f"Success! {"3491_PD_01"} found.")
    arduino_ser.reset_input_buffer()
    get_voltage(arduino_ser)
    print("Arduino initialized")
else:
    laser_ser.close()
    arduino_ser.close()
    print("Wrong ardruino device")



#data acquisition loop: increase the current by 0.01 mA every second for 100 seconds, and record the voltage at each step
with open("bg.csv", "w", newline="") as f:
    writer = csv.writer(f)
    writer.writerow(["current_mA", "voltage_V"])
    #increase the current by 0.01 mA every second for 100 seconds
    for i in range(400):    
        laser_ser.write(b"LASer:INC 1\n")
        time.sleep(0.8)
        current_mA = I_init_mA + (i+1) * 0.01
        voltage = get_voltage(arduino_ser)
       #print(f"Current: {current_mA:.2f} mA, Voltage: {voltage} V")
        writer.writerow([f"{current_mA:.2f}", f"{voltage}"])
write_value(laser_ser, b'LASer:LDI', I_init_mA)
print("Data acquisition Complete")

arduino_ser.close()
laser_ser.close()
