from motor import *
from spectrometer import *
import numpy as np
import csv
from datetime import datetime
import time
import matplotlib.pyplot as plt


# Angular sweep parameters
AZIMUTH_START = 0
AZIMUTH_END = 90
AZIMUTH_STEP = 1
azimuth_angles = np.arange(AZIMUTH_START, AZIMUTH_END+AZIMUTH_STEP, AZIMUTH_STEP)

ALTITUDE_START = -80
ALTITUDE_END = 80
ALTITUDE_STEP = 0.2
altitude_angles = np.arange(ALTITUDE_START, ALTITUDE_END+ALTITUDE_STEP, ALTITUDE_STEP)


# Initialize motors
azimuth_stage, altitude_stage = get_axes()
init_axes(azimuth_stage, altitude_stage)

# Turn off motor LEDs while measuring
# TODO: fix
# azimuth_stage.settings.set('system.led.enable', 0)
# altitude_stage.settings.set('system.led.enable', 0)


# Initialize spectrometer
spec = get_spectrometer()
wavelengths = spec.wavelengths()
set_integration_time(spec, 100000)


# Create output CSV
output_file_prefix = "goniometer_data"
output_filename = f"{output_file_prefix}_{datetime.now().strftime('%Y_%m_%dT%H%M%S')}.csv"
with open(output_filename, mode='w', newline='') as f:
    col_labels = ["Azimuth (deg)", "Altitude (deg)"]
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



# Sweep azimuth
for az in azimuth_angles:
    # Move motor (blocks until done)
    print(f"Setting Azimuth to {az:+5.2f}°")
    set_azimuth(azimuth_stage, float(az))

    # Sweep altitude
    for alt in altitude_angles:
        # Move motor
        print(f"Setting Altitude to {alt:+5.2f}°")
        set_altitude(altitude_stage, float(alt))

        # Settling time
        time.sleep(0.2)

        # Take new reading
        reading = spec.intensities()

        # Save readings to csv
        with open(output_filename, mode='a', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(reading)

        # Show readings in figure
        line.set_data(wavelengths, reading)
        ax.set_title(f"Spectrometer Reading ({az:+5.2f}°, {alt:+5.2f}°)")
        plt.draw()  # Redraw the plot
        plt.pause(0.01)
        

# Turn motor LEDs back on
# TODO: fix
# azimuth_stage.settings.set('system.led.enable', 1)
# altitude_stage.settings.set('system.led.enable', 1)

plt.ioff()  # Turn off interactive mode
plt.show()  # Keep the plot window open at the end
