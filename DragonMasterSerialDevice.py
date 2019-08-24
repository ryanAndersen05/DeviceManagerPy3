from time import sleep
from time import time

import serial
import serial.tools.list_ports
import DragonMasterDevice
import DragonMasterDeviceManager


"""
The base class for all devices that use Serial communication
"""
class SerialDevice(DragonMasterDevice.DragonMasterDevice):

    

    def __init__(self, deviceManager, comport, baudrate = 9600):
        self.comport = comport
        self.baudrate = baudrate
        self.serialObject = None
        return

    def start_device(self):
        self.serialObject = self.open_serial_device()
    #Universal Serial Methods
    """
    Method used to safely open our serial device
    """
    def open_serial_device(self, comport, baudrate, readTimeout, writeTimeout):
        try:
            serialObject = serial.Serial(
                port=comport,
                baudrate=baudrate,
                parity=serial.PARITY_NONE,
                bytesize=serial.EIGHTBITS,
                timeout=5,
                writeTimeout=writeTimeout,
                stopbits = serial.STOPBITS_ONE
            )
            return serialObject
        except(OSError, serial.SerialException, Exception) as e:
            print ("There was an error attempting to open our serrial port: " + comport)
            print (e)
        return None

    """
    Method used to safely close out of our serial port
    """
    def close_serial_device(self):
        if (self.serialObject == None):
            return
        
        if (self.serialObject.isOpen):
            try:
                self.serialObject.close()
                print ("Serial Device (" + self.serialObject.port + ") successfully closed")
            except Exception as e:
                print ("There was an error closing our port")
                print (e)
    """
    Polls a serial thread to check if at any point there is something to read from a given serial device
    """
    def poll_serial_thread(self):
        serialDevice = dragonMasterSerialDevice.serialDevice
        try:
            while dragonMasterSerialDevice.pollDeviceForEvent:

                if not dragonMasterSerialDevice.blockReadEvent and serialDevice.in_waiting > 1:
                        dragonMasterSerialDevice.on_data_received_event()
                sleep(.016)#
        except:
            # print serialDevice
            print ("There was an error polling device " + dragonMasterSerialDevice.to_string())
            dragonMasterSerialDevice.deviceManager.remove_device(dragonMasterSerialDevice)
            dragonMasterSerialDevice.pollDeviceForEvent = False  # Thread will end if there is an error polling for a device

        print (dragonMasterSerialDevice.to_string() + " no longer polling for events")#Just want this for testing. want to remove later
    #End Universal Serial Methods
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