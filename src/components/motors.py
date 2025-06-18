import serial.tools.list_ports
from zaber_motion import Units
from zaber_motion.ascii import Connection
from .constants import *


class ZaberMotor:
    """High-level class for both linear and rotary stages"""

    def __init__(self, serial_num, conn):
        """
        Params:
        - serial_num (int): Device serial number
        - angle_offset (float): Absolute angle when stage is straight
        - usb_serial_num (str): Serial number of USB device controller
        - baud_rate (int): Serial communication baud rate
        """
        # Device info
        self._serial_num = serial_num

        # Declare Device/Axis objects
        self._device = None
        self._axis = None

        # Connect to device
        self.connect(conn)

    def connect(self, conn):
        """Connect to Zaber Stage via USB"""
        # Find axis
        device_list = conn.detect_devices()
        for device in device_list:
            if device.serial_number == self._serial_num:
                self._device = device
                self._axis = device.get_axis(1)
                print(f"Connected to Device (SN={self._serial_num})")
                break
        else:
            print("Failed to find device with specified serial number")
            raise ConnectionError



class ZaberRotaryStage(ZaberMotor):
    """Wrapper for controlling Zaber rotary stage"""

    def __init__(self, serial_num, conn):
        """
        Params:
        - serial_num (int): Device serial number
        - usb_serial_num (str): Serial number of USB device controller
        - baud_rate (int): Serial communication baud rate
        """

        # Initialize parent class
        super().__init__(
            serial_num=serial_num,
            conn=conn
        )

        # Angular offset
        self._angle_offset = 0.0 # TODO: Can I replace this logic with limit.home.x settings?

    def configure(self, angle_offset=None, limit_min=None, limit_max=None, max_speed=None, max_accel=None):
        """
        Configure the rotary stage
        Parameters:
        - angle_offset (float): Encoder reading (degrees) when axis is at "0" position
        - limit_min (float): Minimum allowable angle in degrees
        - limit_max (float): Maximum allowable angle in degrees
        - max_speed (float): Maximum rotational speed in degrees/second
        - max_accel (float): Maximum rotational acceleration in degrees/second^2
        """
        # Set angle offset
        if angle_offset:
            self._angle_offset = angle_offset

        # Set axis limits
        if limit_min:
            self._axis.settings.set("limit.min", limit_min-self._angle_offset, Units.ANGLE_DEGREES)
        if limit_max:
            self._axis.settings.set("limit.max",  limit_max-self._angle_offset, Units.ANGLE_DEGREES)

        # Set max speed/accel
        if max_speed:
            self._axis.settings.set('maxspeed', max_speed, Units.ANGULAR_VELOCITY_DEGREES_PER_SECOND)
        if max_accel:
            self._axis.settings.set('accel', max_accel, Units.ANGULAR_ACCELERATION_DEGREES_PER_SECOND_SQUARED)

    def set_angle(self, angle_deg):
        self._axis.move_absolute(angle_deg-self._angle_offset, Units.ANGLE_DEGREES)

    def move_by(self, offset_deg):
        """Move relative amount in degrees"""
        self._axis.move_relative(offset_deg, Units.ANGLE_DEGREES)

    def get_angle(self):
        return self._axis.get_position(Units.ANGLE_DEGREES) # TODO: Offset?

    def home(self):
        """Safely home axis. Make sure the axis moves in the correct direction."""
        pos = self.get_angle()
        assert abs(pos) < 180, "Angular position is too large. Please manually move closer to zero."
        if pos < 0: self._axis.move_relative(-pos+5, Units.ANGLE_DEGREES)
        self._axis.home()



class ZaberLinearStage(ZaberMotor):
    """Wrapper for controlling Zaber linear stage"""

    def configure(self, limit_min=None, limit_max=None, max_speed=None, max_accel=None):
        """
        Configure the rotary stage
        Parameters:
        - limit_min (float): Minimum allowable position in millimeters
        - limit_max (float): Maximum allowable angle in millimeters
        - max_speed (float): Maximum rotational speed in millimeters/second
        - max_accel (float): Maximum rotational acceleration in millimeters/second^2
        """
        # Set axis limits
        if limit_min:
            self._axis.settings.set("limit.min", limit_min, Units.LENGTH_MILLIMETRES)
        if limit_max:
            self._axis.settings.set("limit.max", limit_max, Units.LENGTH_MILLIMETRES)

        # Set max speed/accel
        if max_speed:
            self._axis.settings.set('maxspeed', max_speed, Units.VELOCITY_MILLIMETRES_PER_SECOND)
        if max_accel:
            self._axis.settings.set('accel', max_accel, Units.ACCELERATION_MILLIMETRES_PER_SECOND_SQUARED)

    def set_position(self, position_mm):
        """Set absolute position in mm"""
        self._axis.move_absolute(position_mm, Units.LENGTH_MILLIMETRES)

    def move_by(self, offset_mm):
        """Move relative amount in mm"""
        self._axis.move_relative(offset_mm, Units.LENGTH_MILLIMETRES)

    def get_position(self):
        """Get absolute position in mm"""
        return self._axis.get_position(Units.LENGTH_MILLIMETRES)
    
    def home(self):
        """Home axis"""
        self._axis.home()


def open_zaber_connection(usb_serial_num=ZABER_USB_SERIAL_NUM, baud_rate=ZABER_USB_BAUD_RATE):
    """Open USB COM Port Connection to Zaber"""

    # Search COM ports for Zaber device
    ports = serial.tools.list_ports.comports()
    for p in ports:
        # Open connection if device is found
        if p.serial_number == usb_serial_num:
            conn = Connection.open_serial_port(p.device, baud_rate)
            return conn
    else:
        print("Could not find Zaber motor in COM devices")
        raise ConnectionError


if __name__ == "__main__":
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
        max_speed = 5,
        max_accel = 5,
    )

    y_stage.configure(
        limit_min = 0,
        limit_max = 50,
        max_speed = 5,
        max_accel = 5,
    )

    z_stage.configure(
        limit_min = 0,
        limit_max = 50,
        max_speed = 5,
        max_accel = 5,
    )

    azimuth_stage.set_angle(0)
    altitude_stage.set_angle(20)

    x_stage.set_position(25.767)
    y_stage.set_position(30.014)
    z_stage.set_position(35.905)
