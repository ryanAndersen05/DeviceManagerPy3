#std. lib imports
import time
from time import time
from time import sleep
import re

#external imports
import serial
import serial.tools.list_ports
import threading

#internal project imports
import DragonMasterDevice
import DragonMasterDeviceManager

"""
The base class for all devices that use Serial communication
"""
class SerialDevice(DragonMasterDevice.DragonMasterDevice):

    SERIAL_NOT_POLLING = 0
    SERIAL_WAIT_FOR_EVENT = 1
    SERIAL_IGNORE_EVENT = 2


    def __init__(self, deviceManager):
        DragonMasterDevice.DragonMasterDevice.__init__(self, deviceManager)
        self.serialObject = None
        self.pollingDevice = False
        self.serialState = SerialDevice.SERIAL_NOT_POLLING
        self.comport = None
        return

    """
    The start device method in our serial device begins the polling process to search for 
    packets to the read in from our serial device
    """
    def start_device(self, deviceElement):
        DragonMasterDevice.DragonMasterDevice.start_device(self, deviceElement)
        self.comport = deviceElement.device

        pollingThread = threading.Thread(target=self.poll_serial_thread)
        pollingThread.daemon = True
        pollingThread.start()
        return False

    """
    We will want to close our serial port upon disconnecting our device
    """
    def disconnect_device(self):
        self.pollingDevice = False
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
                self.serialObject = None
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
            self.dragonMasterDeviceManager.remove_device(self)
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
    #region Constants
    DBV_DESCRIPTION = "DBV-400"
    DBV_BAUDRATE = 9600
    UID = 0x42
    #endregion
    #region Commands

    STATUS_REQUEST = bytearray([0x12, 0x08, 0x00, 0x00, 0x00, 0x10, 0x10, 0x00])
    POWER_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x81, 0x00, 0x00, 0x06])
    SET_UID = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x20, 0x01, 0x00, 0x01])
    RESET_REQUEST = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x00, 0x11, 0x00])
    INHIBIT_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x01, 0x82, 0x00, 0x01, 0x06])
    INHIBIT_REQUEST = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x00, 0x12, 0x00])
    IDLE_REQUEST = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x00, 0x13, 0x10])
    IDLE_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x01, 0x83, 0x01, 0x11, 0x06])
    ESCROW_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x01, 0x85, 0x02, 0x11, 0x06])
    BILL_REJECT = bytearray([0x12, 0x09, 0x00, 0x10, 0x02, 0x80, 0x04, 0x11, 0x06])
    ERROR_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x80, 0x01, 0x12, 0x06])
    STACK_INHIBIT = bytearray([0x12, 0x08, 0x00, 0x10, 0x02, 0x00, 0x14, 0x10])
    VEND_VALID_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x02, 0x86, 0x03, 0x11, 0x06])
    ERROR_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x80, 0x01, 0x12, 0x06])
    HOLD_BILL = bytearray([0x12, 0x0a, 0x00, 0x10, 0x01, 0x00, 0x16, 0x10, 0x3c, 0x00])

    REJECT_COMMAND = bytearray([0x12, 0x08, 0x00, 0x10, 0x2a, 0x00, 0x15, 0x10])
    REJECT_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x2a, 0x00, 0x05, 0x11, 0x06])

    NOTE_STAY_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x2a, 0x87, 0x01, 0x13, 0x06])

    DENOM_GET = bytearray([0x12,0x08,0x00,0x10,0x01,0x10,0x21,0x10])
    DENOM_DISABLE = bytearray([0x12,0x0a,0x00,0x10,0x10,0x20,0x21,0x10,0x00,0x00])

    # ENABLE_1 = True # $1
    # ENABLE_5 = True # $5
    # ENABLE_10 = True # $10
    # ENABLE_20 = True # $20
    # ENABLE_50 = True # $50
    # ENABLE_100 = True # $100

    #endregion
    #region States

    NOT_INIT_STATE = 0 # DBV not initialized.
    POWER_UP_NACK_STATE = 1 # Power up ACK not received by DBV yet. Write POWER_UP_ACK to DBV (with event id set) to move past this.
    POWER_UP_STATE = 2 # DBV UID set and powered on. Needs to be reset.
    IDLE_STATE = 3  # DBV can accept bills in this state. Bezel light on.
    INHIBIT_STATE = 4 # DBV CANNOT accept bills in this state. Bezel light off.
    ESCROW_STATE = 5 # DBV is currently accepting a bill
    UNSUPPORTED_STATE = 6  # UID not set. Write SET_UID to DBV UID and move past this state.
    ERROR_STATE = 7 # DBV has encountered an error. Reset the DBV or wait for error to clear.
    ERROR_STATE_STACKER_FAILURE = 8 # The stacker has error when attempting to accept credits. This can usually be fixed with a reset.
    ERROR_STATE_BOX_REMOVED = 9 # The container where credits are stored in the DBV has been removed. This might mean that the operator is removing the credits inserted.
    ERROR_STATE_ACCEPTOR_JAM = 10 # The stacker on top of the DBV has been removed for a few seconds. Re-insert it, and reset.
    CLEAR_STATE = 11  # DBV error has cleared.
    NOTE_STAY_STATE = 12 # A bill has been left in the acceptor slot of the DBV. When removed, the DBV will proceed as normal.

    #endregion
    #region variables
    UidSet = False
    State = NOT_INIT_STATE
    #endregion

    def __init__(self, deviceManager):
        super().__init__(deviceManager)
        return

    #region on data received

    def on_data_received_event(self):
        read = self.read_from_serial()
        if read == None or len(read) < 2:
            return
        length = read[1]
        print (read.hex())
        print (length)
        if (length <= 8):
            if read[6] == 0x00 and read[7] == 0x01:
                self.on_inhibit_success(read)
            elif read[6] == 0x01 and read[7] == 0x11:
                self.on_idle_success(read)
        elif (length <= 9):
            if read[6] == 0x11 and read[7] == 0x00 and read[8] == 0x06:
                self.on_reset_request_received()
            elif read[8] == 0xE2:
                self.on_unsupported_received(read)
            elif read[5] == 0x20 and read[6] == 0x01 and read[7] == 0x00:
                self.on_uid_success()
            elif read[6] == 0x12 and read[7] == 0x00:
                self.on_inhibit_request_received()
            elif read[6] == 0x13 and read[7] == 0x10:
                self.on_idle_request_received()
        elif (length >= 10):
            if read[7] == 0x00 and read[8] == 0x06 and read[9] == 0x04:
                self.on_status_update_received(read)
            elif read[6] == 0x00 and read[7] == 0x00:
                self.on_power_up_nack_received(read)

    #endregion

    #region on read methods
    
    def on_status_update_received(self, message):
        print ("Status")
        if message[10] == 0x00 and message[11] == 0x00:
            self.on_power_up_success()
        if message[10] == 0x00 and message[11] == 0x01:
            self.State = DBV400.INHIBIT_STATE
        if message[10] == 0x01 and message[11] == 0x011:
            self.State = DBV400.IDLE_STATE

        print("New State: " + str(self.State))
    def on_power_up_nack_received(self,message):
        print("power up nack received")
        powerUpAck = DBV400.POWER_ACK
        powerUpAck[5] = message[5]
        self.State = DBV400.POWER_UP_NACK_STATE
        #self.serialObject.flushInput()
        #self.serialObject.flushOutput()
        self.send_dbv_message(powerUpAck)
        sleep(.05)
        self.send_dbv_message(DBV400.STATUS_REQUEST)

    def on_power_up_success(self):
        print("power up success")
        self.power_up_dbv()
        
    def on_unsupported_received(self,message):
        self.State = DBV400.UNSUPPORTED_STATE
        self.UID = message[4]
        self.UidSet = True
        self.send_dbv_message(DBV400.STATUS_REQUEST)

    def on_uid_success(self):
        self.UidSet = True
        self.reset_dbv()

    def on_reset_request_received(self):
        print("resetting")

    def on_inhibit_request_received(self):
        print("inhibit received")
    
    def on_inhibit_success(self,message):
        inhibitMessage = DBV400.INHIBIT_ACK
        inhibitMessage[5] = message[5]
        self.State = DBV400.INHIBIT_STATE
        print("New state: INHIBIT")
        self.send_dbv_message(inhibitMessage)
        sleep(2)
        self.idle_dbv()

    def on_idle_request_received(self):
        print("idle request received")
    
    def on_idle_success(self,message):
        idleMessage = DBV400.IDLE_ACK
        idleMessage[5] = message[5]
        self.State = DBV400.IDLE_STATE
        print("New state: IDLE")
        self.send_dbv_message(idleMessage)
        sleep(.5)
        self.inhibit_dbv()
        
    #endregion

    #region Command Methods

    def send_dbv_message(self, message):
        if self.UidSet == True:
            print("setting uid")
            message[4] = self.UID
        print("message: " + str(type(message)))
        print (message)
        self.write_to_serial(message)

    def set_uid(self):
        uidMessage = DBV400.SET_UID
        uidMessage[8] = self.UID
        self.send_dbv_message(uidMessage)

    def idle_dbv(self):
        if self.State != DBV400.INHIBIT_STATE:
            return
        self.send_dbv_message(DBV400.IDLE_REQUEST)
    
    def inhibit_dbv(self):
        if self.State != DBV400.IDLE_STATE:
            return
        self.send_dbv_message(DBV400.INHIBIT_REQUEST)
    
    def power_up_dbv(self):
        self.set_uid()
    
    def reset_dbv(self):
        if (self.State == DBV400.ERROR_STATE_BOX_REMOVED or self.State == DBV400.ERROR_STATE_ACCEPTOR_JAM):
            return
        self.send_dbv_message(DBV400.RESET_REQUEST)
    
    def get_dbv_state(self):
        message = DBV400.STATUS_REQUEST
        if self.UidSet:
            message[3] = 0x10
        self.send_dbv_message(message)
    
    #endregion

    #region Override Methods
    def start_device(self, deviceElement):
        self.serialObject = self.open_serial_device(deviceElement.device, DBV400.DBV_BAUDRATE, 5, 5)
        print (self.serialObject)
        if self.serialObject == None:
            return False

        super().start_device(deviceElement)
        # self.serialObject.flush()
        self.send_dbv_message(DBV400.STATUS_REQUEST)
        return True

    def to_string(self):
        return "DBV-400"
    #endregion

    pass


