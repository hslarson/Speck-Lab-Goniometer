import matplotlib.pyplot as plt
from datetime import datetime
import numpy as np
import time
import csv

from components.spectrometer import *
from components.motors import *
from alignment import *


# === Angular sweep parameters ===
# -90 is arm horizontal left. +90 is arm horizontal right
ALTITUDE_START = -80 # Starting angle (degrees) of sweep.
ALTITUDE_END = 80 # Final angle (degrees) of sweep
ALTITUDE_STEP = 0.2 # Degrees between each measurement
SETTLE_TIME = 0.5 # Time (in seconds) to wait before collecting measurements after moving motor

# === Spectrometer parameters ===
INTEGRATION_TIME = 5.0 # Integration time (milliseconds)
AVERAGING_POINTS = 128 # Number of readings to collect at each angle
BOXCAR_WIDTH = 10 # Moving average filter width. 1 = No smoothing


# === Set up motors ===
# Open USB
conn = open_zaber_connection()

# Connect to rotary stages
azimuth_stage  = ZaberRotaryStage(ZABER_AZIMUTH_SERIAL_NUM, conn)
altitude_stage = ZaberRotaryStage(ZABER_ALTITUDE_SERIAL_NUM, conn)

# Connect to linear stages
x_stage = ZaberLinearStage(ZABER_X_SERIAL_NUM, conn)
y_stage = ZaberLinearStage(ZABER_Y_SERIAL_NUM, conn)
z_stage = ZaberLinearStage(ZABER_Z_SERIAL_NUM, conn)

# Home stages
azimuth_stage.home()
altitude_stage.home()
x_stage.home()
y_stage.home()
z_stage.home()

# Configure rotary stages
azimuth_stage.configure(
    angle_offset = ZABER_AZIMUTH_ANGLE_OFFSET,
    limit_min = -90,
    limit_max =  90,
    max_speed = 30,
    max_accel = 5
)

altitude_stage.configure(
    angle_offset = ZABER_ALTITUDE_ANGLE_OFFSET,
    limit_min = -90,
    limit_max =  90,
    max_speed = 30,
    max_accel = 5
)

# Configure linear stages
x_stage.configure(
    limit_min = 0,
    limit_max = 50,
    max_speed = 10,
    max_accel = 10,
)

y_stage.configure(
    limit_min = 0,
    limit_max = 50,
    max_speed = 10,
    max_accel = 10,
)

z_stage.configure(
    limit_min = 0,
    limit_max = 50,
    max_speed = 10,
    max_accel = 10,
)

# Set azimuth position
azimuth_stage.set_angle(0)


# === Initialize spectrometer ===
spec = get_spectrometer()
configure_spectrometer(
    spec,
    int_time_ms=INTEGRATION_TIME,
    averages=AVERAGING_POINTS
)

# Take dark spectrum
capture_dark_spectrum(spec)

# Get spectrometer wavelengths
data = capture_spectrum(spec)
wavelengths = data[:,0]


# === Initialize Outputs ===
# Create array of altitude angles
altitude_angles = np.arange(ALTITUDE_START, ALTITUDE_END+ALTITUDE_STEP, ALTITUDE_STEP)

# Create output CSV
output_file_prefix = "../data/goniometer_data"
output_filename = f"{output_file_prefix}_{datetime.now().strftime('%Y_%m_%dT%H%M%S')}.csv"
with open(output_filename, mode='w', newline='') as f:
    col_labels = ["Altitude (deg)"]
    col_labels += [f"{w} nm" for w in wavelengths]

    writer = csv.writer(f)
    writer.writerow(col_labels)

# Initialize the spectrogram plot
fig, ax = plt.subplots()
line, = ax.plot([], [], lw=2)
ax.set_xlim(min(wavelengths), max(wavelengths))
ax.set_ylim(0, 1024) # TODO: what is the max counts?
ax.set_xlabel('Wavelength (nm)')
ax.set_ylabel('Counts')
plt.ion()

# === Align sample ===
# Compute pointing functions
m_x, b_x, m_y, b_y = get_pointing_error(spec, x_stage, y_stage, z_stage, 3)

# Do Z optimization
z_points = np.linspace(30, 40, 5)
align_sample_z(
    spec, 
    x_stage,
    y_stage,
    z_stage,
    altitude_stage, 
    z_points,
    m_x, b_x,
    m_y, b_y,
    5
)


# === Sweep Altitude ===
for alt in altitude_angles:
    # Move motor
    print(f"Setting Altitude to {alt:+5.2f}°")
    altitude_stage.set_angle(float(alt))

    # Motion settling time
    time.sleep(SETTLE_TIME)

    # Take new readings
    reading = capture_spectrum(spec)[:,1]

    # Post-process data
    reading /= AVERAGING_POINTS
    kernel = np.ones(BOXCAR_WIDTH) / BOXCAR_WIDTH
    reading = np.convolve(reading, kernel, mode='same')

    # Save readings to csv
    with open(output_filename, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([alt] + reading.tolist())

    # Show readings in figure
    line.set_data(wavelengths, reading)
    ax.set_title(f"Spectrometer Reading ({alt:+5.2f}°)")
    plt.draw() # Redraw the plot
    plt.pause(0.01)
