from scipy.stats import linregress
import numpy as np
import json
from exp.science import laser_current_to_freq_MHz_2

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


def load_data2(file:str, skiprows=1):
    data = np.loadtxt(file, delimiter=',', skiprows=skiprows)
    return data[:, 0], data[:,1]

def load_data(file: str, skiprows: int = 0) -> dict[str, np.ndarray]:
    """
    Load a CSV file with a header row into a dict mapping column name
    to a 1-D numpy array of floats. Blank/empty cells become NaN.

    Args:
        file:     Path to the CSV file.
        skiprows: Number of lines to skip BEFORE the header row.
                  Default 0 (header is the very first line). Use this for
                  CSVs with comment lines or extra metadata above the header.

    Example:
        >>> d = load_data('data.csv')                  # header on line 1
        >>> d = load_data('data.csv', skiprows=3)      # 3 comment lines, then header
        >>> d['l2_pos_deg']
        array([3.0, 6.0, 9.0, ...])
    """
    arr = np.genfromtxt(
        file, delimiter=',', names=True, dtype=float, skip_header=skiprows
    )
    return {name: np.atleast_1d(arr[name]) for name in arr.dtype.names}


def load_param(file:str):
    return json.load(open(file, 'r'))

