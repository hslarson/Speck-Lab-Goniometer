import serial.tools.list_ports
from zaber_motion import Units
from zaber_motion.ascii import Connection, Axis

# Constants
ZABER_AZIMUTH_SERIAL_NUM  = 132636
ZABER_ALTITUDE_SERIAL_NUM = 132641

ZABER_AZIMUTH_ANGLE_OFFSET  = 0 # The angle reading when azimuth is 0
ZABER_ALTITUDE_ANGLE_OFFSET = -45 # The angle reading when arm is vertical


class ZaberRotaryStage:
    def __init__(self, serial_num, angle_offset=0.0, usb_serial_num="A10NGBR4A", baud_rate=115200):
        """
        Params:
        - serial_num (int): Device serial number
        - angle_offset (float): Absolute angle when stage is straight
        - usb_serial_num (str): Serial number of USB device controller
        - baud_rate (int): Serial communication baud rate
        """

        # Serial communication info
        self._usb_serial_num = usb_serial_num
        self._baud_rate = baud_rate

        # Device info
        self._serial_num = serial_num
        self._angle_offset = angle_offset # TODO: Can I replace this logic with limit.home.x settings?

        # Device/Axis Objects
        self._device = None
        self._axis = None


    def connect(self, axis_number=1):
        """
        Connect to Zaber Stage via USB
        
        Params:
        - axis_number (int): The axis number to connect to
        """

        # Search COM ports for Zaber device
        ports = serial.tools.list_ports.comports()
        for p in ports:
            # Open connection if device is found
            if p.serial_number == self._usb_serial_num:
                conn = Connection.open_serial_port(p.device, self._baud_rate)
                print("Serial communication established")
                break
        else:
            print("Could not find Zaber motor in COM devices")
            raise ConnectionError

        # Find axis
        device_list = conn.detect_devices()
        for device in device_list:
            if device.serial_number == self._serial_num:
                self._device = device
                self._axis = device.get_axis(axis_number)
                print("Found device")
                break
        else:
            print("Failed to find device with specified serial number")
            raise ConnectionError



def init_axes(azimuth_axis: Axis, altitude_axis: Axis):
    """Initialize settings and home axes"""

    # Set axis limits
    azimuth_axis.settings.set("limit.min", -90-ZABER_AZIMUTH_ANGLE_OFFSET, Units.ANGLE_DEGREES)
    azimuth_axis.settings.set("limit.max",  90-ZABER_AZIMUTH_ANGLE_OFFSET, Units.ANGLE_DEGREES)

    altitude_axis.settings.set("limit.min", -90-ZABER_ALTITUDE_ANGLE_OFFSET, Units.ANGLE_DEGREES)
    altitude_axis.settings.set("limit.max",  90-ZABER_ALTITUDE_ANGLE_OFFSET, Units.ANGLE_DEGREES)

    # Safely home stages
    # If we don't ensure that the angle is positive,
    # The motor may rotate in the wrong direction while homing
    print("Homing stages")
    az_pos = azimuth_axis.get_position(Units.ANGLE_DEGREES)
    assert abs(az_pos) < 180, "Azimuth position is large. Please manually move closer to zero."
    if az_pos < 0: azimuth_axis.move_relative(-az_pos+5, Units.ANGLE_DEGREES)
    azimuth_axis.home()

    alt_pos = altitude_axis.get_position(Units.ANGLE_DEGREES)
    assert abs(alt_pos) < 180, "Altitude position is large. Please manually move closer to zero."
    if alt_pos < 0: altitude_axis.move_relative(-alt_pos+5, Units.ANGLE_DEGREES)
    altitude_axis.home()


def set_altitude(axis: Axis, angle_deg):
    """
    Set the position of the altitude stage:\n
      0 = Vertical\n
    -90 = Left\n
    +90 = Right
    """
    axis.move_absolute(angle_deg-ZABER_ALTITUDE_ANGLE_OFFSET, Units.ANGLE_DEGREES)


def set_azimuth(axis: Axis, angle_deg):
    """
    Set the position of the azimuth stage:\n
      0 = Probes in front\n
    -90 = Probes on right\n
    +90 = Probes on left
    """
    axis.move_absolute(angle_deg-ZABER_AZIMUTH_ANGLE_OFFSET, Units.ANGLE_DEGREES)


if __name__ == "__main__":
    az, alt = get_axes()
    init_axes(az, alt)

    print("starting move")
    set_altitude(alt, 0)
    print("done")
    set_azimuth(az, 45)