"""
Class that maanages our Draxboard communication and state
"""
class Draxboard(SerialDevice):
    
    REQUEST_STATUS = bytearray([0x01, 0x00, 0x01, 0x02])
    SET_OUTPUT_STATE = bytearray([0x04, 0x02, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00])
    DRAXBOARD_OUTPUT_ENABLE = bytearray([0x02, 0x05, 0x09, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x12])
    METER_INCREMENT = bytearray([0x09, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00])

    #region const varialbes
    ##METER INDEX 
    IN_METER = 0x00
    OUT_METER = 0x01
    IN_METER_MACHINE = 0x02#In some cases our draxboard will have 4 meters. 3 and 4 are meant to represent the machine money in/out
    OUT_METER_MACHINE = 0x03

    ##Return Packet Data
    REQUEST_STATUS_ID = 0x01
    REQUEST_STATUS_SIZE = 18
    INPUT_EVENT_ID = 0xfa
    INPUT_EVENT_SIZE = 9
    OUTPUT_EVENT_ID = 0x04
    OUTPUT_EVENT_SIZE = 8
    METER_INCREMENT_ID = 0x09
    METER_INCREMENT_SIZE = 7
    PENDING_METER_ID = 0x0a
    PENDING_METER_SIZE = 7

    ##Input Bytes
    INPUT_INDEX = 3
    DOOR_STATE_INDEX = 7

    ##Draxboard Properties
    DRAX_BAUDRATE = 115200
    DRAX_DESCRIPTION = "DRAX - CDC-ACM 2"
    ALT_DRAX_DESCRIPTION = "Dual RS-232 Emulation - CDC-ACM 1"
    #endregion const variables

    def __init__(self, deviceManager):
        super().__init__(deviceManager)
        self.versionNumberHigh = 0
        self.versionNumberLow = 0
        self.draxOutputState = 0
        self.playerStationNumber = 0

        self.playerStationHash = 0#The player station hash is a value assigned only to our Draxboard. It is a value derived from the usb path to our draxboard
        return

    #region Override methods
    def start_device(self, deviceElement):

        self.serialObject = self.open_serial_device(deviceElement.device, Draxboard.DRAX_BAUDRATE, 5, 5)
        if self.serialObject == None:
            return False

        requestStatus = self.write_serial_check_for_input_events(self.REQUEST_STATUS, Draxboard.REQUEST_STATUS_ID, Draxboard.REQUEST_STATUS_SIZE)
        if requestStatus == None:
            print ("Request Status Was None")
            return False
        if len(requestStatus) < Draxboard.REQUEST_STATUS_SIZE or requestStatus[0] != Draxboard.REQUEST_STATUS_ID:
            print ("Reqeust Status length was too short or invalid: " + str(requestStatus))
            return False


        self.versionNumberHigh = requestStatus[15]
        self.versionNumberLow = requestStatus[16]

        self.playerStationNumber = requestStatus[10]
        if self.write_serial_wait_for_read(self.DRAXBOARD_OUTPUT_ENABLE) == None:
            print ("Output Enable was not successful")
            return False

        read = self.toggle_output_state_of_drax(0x180f)
        if read == None:
            print ("Default output assignement was not successful")
            return False
        super().start_device(deviceElement)
        self.playerStationHash = self.get_draxboard_device_path_hash(deviceElement)
        
        return True


    def fetch_parent_path(self, deviceElement):
        devToReturn = None
        timesWeWereFound = 0
        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if dev.device_path.__contains__(deviceElement.location) and dev.device_path.__contains__(deviceElement.name):
                timesWeWereFound += 1
                devToReturn = dev.parent.parent.parent.device_path

        
        return devToReturn

    

    """
    This primarily for retrieving player input as that is the only case where we do not write an event before expecting
    a response. Inputs are driven entirely by our players and as such can happen at any time
    """
    def on_data_received_event(self):
        if self.serialState != SerialDevice.SERIAL_WAIT_FOR_EVENT:
            return

        readEvent = self.read_from_serial(2)

        if readEvent == None:
            print ("Draxboard read event was none....")
            return

        for i in range(int(len(readEvent) / Draxboard.INPUT_EVENT_SIZE)):
            tempLine = readEvent[i*Draxboard.INPUT_EVENT_SIZE:(i+1*Draxboard.INPUT_EVENT_SIZE)]
            self.check_packet_for_input_event(tempLine)

    """
    To string displays the comport of the drax device
    """
    def to_string(self):
        if (self.comport != None):
            return "Draxboard (" + self.comport + ")"
        else:
            return "Draxboard (Missing)"

    """
    This method returns a hash value that is a derivation of the physical path our draxboard device.

    This creates an integer has that we can use to identify our player station group of devices
    This is based entirely on the usb path of our draxboard, so it should be unique
    """
    def get_draxboard_device_path_hash(self, draxElement):
        try:
            split = draxElement.location.split(':')
            splitUp = split[0].split('-')
            hashString = ""

            for st in splitUp:
                for value in st.split('.'):
                    hashString += value
            playerStationHash = int(hashString)

            return playerStationHash
        except Exception as e:
            print ("There was an error trying to create the draxboard hash")
            print (e)
            return 0

            
    #endregion Override Methods
    """
    Sets up and adds an input packet to our TCP queue, so that it can be sent at the next availability
    """
    def add_input_event_to_tcp_queue(self, inputPacket):
        if inputPacket == None or len(inputPacket) < Draxboard.INPUT_EVENT_SIZE or inputPacket[0] != Draxboard.INPUT_EVENT_ID:
            print ("Invalid Input Event Packet. Please Be sure you are correctly interpreting our input packets")
            return
        inputPacketToSend = [DragonMasterDeviceManager.DragonMasterDeviceManager.DRAX_INPUT_EVENT, inputPacket[Draxboard.INPUT_INDEX], inputPacket[Draxboard.DOOR_STATE_INDEX]]
        self.dragonMasterDeviceManager.add_event_to_send(inputPacketToSend)
        return

    """
    Due to the fact that we can receive inputs from the player while attempting to write an event to the draxboard, it is
    possible that the response may contain an input events that we want to filter out and send to our tcp queue in our device manager
    """
    def write_serial_check_for_input_events(self, messageToWrite, responseID, responseSize):
        read = self.write_serial_wait_for_read(messageToWrite)
        validRead = None

        while read != None and len(read) > 0:
            if read[0] == responseID:
                if len(read) <= responseSize:
                    return read
                else:
                    validRead = read[0:responseSize]
                    read = read[responseSize:len(read)]
            elif self.check_packet_for_input_event(read):
                if len(read) <= Draxboard.INPUT_EVENT_SIZE:
                    read = self.read_from_serial(5)
                else:
                    read = read[Draxboard.INPUT_EVENT_SIZE:len(read)]
            else:
                return validRead
        return validRead

    """
    Toggles the draxboard output state. This can control certain functions of the draxboard such as
    the bell, joystick vibrators, button lights, etc

    There are 3 types of toggles
        Type 0 - output that is passed through is what the state will be
        Type 1 - output bit enable (Use this to toggle only one bit on)
        Type 2 - output bit disable (Use this to toggle one bit off)
    """
    def toggle_output_state_of_drax(self, outputToggleu32, toggleMessageType=0):
        if toggleMessageType == 0:
            pass
            # self.draxOutputState = outputToggleu32
        elif toggleMessageType == 1:
            outputToggleu32 = self.draxOutputState | outputToggleu32
        elif toggleMessageType == 2:
            outputToggleu32 = self.draxOutputState & (~outputToggleu32)
        else:
            return None

        byte1 = outputToggleu32 >> 24 & 0xff
        byte2 = outputToggleu32 >> 16 & 0xff
        byte3 = outputToggleu32 >> 8 & 0xff
        byte4 = outputToggleu32 >> 0 & 0xff

        outputMessageArray = self.SET_OUTPUT_STATE.copy()
        checkSumByteIndex = 7
        outputMessageArray[3] = byte4
        outputMessageArray[4] = byte3
        outputMessageArray[5] = byte2
        outputMessageArray[6] = byte1
        outputMessageArray[checkSumByteIndex] = self.calculate_checksum(outputMessageArray)


        read = self.write_serial_check_for_input_events(outputMessageArray, Draxboard.OUTPUT_EVENT_ID, Draxboard.OUTPUT_EVENT_SIZE)
        if read != None and len(read) >= Draxboard.OUTPUT_EVENT_SIZE and read[0] == Draxboard.OUTPUT_EVENT_ID:
            self.draxOutputState = read[4] + read[3] * 255
            self.send_current_drax_output_state(read[4], read[3])

        return read
        
    """
    Sends a packet to our TCP Manager that contains the output state of the draxboard
    """
    def send_current_drax_output_state(self, byte1, byte2):
        packetToSend = [DragonMasterDeviceManager.DragonMasterDeviceManager.DRAX_OUTPUT_EVENT, byte1, byte2]
        self.dragonMasterDeviceManager.add_event_to_send(packetToSend)
        return

        
    """
    This method verifies that there is an input event packet that can be read in. This method will also send
    an input method to the tcp queue if there is a valid input found when searching
    """
    def check_packet_for_input_event(self, inputPacketLine):
        if inputPacketLine == None:
            return False
        if inputPacketLine[0] == 0xfa and len(inputPacketLine) >= Draxboard.INPUT_EVENT_SIZE:
            self.add_input_event_to_tcp_queue(inputPacketLine)
            return True
        return False
    
    pass

    """
    Returns the checksum of the packet that we are going to send to our Draxboard serail
    """
    def calculate_checksum(self, packetWeAreSending):
        return sum(packetWeAreSending) % 256

