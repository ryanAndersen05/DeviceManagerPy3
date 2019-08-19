import DragonMasterDevice
import DragonMasterDeviceManager
import serial


"""
The base class for all devices that use Serial communication
"""
class SerialDevice(DragonMasterDevice.DragonMasterDevice):

    def __init__(self, deviceManager,):

        return
    pass

"""
A class that handles all our Bill Acceptor Actions
"""
class DBV400(SerialDevice):

    def __init__(self, deviceManager):

        return
    pass


"""
Class that maanages our Draxboard communication and state
"""
class Draxboard(SerialDevice):

    def __init__(self, deviceManager):
        return

    pass

"""
Supplimentary class to our reliance printers. This class talks to the reliance printer through
serial communication to retrieve the state of the device and the paper level. Handles other printer
commands that are special to the reliance printer as well
"""
class ReliancePrinterSerial(SerialDevice):
    def __init__(self, deviceManager):

        return

    pass

"""
Class that handles communication with our connected omnidongle. Unlike other classes that handle the state and functionality of
our device, this class strictly relays packets between this device and our Unity Application. Only state we are concerned with
in this class is whether or not it is connected
"""
class Omnidongle(SerialDevice):
    def __init__(self, deviceManager):

        return

    pass