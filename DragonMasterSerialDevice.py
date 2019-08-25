#STD lib imports
import time
from time import sleep
import re

#external imports
import serial
import serial.tools.list_ports
import threading

#project imports
import DragonMasterDevice
import DragonMasterDeviceManager


"""
The base class for all devices that use Serial communication
"""
class SerialDevice(DragonMasterDevice.DragonMasterDevice):

    SERIAL_NOT_POLLING = 0
    SERIAL_WAIT_FOR_EVENT = 1
    SERIAL_IGNORE_EVENT = 2

    def __init__(self, deviceManager, comport, baudrate = 9600):
        self.comport = comport
        self.baudrate = baudrate
        self.serialObject = None
        self.pollingDevice = False
        self.serialState = SerialDevice.SERIAL_NOT_POLLING
        return

    def start_device(self):
        self.serialObject = self.open_serial_device()

        
    #Universal Serial Methods
    def on_data_received_event(self):
        pass



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
        serialDevice = self.serialObject
        self.pollingDevice = True
        self.serialState = SerialDevice.SERIAL_WAIT_FOR_EVENT
        try:
            while self.pollingDevice:
                if self.serialState == SerialDevice.SERIAL_WAIT_FOR_EVENT  and serialDevice.in_waiting > 1:
                        self.on_data_received_event()
                sleep(.016)#Adding a sleep so that we do not consume all the resources and allow python to run other threads
        except Exception as e:
            print ("There was an error polling device " + self.to_string())
            print (e)
            self.deviceManager.remove_device(self)
            self.pollingDevice = False  # Thread will end if there is an error polling for a device

        print (self.to_string() + " no longer polling for events")#Just want this for testing. want to remove later

    #READ/WRITE Methods
    """
    Returns a message if there is one available to read from our serial device
    """
    def read_from_serial(self, delayBeforeReadMilliseconds = 0):
        sleepDelay = float(delayBeforeReadMilliseconds) / 1000
        self.serialState = SerialDevice.SERIAL_IGNORE_EVENT
        if sleepDelay > 0:
            sleep(sleepDelay)
        
        try:
            inWaiting = self.serialObject.in_waiting
            readLine = self.serialObject.read(size=inWaiting)
            self.serialState = SerialDevice.SERIAL_WAIT_FOR_EVENT
            return readLine
        except Exception as e:
            print ("There was an error reading from our device")
            print (e)


    #End READ/WRITE Methods
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