"""
Supplimentary class to our reliance printers. This class talks to the reliance printer through
serial communication to retrieve the state of the device and the paper level. Handles other printer
commands that are special to the reliance printer as well
"""
class ReliancePrinterSerial(SerialDevice):
    #####Command List for Reliance Printer#####
    PRINTER_STATUS_REQUEST = bytearray([0x10, 0x04, 0x14])
    PAPER_STATUS_REQUEST = bytearray([0x10, 0x04, 0x04])
    PAPER_FULL_CUT = bytearray([0x1b, 0x69])
    PAPER_RETRACT = bytearray([0x1d, 0x65, 0x02])
    PAPER_PRESENT_TO_CUSTOMER = bytearray([0x1d, 0x65, 0x20, 0x0c, 0x0a])

    RELIANCE_BAUDE_RATE = 19200
    RELIANCE_SERIAL_DESCRIPTION = "Reliance"

    def __init__(self, deviceManager, associatedReliancePrinter):
        super().__init__(deviceManager)
        self.associatedReliancePrinter = associatedReliancePrinter
        return

    def start_device(self, deviceElement):
        self.serialObject = self.open_serial_device(deviceElement.device, ReliancePrinterSerial.RELIANCE_BAUDE_RATE, readTimeout=3, writeTimeout=15)
        if self.serialObject == None:
            return False
        try:
            super().start_device(deviceElement)
        except Exception as e:
            print ("There was an error starting our Reliance Printer")
            print (e)

        return True 

    """
    NOTE: Make it so that we properly disconnect our printer at the end of this method.
    If we are no longer polling for events, we should disconnect
    """
    def poll_serial_thread(self):
        super().poll_serial_thread()
        
    """
    Disconnects both our serial 
    """
    def disconnect_device(self):
        if not self.pollingDevice:
            return
        self.associatedReliancePrinter.disconnect_device()
        super().disconnect_device()

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


    def __init__(self, deviceManager):
        SerialDevice.__init__(self, deviceManager)
        return
    """
    Omnidongle start flushes out left over messages on start
    """
    def start_device(self, deviceElement):
        self.dragonMasterDeviceManager.CONNECTED_OMNIDONGLE = self
        self.serialObject = self.open_serial_device(deviceElement.device, Omnidongle.OMNI_BAUD_RATE, readTimeout=3, writeTimeout=3)
        if self.serialObject == None:
            return False
        try:
            self.dragonMasterDeviceManager.CONNECTED_OMNIDONGLE = self
            self.serialObject.flush()
            SerialDevice.start_device(self, deviceElement)
            
        except Exception as e:
            print ("There was an error flushing out the Omnidongle")
            print (e)
            return False
        return True

    """
    The parent path for our Omnidongle is not important as it is not assigned to any
    Player Station
    """
    def fetch_parent_path(self, deviceElement):
        return None

    """
    Disconnect our omnidongle by setting our CONNECTED_OMNIDONGLE value
    to None
    """
    def disconnect_device(self):
        
        SerialDevice.disconnect_device(self)
        if (self.dragonMasterDeviceManager.CONNECTED_OMNIDONGLE == self):
            self.dragonMasterDeviceManager.CONNECTED_OMNIDONGLE = None
        return

    """
    To string method that shows the omnidongle description
    """
    def to_string(self):
        return "POM Omnidongle"

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
        self.dragonMasterDeviceManager.add_event_to_send(responsePacket)#We send the response packet that our omnidongle returns after calculating the packet
        return

    def to_string(self):
        if self.comport != None:
            return "POM Omnidongle (" + self.comport + ")"
        else:
            return "POM Omnidongle (Missing)"

    
    pass


