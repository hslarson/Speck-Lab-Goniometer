from pyCCT import PyCCT
import numpy as np


def get_spectrometer():
    """Returns a pyCCT SpectrometerWrapper object"""

    # Find connected devices
    py_cct = PyCCT()
    devices = py_cct.discover_devices()
    if not devices:
        print("No spectrometers found")
        exit(-1)
    
    # Connect to device
    spec = py_cct.connect_to_device(devices[0])
    if not spec:
         print("Failed to connect to spectrometer")
         exit(-1)
    
    print(f"Found Spectrometer (device ID={spec.get_device_id()})")
    return spec


def configure_spectrometer(spectrometer, int_time_ms=None, averages=None):
    """
    Parameters:
    - int_time_ms (float): Sets the integration time (in milliseconds) for the device
    - averages (int): Sets the number of captures to average for a single spectrum acquisition
    """

    # Set exposure for spectrum acquisition
    if int_time_ms:
        exposure_result = spectrometer.set_manual_exposure(int_time_ms)
        if exposure_result:
            print(f"Set exposure time: {spectrometer.get_manual_exposure():.3f} ms")
        else:
            print("Failed to set exposure time")
            exit(-1)

    # Set hardware averaging in the spectrometer
    if averages:
        ave_result = spectrometer.set_hardware_average(averages)
        if ave_result:
            print(f"Set hardware averaging: {spectrometer.get_hardware_average():.3f} frames")
        else:
            print("Failed to set hardware averages")
            exit(-1)

    # Display capture time
    if int_time_ms or averages:
        tm   = spectrometer.get_manual_exposure()
        avgs = spectrometer.get_hardware_average()

        print(f"Each spectrum capture will take {tm*avgs:.1f} ms")


def capture_dark_spectrum(spectrometer):
    """Captures and updates the spectrometer's dark spectrum"""
    try:
        # Close the shutter
        shutter_result = spectrometer.set_shutter(False) # TODO: Redundant?
        assert shutter_result, "Failed to close shutter"

        # Capture the dark spectrum
        dark_result = spectrometer.update_dark_spectrum(False)
        assert dark_result, "Failed to capture dark spectrum"

        # Open the shutter
        shutter_result = spectrometer.set_shutter(True) # TODO: Redundant?
        assert shutter_result, "Failed to re-open shutter"

    # Failed
    except AssertionError as err:
        print(err)
        exit(-1)
    
    else: print("Updated dark spectrum")


def capture_spectrum(spectrometer):
    """Captures a spectrum. Returns: A mx2 Numpy array of wavelengths (col 0), and readings (col 1)"""
    
    # Capture spectrum
    wavelengths, intensities, _, _ = spectrometer.acquire_single_spectrum()
    if (not wavelengths) or (not intensities):
        print("Spectrum capture failed")
        return None
    
    # Construct output array
    return np.column_stack((wavelengths, intensities))


# Unit test
if __name__ == "__main__":
    import matplotlib.pyplot as plt
    import time

    spec = get_spectrometer()

    configure_spectrometer(
        spec, 
        int_time_ms=1000, 
        averages=10
    )

    capture_dark_spectrum(spec)

    print("Capturing spectrum")

    start_ts = time.time()
    data = capture_spectrum(spec)
    end_ts = time.time()

    print(f"Spectrum capture took {(end_ts-start_ts)*1e3:.2f} ms")

    # Post-process
    BOXCAR_WIDTH = 10  # moving average window size
    kernel = np.ones(BOXCAR_WIDTH) / BOXCAR_WIDTH

    # Apply convolution (moving average) to the intensity column
    smoothed = np.convolve(data[:, 1], kernel, mode='same')

    # Plot the spectrogram
    plt.figure(figsize=(8, 5))
    
    # Scatter plot of raw data
    plt.scatter(data[:, 0], data[:, 1], color='blue', alpha=0.5, label='Raw Data')

    # Line plot of smoothed data
    plt.plot(data[:, 0], smoothed, color='red', linewidth=2, label=f'Smoothed (Boxcar {BOXCAR_WIDTH})')

    # Add labels and title
    plt.xlabel('Wavelength (nm)')
    plt.ylabel('Intensity')
    plt.grid(True)  # optional: add a grid

    # Show the plot
    plt.show()
