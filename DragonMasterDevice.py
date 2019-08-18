import DragonMasterDeviceManager


"""
The Base class for all our Dragon Master Devices
"""
class DragonMasterDevice:

    def __init__(self, dragonMasterDeviceManager):
        self.dragonMasterDeviceManager = dragonMasterDeviceManager


class Joystick(DragonMasterDevice):

    pass

class Printer(DragonMasterDevice):

    pass

class ReliancePrinter(DragonMasterDevice):

    pass