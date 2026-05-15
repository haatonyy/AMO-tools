from scipy.stats import linregress
import numpy as np
import json
from .science import laser_current_to_freq_MHz_2

def fit_linear_background_iterative(x, y, niter=2, sigma=2.5):
    mask = np.ones_like(y, dtype=bool)

    for _ in range(niter):
        # fit line to current inliers
        slope, intercept, *_ = linregress(x[mask], y[mask])
        y_fit = slope * x + intercept

        # residuals
        resid = y - y_fit
        std = np.std(resid[mask])

        # keep points close to the line
        mask = np.abs(resid) < sigma * std
    return slope, intercept, mask, y_fit


def load_data(file:str, skiprows=1):
    data = np.loadtxt(file, delimiter=',', skiprows=skiprows)
    return data[:, 0], data[:,1]


def load_param(file:str):
    return json.load(open(file, 'r'))

