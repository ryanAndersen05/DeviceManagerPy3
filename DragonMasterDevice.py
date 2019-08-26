import DragonMasterDeviceManager


"""
The Base class for all our Dragon Master Devices
"""
class DragonMasterDevice:

    def __init__(self, dragonMasterDeviceManager):
        self.dragonMasterDeviceManager = dragonMasterDeviceManager
        self.deviceParentPath = None

    """
    This method should be called every time we connect to a new device for the fist time. If our device does not connect correctly
    this mtehod should return false.
    """
    def start_device():
        return False

    def disconnect_device():
        return

    """
    This method will be called periodically to ensure that our device is still connected and fucntioning correctly
    """
    def poll_device_for_errors():
        return False

    """
    This method sets the parent path of the device
    """
    def get_parent_path():
        return None



"""
Joystick class. Sends events to our Unity application of the current state of the joystick
"""
class Joystick(DragonMasterDevice):

    pass

"""
Printer device handles printer events. Sends the status of the printer to Unity
"""
class Printer(DragonMasterDevice):

    pass

"""
Child class of our printer object. This handles special properties for our Custom TG02 printer
"""
class CustomTG02(Printer):

    pass

"""
Extension of our printer class. This handles special properties for our Reliance Printer
"""
class ReliancePrinter(Printer):

    pass