#std. lib imports
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

    """
    Check to ensure that our serial device is still connected and functioning. This is more
    of a backup check as ending polling should be immediate grounds to disconnect our device
    """
    def has_device_errored(self):
        try:
            return not self.serialObject.is_open or self.serialState == SerialDevice.SERIAL_NOT_POLLING
        except Exception as e:
            print ("There was an error attempting to ")


    def start_device(self):
        print ("You have not set up a proper start function for your Serial Device")
        return False

    """
    We will want to close our serial port upon disconnecting our device
    """
    def disconnect_device(self):
        self.close_serial_device()
        self.serialState = SerialDevice.SERIAL_NOT_POLLING
        return

        
    #Universal Serial Methods
    def on_data_received_event(self):
        return



    """
    Method used to safely open our serial device
    """
    def open_serial_device(self, comport, baudrate, readTimeout=5, writeTimeout=5):
        try:
            serialObject = serial.Serial(
                port=comport,
                baudrate=baudrate,
                parity=serial.PARITY_NONE,
                bytesize=serial.EIGHTBITS,
                timeout=readTimeout,
                writeTimeout=writeTimeout,
                stopbits = serial.STOPBITS_ONE
            )
            return serialObject
        except(OSError, serial.SerialException, Exception) as e:
            print ("There was an error attempting to open our serrial port: " + comport)
            print (e)
        return None#If we failed to create a serial object we will return None

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
        return

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
            self.serialState = SerialDevice.SERIAL_WAIT_FOR_EVENT
        return

    """
    Safely writes a message to our serial object
    
    NOTE: Please be sure that the message is of the type 'bytearray'
    """
    def write_to_serial(self, messageToSend):
        try:
            self.serialObject.write(messageToSend)
        except Exception as e:
            print ("There was an error writing to our serial device")
            print (e)
        return

    """
    In many cases with our serial devices, we will want to send a message and we will expect a response to that message.
    For this it is recommended that you use this method.
    """
    def write_serial_wait_for_read(self, messageToSend, minBytesToRead=1, maxMillisecondsToWait=10, delayBeforeReadMilliseconds=0):
        self.serialState = SerialDevice.SERIAL_IGNORE_EVENT
        maxMillisecondsToWaitConverted = float(maxMillisecondsToWait) / 1000

        try:
            self.serialObject.write(messageToSend)
        except Exception as e:
            print ("There was an error writing to our serial device")
            print (e)
            self.serialState = SerialDevice.SERIAL_WAIT_FOR_EVENT
            return None

        initialTime = time()
        try:
            while time() - initialTime < maxMillisecondsToWaitConverted:
                if (self.serialObject.in_waiting >= minBytesToRead):
                    if (delayBeforeReadMilliseconds > 0):
                        sleep(float(delayBeforeReadMilliseconds) / 1000)
                    inWaiting = self.serialObject.in_waiting
                    readLine = self.serialObject.read(size=inWaiting)
                    return readLine
        except Exception as e:
            print ("There was a problem reading from our device")
            print (e)
            self.serialState = SerialDevice.SERIAL_WAIT_FOR_EVENT
            return None

        print ("Serial Read Timed Out")
        self.serialState = SerialDevice.SERIAL_WAIT_FOR_EVENT
        return None


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

    """
    NOTE: Make it so that we properly disconnect our printer at the end of this method.
    If we are no longer polling for events, we should disconnect
    """
    def poll_serial_thread(self):
        super().poll_serial_thread()
    pass

"""
Class that handles communication with our connected omnidongle. Unlike other classes that handle the state and functionality of
our device, this class strictly relays packets between this device and our Unity Application. Only state we are concerned with
in this class is whether or not it is connected
"""
class Omnidongle(SerialDevice):
    OMNI_BAUD_RATE = 19200
    OMNI_BIT_RATE = 8
    OMNI_SERIAL_DESCRIPTION = "POM OmniDongle"


    def __init__(self, deviceManager, comport):
        SerialDevice.__init__(self, deviceManager, comport)
        return
    """
    Omnidongle start flushes out left over messages on start
    """
    def start_device(self):
        self.serialObject = self.open_serial_device(self.comport, Omnidongle.OMNI_BAUD_RATE, readTimeout=3, writeTimeout=3)
        if self.serialObject == None:
            return False
        try:
            self.serialObject.flush()
        except Exception as e:
            print ("There was an error flushing out the Omnidongle")
            print (e)
            return False
        return True

    def set_parent_path(self):
        return

    """
    Disconnect our omnidongle by setting our CONNECTED_OMNIDONGLE value
    to None
    """
    def disconnect_device(self):
        SerialDevice.disconnect_device(self)
        if (self.deviceManager.CONNECTED_OMNIDONGLE == self):
            self.deviceManager.CONNECTED_OMNIDONGLE = None
        return

    """
    Sends a packet to our omnidongle. This should result in a message that we can return to our
    Unity Application
    """
    def send_data_to_omnidongle(self, packetToSend):
        if (packetToSend == None):
            print ("Packet to send was None")
            return
        if (len(packetToSend) <= 1):
            print ("Our packet length was too short")
            return
        
        responsePacket = self.write_serial_wait_for_read(self, packetToSend, minBytesToRead=7, maxMillisecondsToWait=2000, delayBeforeReadMilliseconds=25)
        if (responsePacket != None):
            responsePacket.insert(0, DragonMasterDeviceManager.DragonMasterDeviceManager.OMNI_EVENT)
        else:
            print ("Our response packet was returned as None")
            return
        self.deviceManager.add_event_to_send(responsePacket)#We send the response packet that our omnidongle returns after calculating the packet
        return

    
    pass