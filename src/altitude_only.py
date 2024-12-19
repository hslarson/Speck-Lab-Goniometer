import matplotlib.pyplot as plt
from datetime import datetime
from spectrometer import *
from motor import *
import numpy as np
import time
import csv


# === Angular sweep parameters ===
# -90 is arm horizontal left. +90 is arm horizontal right
ALTITUDE_START = -80 # Starting angle (degrees) of sweep.
ALTITUDE_END = 80 # Final angle (degrees) of sweep
ALTITUDE_STEP = 0.2 # Degrees between each measurement

# === Spectrometer parameters ===
INTEGRATION_TIME = 5000 # Integration time (microseconds)
AVERAGING_POINTS = 128 # Number of readings to collect at each angle
BOXCAR_WIDTH = 10 # Moving average filter width. 1 = No smoothing



# Create array of altitude angles
altitude_angles = np.arange(ALTITUDE_START, ALTITUDE_END+ALTITUDE_STEP, ALTITUDE_STEP)

# Initialize motors
azimuth_stage, altitude_stage = get_axes()
init_axes(azimuth_stage, altitude_stage)

# Set azimuth position
set_azimuth(azimuth_stage, 0)

# Set altitude speed and acceleration
altitude_stage.settings.set('maxspeed', 30, Units.ANGULAR_VELOCITY_DEGREES_PER_SECOND)
altitude_stage.settings.set('motion.accelonly', 20, Units.ANGULAR_ACCELERATION_DEGREES_PER_SECOND_SQUARED)
altitude_stage.settings.set('motion.decelonly', 20, Units.ANGULAR_ACCELERATION_DEGREES_PER_SECOND_SQUARED)


# Initialize spectrometer
spec = get_spectrometer()
wavelengths = spec.wavelengths()
set_integration_time(spec, INTEGRATION_TIME)


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
ax.set_ylim(0, spec.max_intensity)
ax.set_xlabel('Wavelength (nm)')
ax.set_ylabel('Counts')
plt.ion()


# Sweep altitude
for alt in altitude_angles:
    # Move motor
    print(f"Setting Altitude to {alt:+5.2f}°")
    set_altitude(altitude_stage, float(alt))

    # Motion settling time
    time.sleep(1)

    # Take new readings
    reading = np.zeros(spec.pixels)
    for _ in range(AVERAGING_POINTS):
        reading += spec.intensities()

    # Post-process data
    reading /= AVERAGING_POINTS
    kernel = np.ones(BOXCAR_WIDTH) / BOXCAR_WIDTH
    reading = np.convolve(reading, kernel, mode='valid')

    # Save readings to csv
    with open(output_filename, mode='a', newline='') as f:
        writer = csv.writer(f)
        writer.writerow([alt] + reading)

    # Show readings in figure
    line.set_data(wavelengths, reading)
    ax.set_title(f"Spectrometer Reading ({alt:+5.2f}°)")
    plt.draw() # Redraw the plot
    plt.pause(0.01)


plt.ioff()  # Turn off interactive mode
plt.show()  # Keep the plot window open at the end
