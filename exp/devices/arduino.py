from . import config
import serial
import time

class ArduinoADS1115:
    def __init__(self,
                 port=config.ARDUINO_PORT,
                 adc_channels = [1,3]):
        

        self.port = port
        self.adc_channels = adc_channels
        self.serial = serial.Serial(port, config.ARDUINO_BAUD, timeout=4)
        
        time.sleep(1)
        self.serial.reset_input_buffer()

    def start(self):
        """Start Steaming Arduino"""
        self.serial.write(b"START\n")

    def stop(self):
        """Stop Steaming Arduino"""
        self.serial.write(b"STOP\n")

    def close(self):
        """Close the underlying serial connection."""
        self.serial.close()

    def identify(self):
        """Identify Arduino"""
        self.reset_input_buffer()
        self.serial.write(b"IDENTIFY\n")
        arduino_id = self.serial.readline().decode("utf-8").strip()
        if arduino_id != config.ARDUINO_ID_EXPECTED:
            self.serial.close()
            raise RuntimeError(f"Wrong Arduino! Found: '{arduino_id}'")
        return True
    
    def reset_input_buffer(self):
        """Reset Input buffer"""
        self.serial.reset_input_buffer()


    def read_channel(self, channel: int) -> float | None:
        """
        Request a voltage reading from a single Arduino ADC channel.

        The Arduino must implement a `READCH<n>` command for the requested
        channel. Today that means channels 1 and 3.

        Args:
            channel: ADC channel number, one of {0, 1, 2, 3} (ADS1115 inputs).

        Returns:
            Voltage as a float, or None if the response could not be parsed.
        """
        if channel not in (0, 1, 2, 3):
            raise ValueError(f"Invalid channel {channel}. Must be one of 0, 1, 2, 3.")
        self.reset_input_buffer()
        self.serial.write(f"READCH{channel}\n".encode())
        line = self.serial.readline().decode(errors="ignore").strip()
        try:
            return float(line)
        except ValueError:
            return None


    #TODO: rewrite to allow all channels 
    def read_all_channels(self) -> tuple[float | None, float | None]:
        """
        Request a reading from both Arduino ADC channels in one round-trip.

        The Arduino responds with "v_ch1,v_ch3" (newline-terminated):
        channel A1 (signal) followed by channel A3 (error).

        Returns:
            (ch1_V, ch3_V) as floats, or (None, None) if parsing fails.
        """
        self.reset_input_buffer()
        self.serial.write(b"READBOTH\n")
        line = self.serial.readline().decode(errors="ignore").strip()
        #print("line:", line)
        parts = line.split(",")
        #print("parts:", parts)
        if len(parts) != 2:
            return None, None
        try:
            return float(parts[0]), float(parts[1])
        except ValueError:
            return None, None

    # Gain codes for ADS1115:
    #   0  → GAIN_TWOTHIRDS  ±6.144 V  (0.1875    mV/bit)
    #   1  → GAIN_ONE        ±4.096 V  (0.125     mV/bit)
    #   2  → GAIN_TWO        ±2.048 V  (0.0625    mV/bit)  ← default
    #   4  → GAIN_FOUR       ±1.024 V  (0.03125   mV/bit)
    #   8  → GAIN_EIGHT      ±0.512 V  (0.015625  mV/bit)
    #  16  → GAIN_SIXTEEN    ±0.256 V  (0.0078125 mV/bit)
    def set_adc_gain_all(self, gain_code: int):
        """
        Set the ADS1115 gain from Python.

        Args:
            gain_code: One of 0, 1, 2, 4, 8, 16.
        """
        #valid_gains = {0, 1, 2, 4, 8, 16}
        #if gain_code not in valid_gains:
        #    raise ValueError(f"Invalid gain code {gain_code}. Must be one of {valid_gains}")
        
        for ch in [0,1,2,3]:
            self.set_adc_channel_gain(gain_code, ch)

    def set_adc_channel_gain(self, gain_code: int, channel: int):
        """
        Set the ADS1115 gain from Python for a specific channel

        Args:
            gain_code: One of 0, 1, 2, 4, 8, 16.
        """
        valid_gains = {0, 1, 2, 4, 8, 16}
        valid_channels = {0, 1, 2, 3}
        if gain_code not in valid_gains:
            raise ValueError(f"Invalid gain code {gain_code}. Must be one of {valid_gains}")
        if channel not in valid_channels:
            raise ValueError(f"Invalid channel {channel}. Must be one of {valid_channels}")
        
        self.serial.write(f"GAINCH {channel} {gain_code}\n".encode())
        response = self.serial.readline().decode(errors="ignore").strip()
        print(f"[arduino] Set channel {channel} gain: {response}")

    def set_adc_gain(self, gain_dict: dict):
        for channel in gain_dict.keys():
            self.set_adc_channel_gain(gain_dict[channel], channel)