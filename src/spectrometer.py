from seabreeze.spectrometers import Spectrometer, SeaBreezeError


SPECTROMETER_SERIAL_NUM = "USB2+F00373"


def get_spectrometer():
    """Returns a spectrometer object"""
    try:
        spec = Spectrometer.from_serial_number(SPECTROMETER_SERIAL_NUM)
        if spec: print("Found spectrometer")
        return spec
    except SeaBreezeError as err:
        print(err)
        exit()


def set_integration_time(spectrometer: Spectrometer, int_time_micros):
    """Set the integration time (in microseconds) for the device"""

    # Check limits
    int_min, int_max = spectrometer.integration_time_micros_limits
    assert (int_time_micros >= int_min) and (int_time_micros <= int_max), "Invalid integration time"

    # Set integration time
    spectrometer.integration_time_micros(int_time_micros)


if __name__ == "__main__":
    spec = get_spectrometer()