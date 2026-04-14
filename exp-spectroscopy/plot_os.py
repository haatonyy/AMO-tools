"""
plot_oscilloscope_interactive.py — Oscilloscope data viewer with file index slider.

Run from terminal:  python plot_oscilloscope_interactive.py
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
from glob import glob
from scipy.signal import savgol_filter

# --------------------------------------------------------------------------- #
#  Data helpers                                                                #
# --------------------------------------------------------------------------- #

def load_data(file: str, skiprows=18):
    data = np.loadtxt(file, delimiter=',', skiprows=skiprows, usecols=(3, 4))
    return data[:, 0], data[:, 1]


def reduced_data(filename):
    x, y = load_data(filename)
    return x, y

# --------------------------------------------------------------------------- #
#  Load files and background                                                   #
# --------------------------------------------------------------------------- #

files = np.sort(glob("data_oscilloscope_F4/*/*.CSV"))

# Background: last file, smoothed
times_bg, values_bg = load_data(files[-1])
smoothed_bg = savgol_filter(values_bg, window_length=150, polyorder=1)

IDX_INIT = 0

# --------------------------------------------------------------------------- #
#  Figure                                                                      #
# --------------------------------------------------------------------------- #

fig, ax = plt.subplots(figsize=(9, 5))
plt.subplots_adjust(bottom=0.20)

times, values_data = load_data(files[IDX_INIT])
values   = values_data - smoothed_bg
smoothed = savgol_filter(values, window_length=20, polyorder=5)

[raw_line]    = ax.plot(times[300:-300], values[300:-300],
                        color="tab:blue", lw=0.8, alpha=0.6, label="raw")
[smooth_line] = ax.plot(times[300:-300], smoothed[300:-300],
                        color="tab:orange", lw=1.5, label="smoothed")
# Set y-axis scale from the 7th file (index 6) and lock it
_, values_ref = load_data(files[6])
values_ref    = savgol_filter(values_ref - smoothed_bg, window_length=20, polyorder=5)
y_margin      = (values_ref[300:-300].max() - values_ref[300:-300].min()) * 0.1
ax.set_ylim(values_ref[300:-300].min() - y_margin,
            values_ref[300:-300].max() + y_margin)
ax.autoscale(enable=False, axis='y')
ax.axhline(0, color="black", lw=0.8, ls="--")

ax.set_xlabel("Time (s)")
ax.set_ylabel("Voltage (V)")
ax.set_title(f"idx={IDX_INIT}  —  {files[IDX_INIT]}", fontsize=9)
ax.legend(fontsize=8, loc="upper right")

# --------------------------------------------------------------------------- #
#  Slider + buttons                                                            #
# --------------------------------------------------------------------------- #

ax_idx   = plt.axes([0.15, 0.07, 0.45, 0.04])
ax_back  = plt.axes([0.62, 0.02, 0.08, 0.05])
ax_next  = plt.axes([0.72, 0.02, 0.08, 0.05])
ax_reset = plt.axes([0.82, 0.02, 0.08, 0.05])

slider_idx = Slider(ax_idx, "file index", 0, len(files) - 2,
                    valinit=IDX_INIT, valstep=1)

btn_back  = Button(ax_back,  "Back")
btn_next  = Button(ax_next,  "Next")
btn_reset = Button(ax_reset, "Reset")

btn_reset.on_clicked(lambda e: slider_idx.reset())

def next_file(e):
    slider_idx.set_val(min(slider_idx.val + 1, len(files) - 2))

def back_file(e):
    slider_idx.set_val(max(slider_idx.val - 1, 0))

btn_next.on_clicked(next_file)
btn_back.on_clicked(back_file)

# --------------------------------------------------------------------------- #
#  Update                                                                      #
# --------------------------------------------------------------------------- #

def update(_):
    idx = int(slider_idx.val)
    times, values_data = load_data(files[idx])
    values   = values_data# - smoothed_bg
    smoothed = savgol_filter(values, window_length=20, polyorder=5)

    raw_line.set_xdata(times[300:-300])
    raw_line.set_ydata(values[300:-300])
    smooth_line.set_xdata(times[300:-300])
    smooth_line.set_ydata(smoothed[300:-300])

    ax.set_title(f"idx={idx}  —  {files[idx]}", fontsize=9)
    ax.relim()
    ax.autoscale_view(scaley=False)
    fig.canvas.draw_idle()

slider_idx.on_changed(update)

plt.show()