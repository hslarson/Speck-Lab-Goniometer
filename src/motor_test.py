import serial.tools.list_ports
from zaber_motion import Units
from zaber_motion.ascii import Connection, Axis

# Constants
ZABER_BAUD_RATE = 115200
ZABER_USB_SERIAL_NUM = "A10NGBR4A"
ZABER_AZIMUTH_SERIAL_NUM  = 132636
ZABER_ALTITUDE_SERIAL_NUM = 132641

ZABER_AZIMUTH_ANGLE_OFFSET  = 0 # The angle reading when azimuth is 0
ZABER_ALTITUDE_ANGLE_OFFSET = -45 # The angle reading when arm is vertical



def get_axes():
    """Returns tuple of Axis objects: (azimuth axis, altitude axis)"""

    # Search COM ports for Zaber device
    ports = serial.tools.list_ports.comports()
    for p in ports:
        # Open connection if device is found
        if p.serial_number == ZABER_USB_SERIAL_NUM:
            conn = Connection.open_serial_port(p.device, ZABER_BAUD_RATE)
            break
    else:
        print("Could not find Zaber motor in COM devices")
        exit(-1)

    azimuth_axis = None
    altitude_axis = None

    # Detect motors
    device_list = conn.detect_devices()
    for device in device_list:
        if device.serial_number == ZABER_AZIMUTH_SERIAL_NUM:
            azimuth_axis = device.get_axis(1)
        elif device.serial_number == ZABER_ALTITUDE_SERIAL_NUM:
            altitude_axis = device.get_axis(1)
    
    # Check that both stages were found
    assert (azimuth_axis != None), "Azimuth stage not detected"
    assert (altitude_axis != None), "Altitude stage not detected"

    return azimuth_axis, altitude_axis



def init_axes(azimuth_axis: Axis, altitude_axis: Axis):
    """Initialize settings and home axes"""

    # Set axis limits
    azimuth_axis.settings.set("limit.min", -5-ZABER_AZIMUTH_ANGLE_OFFSET, Units.ANGLE_DEGREES)
    azimuth_axis.settings.set("limit.max", 90-ZABER_AZIMUTH_ANGLE_OFFSET, Units.ANGLE_DEGREES)

    altitude_axis.settings.set("limit.min", -90-ZABER_ALTITUDE_ANGLE_OFFSET, Units.ANGLE_DEGREES)
    altitude_axis.settings.set("limit.max",  90-ZABER_ALTITUDE_ANGLE_OFFSET, Units.ANGLE_DEGREES)

    # Safely home stages
    # If we don't ensure that the angle is positive,
    # The motor may rotate in the wrong direction while homing
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

    set_altitude(alt, 0)
    set_azimuth(az, 45)
