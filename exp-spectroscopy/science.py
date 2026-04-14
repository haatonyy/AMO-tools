from arc import Cesium
import config
import numpy as np


Cs = Cesium()

def get_852_RabiFreq_MHz(power_mW: float, beam_waist_mm = 1.24, q=0) -> float:
    """
    Calculate the expected Rabi frequency (in MHz) for the 852 nm transition,
    given the laser power in mW and beam waist in mm.

    Args:
        power_mW: Laser power in milliwatts.
        beam_waist_mm: Beam waist (1/e^2 radius) in millimeters.

    Returns:
        Rabi frequency in MHz.
    """
    # Convert units
    power_W = power_mW / 1000.0
    beam_waist_m = beam_waist_mm * 1e-3

    return Cs.getRabiFrequency(n1=6, l1=0, j1=0.5, mj1=0.5, n2=6, l2=1, j2=1.5, q=0,
                               laserPower=power_W,laserWaist=beam_waist_m)/(2*np.pi*10**6)

def get_3491_RabiFreq_MHz(power_mW: float, beam_waist_mm: float = 0.86, q=0) -> float:
    """
    Calculate the expected Rabi frequency (in MHz) for the 349.1 nm transition,
    given the laser power in mW and beam waist in mm.

    Args:
        power_mW: Laser power in milliwatts.
        beam_waist_mm: Beam waist (1/e^2 radius) in millimeters.

    Returns:
        Rabi frequency in MHz.
    """
    # Convert units
    power_W = power_mW / 1000.0
    beam_waist_m = beam_waist_mm * 1e-3

    return Cs.getRabiFrequency(n1=6, l1=1, j1=1.5, mj1=0.5, n2=5, l2=2, j2=2.5, q=q,
                               laserPower=power_W,laserWaist=beam_waist_m)/(2*np.pi*10**6)

def laser_current_to_freq_MHz(current_mA: float, zero_point_mA: float = 73):
    """
    Convert laser current (in mA) to an estimated Rabi frequency (in MHz) for the 349.1 nm transition.

    Args:
        current_mA: Laser current in milliamps.
        zero_point_mA: Current at which the Rabi frequency is zero (mA)."""
    return (current_mA - zero_point_mA) * (-22.2/0.01)

def laser_current_to_freq_MHz_2(current_mA: float, zero_point_mA: float = 73):
    """
    Convert laser current (in mA) to an estimated Rabi frequency (in MHz) for the 349.1 nm transition.

    Args:
        current_mA: Laser current in milliamps.
        zero_point_mA: Current at which the Rabi frequency is zero (mA)."""
    wavelength = 3491 + (current_mA-zero_point_mA) * 0.091 
    freq_0_MHz = 299792458/(3491*1e-3)
    freq_MHz = 299792458/(wavelength*1e-3)
    
    return freq_MHz - freq_0_MHz

def get_laser_temperature(R: float) -> float:
    """
    Convert thermistor resistance to temperature using the B-parameter equation.
    1/T = 1/T0 + (1/B) * ln(R/R0)

    Args:
        R: Measured thermistor resistance (Ohms)

    Returns:
        Temperature in Celsius
    """
    T0_K = config.THERMISTOR_T0 + 273.15          # convert to Kelvin
    inv_T = (1 / T0_K) + (1 / config.THERMISTOR_B) * np.log(R / config.THERMISTOR_R0)
    T_K   = 1 / inv_T
    return T_K - 273.15      


#get_intensity_W_per_m2(power_mW: float, beam_waist_mm: float) -> float:
    """
    Calculate the laser intensity in W/m^2 given the power in mW and beam waist in mm.

    Args:
        power_mW: Laser power in milliwatts.
        beam_waist_mm: Beam waist (1/e^2 radius) in millimeters.

    Returns:
        Intensity in W/m^2.
    """
    # Convert units
    #power_W = power_mW / 1000.0
    #beam_waist_m = beam_waist_mm * 1e-3

    #area_m2 = np.pi * (beam_waist_m ** 2)
    #intensity_W_per_m2 = power_W / area_m2
    #return intensity_W_per_m2