##Search Device Methods

"""
Returns a list of all connected DBV 400 comports
"""
def get_all_connected_dbv400_comports():
    dbv400Elements = []
    allPorts = serial.tools.list_ports.comports()

    for element in allPorts:
        if element.description.__contains__(DBV400.DBV_DESCRIPTION):
            dbv400Elements.append(element)
    
    return dbv400Elements

"""
Returns the first omnidongle comport that we find
"""
def get_omnidongle_comports():
    allPorts = serial.tools.list_ports.comports()

    for element in allPorts:
        if element.description.__contains__(Omnidongle.OMNI_SERIAL_DESCRIPTION):
            return element

    return None

"""
Returns a list of all the connected draxboards that are found in our system
"""
def get_all_connected_draxboard_elements():
    allPorts = serial.tools.list_ports.comports()
    draxboardElements = []
    for element in allPorts:
        if element.description.__contains__(Draxboard.DRAX_DESCRIPTION) or element.description.__contains__(Draxboard.ALT_DRAX_DESCRIPTION):
            draxboardElements.append(element)

    return draxboardElements

"""
Returns a list of all Reliance serial comports
"""
def get_all_reliance_printer_serial_elements():
    allPorts = serial.tools.list_ports.comports()
    relianceElements = []
    for element in allPorts:
        if element.description.__contains__(ReliancePrinterSerial.RELIANCE_SERIAL_DESCRIPTION):
            print (element.location)
            relianceElements.append(element)

    return relianceElements

#End Search Device Methods