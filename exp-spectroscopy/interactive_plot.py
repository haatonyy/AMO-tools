"""
interactive_lines.py — Sliders for `a` (line offset) and file index only.
zero_point is fixed at 72.835 (as set in reduced_data default).

Run from terminal:  python interactive_lines.py
"""

import numpy as np
import matplotlib.pyplot as plt
from matplotlib.widgets import Slider, Button
from glob import glob

from utils import load_data
from data_analysis import fit_linear_background_iterative
from science import laser_current_to_freq_MHz_2

# --------------------------------------------------------------------------- #
#  Config                                                                      #
# --------------------------------------------------------------------------- #

#P852_mW =7.3data
parent = "04132026/data-p852=7.3mW/"
#p852_mW=3 data
#parent = "04122026/04122026-130418-spec/"
#852_mW=11.1 data
#parent = "04112026/04112026-154320-spec/"
#p852_mW=27.7 data
#parent = "04112026/04112026-233630-spec/"
dataf_ls = np.sort(glob(parent + "data_*.csv"))

ZERO_POINT = 72.835   # fixed
A_INIT     = 0.0
IDX_INIT   = 0
YMIN, YMAX = 1.02, 0.90

# --------------------------------------------------------------------------- #
#  Data helper                                                                 #
# --------------------------------------------------------------------------- #

def reduced_data(filename, zero_point=ZERO_POINT):
    x, y = load_data(filename)
    y = y - (-0.013)
    a, b, _, _ = fit_linear_background_iterative(x, y, n_iter=3)
    yf = y / (a * x + b)
    xf = laser_current_to_freq_MHz_2(x, zero_point)
    return xf[25:100], yf[25:100]

# --------------------------------------------------------------------------- #
#  Transitions                                                                 #
# --------------------------------------------------------------------------- #

transitions = [
    (0,                                              "blue", "6'->5"),
    (127.2,                                          "red",  "5'->5"),
    (127.2 + 106.0,                                  "blue", "4'->5"),
    (127.2 + 251.1,                                  "blue", "5'->4"),
    (127.2 + 106.0 + 251.1,                          "blue", "4'->4"),
    (127.2 + 106.0 + 251.1 + 84.8,                  "blue", "3'->4"),
    (127.2 + 106.0 + 251.1 + 201.3,                 "blue", "4'->3"),
    (127.2 + 106.0 + 251.1 + 201.3 + 84.8,          "blue", "3'->3"),
    (127.2 + 106.0 + 251.1 + 201.3 + 84.8 + 151.2, "blue", "3'->2"),
]

# --------------------------------------------------------------------------- #
#  Figure                                                                      #
# --------------------------------------------------------------------------- #

fig, ax = plt.subplots(figsize=(8, 5))
plt.subplots_adjust(bottom=0.25)

x0, y0 = reduced_data(dataf_ls[IDX_INIT])
[data_line] = ax.plot(x0, y0, ".-", color="black", lw=1, ms=3)

vline_artists = []
for offset, col, label in transitions:
    vl = ax.axvline(A_INIT + offset, color=col, lw=1.2, alpha=0.8, label=label)
    vline_artists.append(vl)

ax.set_xlabel(r"Detuning $\Delta_{3491}$ (MHz)")
ax.set_ylabel("Normalised transmission")
ax.set_ylim(0.85, 1.06)
ax.set_title(f"file index {IDX_INIT}  —  {dataf_ls[IDX_INIT]}", fontsize=9)
ax.legend(fontsize=7, ncol=3, loc="lower right")

# --------------------------------------------------------------------------- #
#  Sliders                                                                     #
# --------------------------------------------------------------------------- #

ax_a   = plt.axes([0.15, 0.13, 0.65, 0.03])
ax_idx = plt.axes([0.15, 0.06, 0.65, 0.03])

slider_a   = Slider(ax_a,   "a (MHz)",    -300.0, 300.0,
                    valinit=A_INIT, valstep=0.5)
slider_idx = Slider(ax_idx, "file index", 0, len(dataf_ls) - 1,
                    valinit=IDX_INIT, valstep=1)

ax_reset = plt.axes([0.82, 0.00, 0.10, 0.05])
Button(ax_reset, "Reset").on_clicked(
    lambda e: [slider_a.reset(), slider_idx.reset()]
)

# --------------------------------------------------------------------------- #
#  Update                                                                      #
# --------------------------------------------------------------------------- #

def update(_):
    a   = slider_a.val
    idx = int(slider_idx.val)

    x, y = reduced_data(dataf_ls[idx])
    data_line.set_xdata(x)
    data_line.set_ydata(y)
    ax.set_title(f"file index {idx}  —  {dataf_ls[idx]}", fontsize=9)

    for i, (offset, _, _) in enumerate(transitions):
        vline_artists[i].set_xdata([a + offset, a + offset])

    ax.relim()
    ax.autoscale_view(scaley=False)
    fig.canvas.draw_idle()

slider_a.on_changed(update)
slider_idx.on_changed(update)

plt.show()