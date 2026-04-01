import numpy as np
import scipy as sp

def power_func(x, x0, w):
    #Poffset = 0 if you can measure the full curve or be able to measure Poffset
    #for example, by blocking the beam for example
    return 0.5 * (1 + sp.special.erf((x-x0)*np.sqrt(2)/w) )


def get_waist(xdata, ydata):
    return sp.optimize.curve_fit(power_func,xdata, ydata)[0]