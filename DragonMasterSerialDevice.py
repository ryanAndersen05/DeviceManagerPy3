#std. lib imports
import time
from time import time
from time import sleep
import re
import queue
import os

#external imports
import serial
import serial.tools.list_ports
import threading

#internal project imports
import DragonMasterDevice
import DragonMasterDeviceManager

"""
@author Ryan Andersen, EQ Games, Phone #: (404-643-1783)

The base class for all devices that use Serial communication
"""
class SerialDevice(DragonMasterDevice.DragonMasterDevice):

    #region serial states

    #These are not used outside of this class
    SERIAL_NOT_POLLING = 0
    SERIAL_WAIT_FOR_EVENT = 1
    SERIAL_IGNORE_EVENT = 2
    #endregion serial states


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
    """
    All serial classes will be running a thread to see if there are any events ready to be received. This event will trigger upon one byte being read in. You must read the rest
    in after the event is called.

    firstByteOfPacket will be of type bytes()
    """
    def on_data_received_event(self, firstByteOfPacket):

        return



    """
    Method used to safely open our serial device
    """
    def open_serial_device(self, comport, baudrate, readTimeout=5, writeTimeout=5):
        self.comport = comport
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
                firstReadByte = self.serialObject.read(1)
                if firstReadByte != None and len(firstReadByte) > 0:
                    self.on_data_received_event(firstReadByte)

        except Exception as e:
            print ("There was an error polling device " + str(self.get_player_station_hash()) + ", Error: " + self.to_string())
            print (e)
            self.on_poll_serial_errored()
            self.pollingDevice = False  # Thread will end if there is an error polling for a device



        print (self.to_string() + " no longer polling for events")#Just want this for testing. want to remove later
        return


    """
    Upon a poll error experienced, this method will be called. Add any clean up that is necessary into this method
    as an override
    """
    def on_poll_serial_errored(self):
        self.dragonMasterDeviceManager.remove_device(self)

    #READ/WRITE Methods


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

    #End READ/WRITE Methods
    #End Universal Serial Methods
    pass

"""
Base class for our Bill Acceptors. This is a class that can apply to every bill acceptor that we add to the project.
"""
class BillAcceptor(SerialDevice):
    DBV_DESCRIPTION = ""

    """
    Returns a byte code that represents the type of the bill acceptor that is being used
    """
    def get_ba_type(self):
        return 0
    pass

"""
@author Aaron Thurston, EQ Games/Kaneva, Phone#: 404-680-2119 (Lead Programmer for DBV)
@author Ryan Andersen, EQ Games, Phone#: 404-643-1783 (Support programmer for DBV)

A class that handles all our Bill Acceptor Actions
"""
class DBV400(BillAcceptor):
    FIRMWARE_UPDATE_FILE_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "DBV400_LatestFirmware.bin")
    #region Constants
    DBV_DESCRIPTION = "DBV-400"
    DBV_BAUDRATE = 9600
    UID = 0x42
    #endregion
    #region Commands

    STATUS_REQUEST = bytearray([0x12, 0x08, 0x00, 0x10, 0x00, 0x10, 0x10, 0x00])
    VERSION_REQUEST = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x10, 0x03, 0x00])
    POWER_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x81, 0x00, 0x00, 0x06])
    POWER_ACCEPTOR_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x81, 0x01, 0x00, 0x06])
    SET_UID = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x20, 0x01, 0x00, 0x01])
    RESET_REQUEST = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x00, 0x11, 0x00])
    INHIBIT_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x01, 0x82, 0x00, 0x01, 0x06])
    INHIBIT_REQUEST = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x00, 0x12, 0x00])
    IDLE_REQUEST = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x00, 0x13, 0x10])
    IDLE_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x01, 0x83, 0x01, 0x11, 0x06])
    ESCROW_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x01, 0x85, 0x02, 0x11, 0x06])
    BILL_REJECT = bytearray([0x12, 0x09, 0x00, 0x10, 0x02, 0x80, 0x04, 0x11, 0x06])
    STACK_INHIBIT = bytearray([0x12, 0x08, 0x00, 0x10, 0x02, 0x00, 0x14, 0x10])
    VEND_VALID_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x02, 0x86, 0x03, 0x11, 0x06])
    ERROR_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x80, 0x01, 0x12, 0x06])
    CLEAR_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x00, 0x80, 0x00, 0x12, 0x06])
    HOLD_BILL = bytearray([0x12, 0x0a, 0x00, 0x10, 0x01, 0x00, 0x16, 0x10, 0x3c, 0x00])

    REJECT_COMMAND = bytearray([0x12, 0x08, 0x00, 0x10, 0x2a, 0x00, 0x15, 0x10])
    REJECT_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x2a, 0x00, 0x04, 0x11, 0x06])
    RETURN_ACK = bytearray([0x12, 0x09, 0x00, 0x10, 0x2a, 0x00, 0x05, 0x11, 0x06])

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

    NOT_INIT_STATE = 16 # DBV not initialized.
    POWER_UP_NACK_STATE = 1 # Power up ACK not received by DBV yet. Write POWER_UP_ACK to DBV (with event id set) to move past this.
    POWER_UP_ACCEPTOR_NACK_STATE = 2 # Power up ACK not received, but with a bill currently in the acceptor.
    POWER_UP_STATE = 3 # DBV UID set and powered on. Needs to be reset.
    IDLE_STATE = 4  # DBV can accept bills in this state. Bezel light on.
    INHIBIT_STATE = 5 # DBV CANNOT accept bills in this state. Bezel light off.
    ESCROW_STATE = 6 # DBV is currently accepting a bill
    UNSUPPORTED_STATE = 7  # UID not set. Write SET_UID to DBV UID and move past this state.
    ERROR_STATE = 8 # DBV has encountered an error. Reset the DBV or wait for error to clear.
    ERROR_STATE_STACKER_FAILURE = 9 # The stacker has error when attempting to accept credits. This can usually be fixed with a reset.
    ERROR_STATE_BOX_REMOVED = 10 # The container where credits are stored in the DBV has been removed. This might mean that the operator is removing the credits inserted.
    ERROR_STATE_ACCEPTOR_JAM = 11 # The stacker on top of the DBV has been removed for a few seconds. Re-insert it, and reset.
    CLEAR_STATE = 12  # DBV error has cleared.
    NOTE_STAY_STATE = 13 # A bill has been left in the acceptor slot of the DBV. When removed, the DBV will proceed as normal.
    ACTIVE_STATE = 14 # DBV is actively holding or accepting bill.
    WAITING_STATE = 15
    #States have been switched to hex, becuaes I realized that the states have a ushort value that is associated with it
    DOWNLOAD_IDLE = 0x0401 #Means that the bill acceptor is ready to receive the next download packet
    DOWNLOAD_WRITE = 0x0402 #Means that the bill acceptor is currently writing the information that you sent it
    ABNORMAL = 0x02d1 #Something went wrong while you were trying to download new firmware
    FIRMWARE_MISMATCH = 0x03d2 #Firmware mismatch... noe entirely sure how you get this

    #endregion
    #region variables
    UidSet = False # UID of this device has been set. If this is true,
    State = NOT_INIT_STATE # Current state of the DBV
    AutoReject = False # If set to true, immediately reject any bills inserted into the DBV. NOTE: We really don't use this anymore. This is handled on Unity's side now
    AmountStored = 0 # Current amount stored the
    #endregion

    def __init__(self, deviceManager):
        super().__init__(deviceManager)
        self.dbvVersionBytes = []
        self.dbvVersion = None
        return


    #region on data received
    """ Handles all byte strings sent from the DBV to the host"""
    def on_data_received_event(self, firstByteOfPacket):
        read = firstByteOfPacket
        lengthOfMessage = 0
        if read[0] == 0x12:
            read += self.serialObject.read(1)
        if len(read) >= 2:
            read += self.serialObject.read(read[1] - 2)
            lengthOfMessage = read[1]
        else:
            read = firstByteOfPacket + self.serialObject.read(self.serialObject.in_waiting)

        if read == None or len(read) < 2:
            print ("Invalid Message: " + read)
            return
        length = len(read)#really just a way to double check that we received a valid message
        if length == lengthOfMessage:
            self.process_data_received_message(read)
        return

    """
    Takes in the packet that is received by our DBV-400 and selects the method most appropriate to process the data
    """
    def process_data_received_message(self, read):
        # print ("DBV Path: " + str(self.get_player_station_hash()) + ", Message:" + read.hex())
        length = read[1]
        
        if (length <= 8):
            if read[6] == 0x00 and read[7] == 0x01:
                self.on_inhibit_success(read)
                return
            elif read[6] == 0x01 and read[7] == 0x11:
                self.on_idle_success(read)
                return
            elif read[6] == 0x03 and read[7] == 0x11:
                self.on_vend_valid(read)
                return
            elif read[6] == 0x01 and read[7] == 0x13:
                self.on_note_stay_received(read)
                return
            elif read[6] == 0x01 and (read[7] == 0x12 or read[7] == 0x02):
                self.on_operation_error(read)
                return
            elif read[6] == 0x00 and (read[7] == 0x12 or read[7] == 0x02):
                self.on_operation_error_clear(read)
                return
            elif read[2] == 0x00 and read[3] == 0x10:
                self.on_download_status_received(read)
                return
        elif (length <= 9):
            if read[6] == 0x11 and read[7] == 0x00 and read[8] == 0x06:
                self.on_reset_request_received()
                return
            elif read[8] == 0xe2:
                self.on_unsupported_received(read)
                return
            elif read[8] == 0xe4:
                # print ("Error: Unavailable. DBV is not ready to receive more than likely")
                return
            elif read[5] == 0x20 and read[6] == 0x01 and read[7] == 0x00:
                self.on_uid_success()
                return
            elif read[6] == 0x12 and read[7] == 0x00:
                self.on_inhibit_request_received()
                return
            elif read[6] == 0x13 and read[7] == 0x10:
                self.on_idle_request_received()
                return
            elif read[6] == 0x14 and read[7] == 0x10:
                self.on_stack_inhibit_success()
                return
            elif read[6] == 0x04 and read[7] == 0x11:
                self.on_bill_rejected(read)
                return
            elif read[6] == 0x05 and read[7] == 0x11:
                self.on_bill_returned(read)
                return
            elif read[6] == 0x16 and read[7] == 0x10:
                self.on_bill_held()
                return
            elif read[6] == 0x15 and read[7] == 0x10:
                self.on_bill_reject_request_received()
                return
            elif read[5] == 0x00 and read[6] == 0xd1 and read[8] == 0x06:
                self.on_download_request_ack_received(read)
                return
        elif (length >= 10):
            if read[7] == 0x00 and read[8] == 0x06 and read[9] == 0x04:
                self.on_status_update_received(read)
                return
            elif read[6] == 0xd5 and read[7] == 0x00:
                self.on_download_info_received(read)
                return
            elif read[6] == 0x00 and read[7] == 0x00:
                self.on_power_up_nack_received(read)
                return
            elif read[6] == 0x01 and read[7] == 0x00:
                self.on_power_up_acceptor_nack_received(read)
                return
            elif read[6] == 0x02 and read[7] == 0x11:
                self.on_bill_inserted(read)
                return
            elif read[6] == 0x03 and read[7] == 0x00 and read[8] == 0x06:
                self.on_version_message_received(read)
                return
        # print ("I didn't process anything for this packet: " + read.hex())
        return
    #endregion

    #region on read methods

    """ Process status request message sent from DBV to host """
    def on_status_update_received(self, message):
        self.State = DBV400.UNSUPPORTED_STATE
        if (message[10] == 0x00 or message[10] == 0x01) and message[11] == 0x00:
            self.on_power_up_success()
        if message[10] == 0x00 and message[11] == 0x01:
            self.State = DBV400.INHIBIT_STATE
        if message[10] == 0x01 and message[11] == 0x011:
            self.State = DBV400.IDLE_STATE
        if message[10] == 0x01 and message[10] == 0x13:
            self.State = DBV400.NOTE_STAY_STATE
            self.reset_dbv()
        if message[10] == 0x01 and message[11] == 0x12:
            self.on_error_state_received(message)
        if message[10] == 0x00 and message[11] == 0x12:
            self.State = DBV400.CLEAR_STATE
            self.reset_dbv()
        if message[10] == 0x02 and message[11] == 0x11:
            self.State = DBV400.ESCROW_STATE
        if message[10] == 0x03 and message[11] == 0x11:
            self.State = DBV400.ACTIVE_STATE

        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT,self.State.to_bytes(2, 'big'))#Sends a state update to our unity application
        # print("New State: " + str(self.State))

    """ We have received a message that the DBV has started (or restarted) and needs to be acknowledged """
    def on_power_up_nack_received(self,message):
        # print("power up nack received")
        powerUpAck = DBV400.POWER_ACK
        powerUpAck[5] = message[5]
        self.UidSet = False
        self.State = DBV400.POWER_UP_NACK_STATE
        self.send_dbv_message(powerUpAck)
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT, self.State.to_bytes(2, 'big'))
        self.get_dbv_state()

    """ Same as above, but the DBV has started with a bill that is waiting to be stacked """
    def on_power_up_acceptor_nack_received(self, message):
        # print("power up acceptor nack received")
        # print ("Power UP")
        self.UidSet = False
        powerUpAck = DBV400.POWER_ACCEPTOR_ACK
        powerUpAck[5] = message[5]
        self.State = DBV400.POWER_UP_ACCEPTOR_NACK_STATE
        self.send_dbv_message(powerUpAck)
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT,self.State.to_bytes(2, 'big'))
        self.get_dbv_state()

    """ DBV has successfully received a power up acknowledgement and is ready to proceed with the power up process """
    def on_power_up_success(self):
        # print("power up success")
        self.State = DBV400.POWER_UP_STATE
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT,self.State.to_bytes(2, 'big'))
        self.power_up_dbv()
        return

    """ The last message sent to the DBV contained the incorrect UID """
    def on_unsupported_received(self,message):
        # print("unsupported received")
        self.State = DBV400.UNSUPPORTED_STATE
        self.UID = message[4]
        self.UidSet = True
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT, self.State.to_bytes(2, 'big'))
        return


    """ The DBV was successfully set during power up. We can now reset the DBV """
    def on_uid_success(self):
        # print("UID set success")
        self.UidSet = True
        return

    """ Reset message was successfully received by the DBV """
    def on_reset_request_received(self):
        # print ("Reset Request Received")
        self.AmountStored = 0
        self.State = DBV400.WAITING_STATE
        pass

    """ Inhibit message was successfuly received by the DBV """
    def on_inhibit_request_received(self):
        # print ("Inhibit Request Recieved: " +str(self.get_player_station_hash()))
        self.State = DBV400.WAITING_STATE
        pass

    """ DBV was successfully set to inhibit state. Send ACK to DBV to confirm state """
    def on_inhibit_success(self,message):
        # print ("Inhibit Success Event")
            
        inhibitMessage = DBV400.INHIBIT_ACK
        inhibitMessage[5] = message[5]
        self.State = DBV400.INHIBIT_STATE
        self.send_dbv_message(inhibitMessage)
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT, self.State.to_bytes(2, 'big'))
        self.check_begin_firmware_download()
        return



    """ Idle request successfully received by the DBV """
    def on_idle_request_received(self):
        # print ("Idle Request Acked")
        self.State = DBV400.WAITING_STATE
        pass

    """ DBV was successfully set to idle state. Send ACK to DBV to confirm state """
    def on_idle_success(self,message):
        # print ("Idle successfully received")
        idleMessage = DBV400.IDLE_ACK
        idleMessage[5] = message[5]
        self.send_dbv_message(idleMessage)
        self.State = DBV400.IDLE_STATE
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT, self.State.to_bytes(2, 'big'))

    """ A DBV has been inserted into DBV. We need to send an escrow message to confirm this """
    """ Our current workflow is to tell the DBV to hold the bill for 60 seconds while deciding whether to stack or reject """
    def on_bill_inserted(self, message):
        # print ("Bill Inserted Event")

        escrowMessage = DBV400.ESCROW_ACK
        escrowMessage[5] = message[5]
        self.send_dbv_message(escrowMessage)
        self.AmountStored = message[11]
        if self.AutoReject:
            self.send_dbv_message(DBV400.REJECT_COMMAND)
        else :
            self.send_dbv_message(DBV400.HOLD_BILL)
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_INSERTED_EVENT, [self.AmountStored])

    """ A bil inserted to the DBV was rejected due to an error (invalid bill, invalid state, etc.) """
    def on_bill_rejected(self, message):
        # print ("Bill Rejected Event")
        rejectAck = DBV400.REJECT_ACK
        rejectAck[5] = message[5]
        self.send_dbv_message(rejectAck)
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_REJECTED_EVENT,[self.AmountStored])
        self.AmountStored = 0

    """ A bill was returned by the DBV due to a reject command from a player or powering up with a bill inserted """
    def on_bill_returned(self, message):
        # print ("Bill Returned Event")
        returnAck = DBV400.RETURN_ACK
        returnAck[5] = message[5]
        self.send_dbv_message(returnAck)
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_RETURNED_EVENT,[self.AmountStored])
        self.AmountStored = 0

    """ A bill was successfully held in the bill acceptor from a command """
    def on_bill_held(self):
        # print ("Bill Held")
        pass

    """ A stack command was successfully processed by the DBV. The bill inserted will now be stacked """
    def on_stack_inhibit_success(self):
        # print ("Stack inhibit success")
        pass

    """ The bill stacked in the bill acceptor was succesfully processed and stacked """
    def on_vend_valid(self, message):
        # print ("Vend Valid")
        vendValidAck = DBV400.VEND_VALID_ACK
        vendValidAck[5] = message[5]
        self.send_dbv_message(vendValidAck)
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_ACCEPTED_EVENT,[self.AmountStored])
        self.AmountStored = 0
        return

    """ A reject bill command was successfully processed """
    def on_bill_reject_request_received(self):
        # print ("BILL REJECT REQUEST")
        pass

    """ A returned/rejected bill was left at the mouth of the DBV and needs to be removed """
    def on_note_stay_received(self, message):
        # print ("Note Stay Event")
        noteStayAck = DBV400.NOTE_STAY_ACK
        noteStayAck[5] = message[5]
        self.send_dbv_message(noteStayAck)
        self.State = DBV400.NOTE_STAY_STATE
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT,self.State.to_bytes(2, 'big'))
        pass

    """ The DBV has reported an error. Ack this message and wait for the error clear message """
    def on_operation_error(self, message):
        # print ("Operation Error")
        opErrorAck = DBV400.ERROR_ACK[:]
        opErrorAck[5] = message[5]
        opErrorAck[7] = message[7]
        self.send_dbv_message(opErrorAck)
        self.State = DBV400.ERROR_STATE
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT,self.State.to_bytes(2, 'big'))
        pass

    """ A DBV error was cleared and the system is ready to be reset to resume normal operation """
    def on_operation_error_clear(self, message):
        # print ("Operation Error Cleared")
        clearAck = DBV400.CLEAR_ACK[:]
        clearAck[5] = message[5]
        clearAck[7] = message[7]
        self.send_dbv_message(clearAck)
        self.State = DBV400.CLEAR_STATE
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT,self.State.to_bytes(2, 'big'))
        self.reset_dbv()
        pass

    """ Process this error message to determine the specific error state """
    def on_error_state_received(self, message):
        if len(message) >= 13:
            if message[13] == 0xc3:
                self.State = DBV400.ERROR_STATE_ACCEPTOR_JAM
                # wait for clear state
            elif message[13] == 0xff:
                self.State = DBV400.ERROR_STATE_STACKER_FAILURE
                self.reset_dbv()
                # reset immediately from this type of error
            else:
                self.State = DBV400.ERROR_STATE
                # let the operator reset from this error
            self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT,self.State.to_bytes(2, 'big'))
        pass


    """ Process a message from our DBV to determine the version we are in """
    def on_version_message_received(self, message):
        indexOfVersion = 9
        self.dbvVersionBytes = message
        self.dbvVersion = message[indexOfVersion:].decode('utf-8')
        return
    #endregion on read methods

    #region Command Methods

    """ Send the DBV a message, formatting the message with the UID if neccessary """
    def send_dbv_message(self, message):
        if self.UidSet:
            message[4] = self.UID
        else:
            message[4] = 0x00

        # print(self.to_string() + " SEND: " + str(message.hex()))
        self.write_to_serial(message)
        return

    """ Set the UID of this class. After the UID of the DBV is set, every subsequent packet sent must include it in its 4th index """
    def set_uid(self):
        uidMessage = DBV400.SET_UID
        uidMessage[8] = self.UID
        self.write_to_serial(uidMessage)
        return

    """ Set the DBV to idle if in inhibit """
    def idle_dbv(self):
        if self.State != DBV400.INHIBIT_STATE:
            return
        self.send_dbv_message(DBV400.IDLE_REQUEST)
        return

    """ Inhibit the DBV to stop accepting bills """
    def inhibit_dbv(self):
        if self.State != DBV400.IDLE_STATE:
            return
        self.send_dbv_message(DBV400.INHIBIT_REQUEST)
        return

    """ Power up method. Set the UID of the DBV and reset """
    def power_up_dbv(self):
        self.set_uid()
        return

    """ Reset the DBV """
    def reset_dbv(self):
        if (self.State == DBV400.ERROR_STATE_BOX_REMOVED or self.State == DBV400.ERROR_STATE_ACCEPTOR_JAM or self.State == DBV400.WAITING_STATE):
            return
        self.send_dbv_message(DBV400.RESET_REQUEST)
        return

    """ Query the current DBV state """
    def get_dbv_state(self):
        message = DBV400.STATUS_REQUEST
        self.send_dbv_message(message)
        return

    """ Stack the current bill in the acceptor """
    def stack_bill(self):
        self.send_dbv_message(DBV400.STACK_INHIBIT)
        return

    """ Reject the current bill in the acceptor """
    def reject_bill(self):
        self.send_dbv_message(DBV400.REJECT_COMMAND)
        return

    """ Send event message to Unity """
    def send_event_message(self, eventType, messageContent):
        message = messageContent
        playerStationHash = self.get_player_station_hash()
        self.dragonMasterDeviceManager.add_event_to_send(eventType, message, playerStationHash)
        return

    """ Send event message to request the version of the DBV that that we are running """
    def send_dbv_version_request(self):
        self.send_dbv_message(DBV400.VERSION_REQUEST)
        return

    #endregion

    #region updating dbv firmware
    LATEST_DBV_FIRMWARE = None

    DOWNLOAD_REQUEST_PACKET = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x00, 0xd1, 0x00]) #Packet requests that we enter dbv download mode
    DOWNLOAD_INFO_REQUEST_PACKET = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x10, 0xd5, 0x00]) #Packet to request that we gather info about our download state
    DOWNLOAD_SEND_BYTES_PACKET = bytearray([0x12, 0x00, 0x10, 0x10, 0x01, 0x00, 0xd2, 0x00]) #Packet that sends the byte chunks of our firmware bin file
    DOWNLOAD_END_PACKET = bytearray([0x12, 0x08, 0x00, 0x10, 0x01, 0x00, 0xd3, 0x00]) #This packets should be sent after all our firmware data has been sent



    DOWNLOAD_INDEX = 0 #Index in Download packet that we are currently in
    DOWNLOAD_PACKET_DATA = [] #List of all the bytes that we need to send to our DBV. This should only need to be opened once per 
    MAX_DOWNLOAD_BYTE_SIZE = 0 #This represents the max number of bytes that we can send at a time for our download packets
    DOWNLOAD_START_POSITION = 0 #Upon starting our download process, the dbv will send a hex address that will indicate where we should write our data, this should be saved so that we do not have to ask for download info before sending each download packet
    DOWNLOAD_INFO_COLLECTED = False #Before starting our download process we should set this to false. If set to false we will request download info. Upon receiving this packet, this will be toggled back to True
    DOWNLOAD_PROCESS_BEGAN = False

    """

    """
    def bill_acceptor_requires_firmware_update(self):
        if (DBV400.LATEST_DBV_FIRMWARE == None):
            return False
        return not self.dbvVersion.lower().__contains__(DBV400.LATEST_DBV_FIRMWARE.lower())

    """

    """
    def check_begin_firmware_download(self):
        if self.DOWNLOAD_PROCESS_BEGAN:
            return
        if self.bill_acceptor_requires_firmware_update():
            self.begin_firmware_download_process()
        else:
            # print ("Nothing Happened")
            pass


    """
    Runs a process to update the firmware in our DBV devices if needed

    NOTE: The bill acceptor needs to be in the Inhibit state before we run this process. We may need to delay the download process to set our 
    """
    def begin_firmware_download_process(self):
        if (self.State != DBV400.INHIBIT_STATE):
            print ("Please be sure that the DBV is in the inhibit state before running firmware update")
            return
        self.DOWNLOAD_PROCESS_BEGAN = True
        self.DOWNLOAD_INDEX = 0
        self.DOWNLOAD_INFO_COLLECTED = False
        self.send_download_request()

        return

    """
    Sends a request to begin the download process for our DBV
    """
    def send_download_request(self):
        print ("Sending Download Request")
        self.send_dbv_message(DBV400.DOWNLOAD_REQUEST_PACKET)
        return

    """
    Sends a packet to request the download info. This should include the max size of our packet that we are able to send to our dbv
    """
    def send_download_info_request(self,):
        print ("Sending Info Request")
        self.DOWNLOAD_INFO_COLLECTED = True
        self.send_dbv_message(DBV400.DOWNLOAD_INFO_REQUEST_PACKET)
        return

    """
    This should be called upon receiving a dbv idle message. If you have not received download info, you should request that first before calling this
    """
    def send_download_bytes_to_dbv(self):
        # print ("Attempting to Send Download bytes: " + str(self.DOWNLOAD_INDEX) + "/" + str(len(DBV400.DOWNLOAD_PACKET_DATA)))
        fullPacketSize = len(DBV400.DOWNLOAD_PACKET_DATA)
        if self.DOWNLOAD_INDEX > fullPacketSize:
            print (str(self.get_player_station_hash()) + ": DBV Firmware Update Complete!")
            self.send_download_complete_message()
            return
        
        indexForDLPacket = self.DOWNLOAD_START_POSITION + self.DOWNLOAD_INDEX
        indexForDLPacketAsBytes = int.to_bytes(indexForDLPacket, 4, byteorder='little')
        downloadPacket = DBV400.DOWNLOAD_SEND_BYTES_PACKET[:] + bytearray(indexForDLPacketAsBytes)
        downloadPacketChunkSize = self.MAX_DOWNLOAD_BYTE_SIZE - len(downloadPacket)
        dlPacketInfo = DBV400.DOWNLOAD_PACKET_DATA[self.DOWNLOAD_INDEX: min(self.DOWNLOAD_INDEX + downloadPacketChunkSize, fullPacketSize)]
        updatedDownloadIndex = self.DOWNLOAD_INDEX + downloadPacketChunkSize

        ###This part has nothing to do with sending our download packet simply for displaying percentage for debugging purposes
        percentageIncrement = 10
        previousPercentageComplete = int(int(float(self.DOWNLOAD_INDEX) / float(fullPacketSize) * 100) / percentageIncrement)
        nextPercentageComplete = int(int(float(updatedDownloadIndex) / float(fullPacketSize) * 100) / percentageIncrement)
        if  previousPercentageComplete < nextPercentageComplete:
            print (str(self.get_player_station_hash()) + " DBV Downloading: " + str(nextPercentageComplete * percentageIncrement) + "%")

        ############################################################################################################################
        self.DOWNLOAD_INDEX = updatedDownloadIndex
        try:
            downloadPacket += bytearray(dlPacketInfo)
            packetSizeAsBytes = int.to_bytes(len(downloadPacket), 2, byteorder='little')
            
            downloadPacket[1] = packetSizeAsBytes[0]
            downloadPacket[2] = packetSizeAsBytes[1]
            self.send_dbv_message(downloadPacket)

        except Exception as e:
            print (e)
            print (self.MAX_DOWNLOAD_BYTE_SIZE)
            print (updatedDownloadIndex)
            print (len(downloadPacket))
        
        return

    """
    This method should be called upon completing the download process for our DBV firmware update
    """
    def send_download_complete_message(self):
        # print ("Sending Download Complete")
        self.send_dbv_message(DBV400.DOWNLOAD_END_PACKET)
        return

    """
    This method should be called upon receiving a Download status packet
    """
    def on_download_status_received(self, packetData):
        ackMessage = bytearray(packetData)
        ackMessage.append(0x06)
        ackMessage[1] = len(ackMessage)
        self.send_dbv_message(ackMessage)
        if packetData[6] == 0x01 and packetData[7] == 0x04:
            self.on_downlaod_idle_received(packetData)
            return
        elif packetData[6] == 0x02 and packetData[7] == 0x04:
            self.on_download_writing_received(packetData)
            return
        elif packetData[6] == 0xd1 and packetData[7] == 0x02:
            self.on_download_write_error(packetData)
            return
        elif packetData[6] == 0xd2 and packetData[7] == 0x03:
            self.on_firmware_mismatch_error(packetData)
            return

        return

    """
    If we receive a download status packet that contains an error code for download write error, this method should be called
    """
    def on_download_write_error(self, packetData):
        print ("Download Write Error")
        return

    """
    This method should be called if there is a firmware mismatch error sent during the download process
    """
    def on_firmware_mismatch_error(self, packetData):
        print ("Firmware Mismatch")
        return

    """
    Message indicating that the write process of our packet data has been processed and that we are able to send the next set of data
    """
    def on_downlaod_idle_received(self, packetData):
        # print ("Download Idle")
        self.State = DBV400.DOWNLOAD_IDLE
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT, self.State.to_bytes(2, 'big'))
        if self.DOWNLOAD_INFO_COLLECTED:
            self.send_download_bytes_to_dbv()
        else:
            self.send_download_info_request()
        return

    """
    Simply confirms that the DBV is in the process of writing the data that we have sent to it
    """
    def on_download_writing_received(self, packetData):
        # print ("Downlaod Write State")
        self.State = DBV400.DOWNLOAD_WRITE
        self.send_event_message(DragonMasterDeviceManager.DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT,self.State.to_bytes(2, 'big'))
        return

    """
    This response indicates that the DBV has received a download request and should now be entering download mode
    """
    def on_download_request_received(self, packetData):
        print ("Downlaod Request")
        return

    """

    """
    def on_download_request_ack_received(self, packetData):
        print ("Download ACK Received")
        return

    """
    This packet will contain information about the packet size that we can send to our DBV as well as other information about
    our Download request
    """
    def on_download_info_received(self, packetData):
        print ("Download Info")
        
        maxPacketSize = int.from_bytes(packetData[9:13], byteorder='little', signed=False)
        startPoint = int.from_bytes(packetData[13:17], byteorder='little', signed=False)

        self.MAX_DOWNLOAD_BYTE_SIZE = maxPacketSize
        self.DOWNLOAD_START_POSITION = startPoint

        self.send_download_bytes_to_dbv()
        return

    """
    After we send a packet that indicates the download process has completed we should receive this packet.
    This is simply a response that our download proecess is completed

    NOTE: You probably won't receive this response before the DBV is disconnected
    """
    def on_downlaod_completion_received(self, packetData):

        return

    #endregion updating dbv firmware

    #region Override Methods
    def start_device(self, deviceElement):
        self.UidSet = False

        self.serialObject = self.open_serial_device(deviceElement.device, DBV400.DBV_BAUDRATE, None, None)
        if self.serialObject == None:
            return False

        self.serialObject.flush()
        if self.serialObject == None:
            return False

        if not self.process_current_state_on_startup():
            return False
        
        super().start_device(deviceElement)
        if self.State == DBV400.NOT_INIT_STATE:
            return False

        if self.State == DBV400.IDLE_STATE:
            self.inhibit_dbv()
        elif self.State == DBV400.UNSUPPORTED_STATE:
            self.reset_dbv()
        elif self.State != DBV400.INHIBIT_STATE:
            self.reset_dbv()
        else:
            self.check_begin_firmware_download()
            return True
        self.get_dbv_state()
        
        return True

    """
    This will run a check to ensure that we are in a power up state before running our normal startup sequence
    """
    def process_current_state_on_startup(self):
        self.serialObject.timeout = .1
        self.serialObject.writeTimeout = 1
        numberOfAttempts = 0
        self.get_dbv_state()
        while numberOfAttempts < 5 and self.State == DBV400.NOT_INIT_STATE:
            numberOfAttempts += 1
            firstByte = self.serialObject.read(1)
            if firstByte:
                self.on_data_received_event(firstByte)#This will ignore process. This is to ensure that we are able to communicate witht the DBV
            else:
                self.get_dbv_state()
            
            
        if self.State == DBV400.NOT_INIT_STATE:
            return False

        numberOfAttempts = 0
        self.set_uid()

        while numberOfAttempts < 5 and not self.UidSet:
            numberOfAttempts += 1
            firstByte = self.serialObject.read(1)
            if firstByte:
                self.on_data_received_event(firstByte)
            else:
                self.set_uid()
        if not self.UidSet:
            return False
        self.send_dbv_version_request()
        numberOfAttempts = 0
        while numberOfAttempts < 5 and self.dbvVersion == None:
            numberOfAttempts += 1
            firstByte = self.serialObject.read(1)
            if firstByte:
                self.on_data_received_event(firstByte)
            else:
                self.send_dbv_version_request()
        if self.dbvVersion == None:
            return False
        self.get_dbv_state
        numberOfAttempts = 0
        while numberOfAttempts < 2 and self.State == DBV400.UNSUPPORTED_STATE:
            numberOfAttempts += 1
            firstByte = self.serialObject.read(1)
            if firstByte:
                self.on_data_received_event(firstByte)
            else:
                self.get_dbv_state()

        if self.dbvVersion == None:
            return False
        self.serialObject.timeout = None
        self.serialObject.writeTimeout = None
        return True


    def fetch_parent_path(self, deviceElement):
        devToReturn = None
        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if dev.device_path.__contains__(deviceElement.location) and dev.device_path.__contains__(deviceElement.name):
                devToReturn = dev.parent.parent.parent.device_path
        return devToReturn

    def to_string(self):
        return "DBV-400 " + self.comport

    def get_ba_type(self):
        return DragonMasterDeviceManager.DragonMasterDeviceManager.BA_DBV_400
    #endregion

    pass

"""
This bill acceptor is functionally the same as our DBV-400
"""
class iVizion(DBV400):
    DBV_DESCRIPTION = "iVIZION"

    def to_string(self):
        return iVizion.DBV_DESCRIPTION + ": " + self.comport

    def get_ba_type(self):
        return DragonMasterDeviceManager.DragonMasterDeviceManager.BA_iVIZION

    def check_begin_firmware_download(self):
        return


"""
New device, that is functionally similar to our DBV-400, with additional features. This class will handle the functionality of
DBV-500 devices that are connected
"""
class DBV500(DBV400):
    DBV_DESCRIPTION = "DBV-500"

    def to_string(self):
        return DBV500.DBV_DESCRIPTION + ": " + self.comport

    def get_ba_type(self):
        return DragonMasterDeviceManager.DragonMasterDeviceManager.BA_DBV_500

    def check_begin_firmware_download(self):
        return
    pass

"""
Class that maanages our Draxboard communication and state
"""
class Draxboard(SerialDevice):
    #region command byte arrays
    REQUEST_STATUS = bytearray([0x01, 0x00, 0x01, 0x02])
    SET_OUTPUT_STATE = bytearray([0x04, 0x02, 0x05, 0x00, 0x00, 0x00, 0x00, 0x00])
    DRAX_OUTPUT_ENABLE = bytearray([]) #Sends a message to the draxboard to only toggle specific output bits on
    DRAX_OUTPUT_DISABLE = bytearray([]) #Sends a message to the draxboard to only toggle specific output bits off
    READ_INPUT_STATE = bytearray([0x03, 0x00, 0x01, 0x04])#Send this packet to receive the current input state of our draxboard device
    DRAXBOARD_OUTPUT_ENABLE = bytearray([0x02, 0x05, 0x09, 0x00, 0x00, 0x00, 0x00, 0x02, 0x00, 0x00, 0x00, 0x12]) #This will set the output state. Unlike output_enable/output_disable, this sets the entire state of the output for our draxboards
    METER_INCREMENT = bytearray([0x09, 0x00, 0x04, 0x00, 0x00, 0x00, 0x00]) #Message to increment our hard meters attached to our draxboard devices
    READ_PENDING_METER = bytearray([0x0a, 0x00, 0x02, 0x01, 0x0d]) #region
    #endregion command byte arrays

    #region const varialbes
    ##METER INDEX
    IN_METER = 0x00
    OUT_METER = 0x01
    IN_METER_MACHINE = 0x02#In some cases our draxboard will have 4 meters. 3 and 4 are meant to represent the machine money in/out
    OUT_METER_MACHINE = 0x03

    ##Return Packet Data
    #Interupting Events (Not polled)
    INPUT_EVENT_ID = 0xfa
    INPUT_EVENT_SIZE = 9
    STATUS_EVENT_ID = 0xfb
    STATUS_EVENT_SIZE = 8
    INPUT_REQUEST_EVENT_ID = 0x03 #This is an input packet, but it is received upon requesting it manually rather than through player interaction

    #Command Events
    REQUEST_STATUS_ID = 0x01
    REQUEST_STATUS_SIZE = 16
    OUTPUT_EVENT_ID = 0x04
    OUTPUT_EVENT_SIZE = 8
    OUTPUT_ENABLE_ID = 0x06
    OUTPUT_DISABLE_ID = 0x07
    METER_INCREMENT_ID = 0x09
    PENDING_METER_ID = 0x0a

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
        #High version byte
        self.versionNumberHigh = 0
        #Low version byte
        self.versionNumberLow = 0
        #ushort value that represents the current draxboard output state
        self.draxOutputState = 0
        #In Later models of the Draxboard we can set the player station number through the hardware. This can be used for first time setup
        self.playerStationNumber = 0
        self.meterTicksRemaining = 0
        self.playerStationHash = 0#The player station hash is a value assigned only to our Draxboard. It is a value derived from the usb path to our draxboard

        return

    #region Override methods
    def start_device(self, deviceElement):
        self.serialObject = self.open_serial_device(deviceElement.device, Draxboard.DRAX_BAUDRATE, 5, 5)
        self.send_request_status()#We want to send a request status to our Draxboard as the very first command to ensure that it is functioning properly as well as gather important info
        firstByteOfRequestStatus = self.serialObject.read(1)
        if firstByteOfRequestStatus == None:
            return False

        self.on_data_received_event(firstByteOfPacket=firstByteOfRequestStatus)

        if self.serialObject == None:
            return False
        self.serialObject.flush()
        super().start_device(deviceElement)#This will begin the polling thread to read inputs returned by the draxboard

        self.write_to_serial(self.DRAXBOARD_OUTPUT_ENABLE)#Turns on all outputs that need to be on

        self.toggle_output_state_of_drax(0x180f)
        self.playerStationHash = self.get_draxboard_device_path_hash(deviceElement)

        return True

    """
    Retrieves the parent path of our draxboard device
    """
    def fetch_parent_path(self, deviceElement):
        devToReturn = None
        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if dev.device_path.__contains__(deviceElement.location) and dev.device_path.__contains__(deviceElement.name):
                devToReturn = dev.parent.parent.parent.device_path
        return devToReturn

    """
    Sends a request status packet which will return the version number as well as other initialization values.
    Send this when you first connect the or when our unity application wants to know what devices are currently connected
    """
    def send_request_status(self):
        self.write_to_serial(self.REQUEST_STATUS)
        return

    """
    This method will send a packet that will request the currennt input state of our draxboard. This should be sent every time we start our python script.
    
    Ideally you should be able to send this upon starting another play session to receive the current input state
    """
    def send_request_current_input_state(self):
        self.write_to_serial(self.READ_INPUT_STATE)
        return

    """
    This method will perform draxboard actions based on the event type packet that is received

    NOTE: Be sure that if there is a return packet that you expect, be sure to include it here to ensure
    that we do not miss any packets
    """
    def on_data_received_event(self, firstByteOfPacket):
        if (firstByteOfPacket == None):
            print ("The first byte was None. This should not have gotten this far")
            return
        if len(firstByteOfPacket) < 1:
            return
        read = firstByteOfPacket + self.serialObject.read(2)
        lengthOfPacket = read[2]
        read += self.serialObject.read(lengthOfPacket)
        try:

            #Dynamic Packets: Packets that can be received at any point regardless of whether they were requested or not
            if firstByteOfPacket[0] == Draxboard.INPUT_EVENT_ID:# Input State Packet (Dynamic)
                self.add_input_event_to_tcp_queue(read)
                return
            elif firstByteOfPacket[0] == Draxboard.STATUS_EVENT_ID:# Drax Status Packet (Dynamic)
                self.on_status_packet_received(read)
                return

            #Response Packet. Packets that are a response to packets that we sent
            elif firstByteOfPacket[0] == Draxboard.INPUT_REQUEST_EVENT_ID:# Input State Packet (Requested)
                self.add_input_event_to_tcp_queue(read)
            elif firstByteOfPacket[0] == Draxboard.REQUEST_STATUS_ID:# Drax Status (Requested)
                self.on_request_status_received(read)
                return
            elif firstByteOfPacket[0] == Draxboard.OUTPUT_EVENT_ID:# Drax Output State Packet
                self.on_output_packet_received(read)
                return
            elif firstByteOfPacket[0] == Draxboard.METER_INCREMENT_ID:# Drax Meter Increment Packet
                self.on_meter_increment_packet_received(read)
                return
            elif firstByteOfPacket[0] == Draxboard.PENDING_METER_ID:# Drax Pending Meter Ticks Event
                self.on_pending_meter_packet_received(read)
                return
            else:
                pass

        except Exception as e:
            print ("There was an error processing a data event from our draxboard")
            print (e)

    #region message received events
    """
    Retrieves the status of the our Draxboard. This will typically retrieved on startup.

    This will contain initialized information of the draxboard such as Version number and the player station number
    if the draxboard version supports it
    """
    def on_request_status_received(self, bytePacket):
        requestStatus = bytePacket
        if len(requestStatus) < Draxboard.REQUEST_STATUS_SIZE:
            print ("Reqeust Status length was too short or invalid: " + str(requestStatus))
            return

        self.versionNumberHigh = requestStatus[15]
        self.versionNumberLow = requestStatus[16]

        self.playerStationNumber = requestStatus[10]
        return

    """
    This method will be called upon receiving a packet for the draxboard status

    TODO: Implement some functionality upon receiving a status packet
    NOTE: This method is obsolete according to the documentation.
    """
    def on_status_packet_received(self, bytePacket):
        return

    


    """
    This method will be calle upon receiving a packet from the drax that correlates to the us toggling the output of the draxboard.
    This will also send a message to Unity to confirm the state that our draxboards have been set to
    """
    def on_output_packet_received(self, bytePacket):
        try:
            outputBytes = bytePacket[3:7]
            self.draxOutputState = int.from_bytes(outputBytes, byteorder='little')
            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.DRAX_OUTPUT_EVENT, \
                outputBytes, self.playerStationHash)
        except Exception as e:
            print("There was an error collecting our output event")
            print (e)

        return

    """
    This method will be called upon receiving a packet from the drax after sending a packet to increment the hard meter ticks

    The response should detail which meter is being set to increment and how many ticks This is simply a confirmation
    """
    def on_meter_increment_packet_received(self, bytePacket):
        print ("Meter Out: " + str(bytePacket))
        return

    """
    This method will be called upon receiving a pending meter ticks remaining packet
    """
    def on_pending_meter_packet_received(self, bytePacket):
        print ("Pending Meter: " + str(bytePacket))
        return


    #endregion message received events




    """
    To string displays the comport of the drax device
    """
    def to_string(self):
        if (self.comport != None):
            return "Draxboard v" + str(self.versionNumberHigh) + "." + str(self.versionNumberLow).zfill(2) + " (" + self.comport + ")"
        else:
            return "Draxboard (Missing)"


    #endregion Override Methods
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


    """
    Method that is used to increment the hard meters that are attached to our draxboard devices
    """
    def increment_meter_ticks(self, meterIDToIncrement, ticksToSend):
        try:
            if ticksToSend == 0:
                return

            incrementMeterCommand = self.METER_INCREMENT
            incrementMeterCommand[3] = meterIDToIncrement

            incrementMeterCommand[4] = (ticksToSend >> (8 * 0)) & 0xff
            incrementMeterCommand[5] = (ticksToSend >> (8 * 1)) & 0xff
            incrementMeterCommand[6] = 0#Need to reset the checksum

            checkSum = self.calculate_checksum(incrementMeterCommand)
            incrementMeterCommand[6] = checkSum

            self.write_to_serial(incrementMeterCommand)

            readPendingMeterCommand = self.READ_PENDING_METER[:]

            readPendingMeterCommand[3] = meterIDToIncrement
            readPendingMeterCommand[4] = 0#need to reset the checksum
            readPendingMeterCommand[4] = self.calculate_checksum(readPendingMeterCommand)
            self.write_to_serial(readPendingMeterCommand)
            sleep(.05)
            firstResult = self.meterTicksRemaining
            self.write_to_serial(readPendingMeterCommand)
            sleep(.05)
            secondResult = self.meterTicksRemaining
            if firstResult > secondResult:
                print ("Incrementing Meter Was Successful")
                return
            else:
                print ("There was an error incrementing the hard meters")
                return

        except Exception as e:
            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.DRAX_METER_ERROR, [], self.playerStationHash)#Add that there was an error attempting to tick meters
            print ("There was an error while sending our hard meter tick event")
            print (e)
        return

    """
    Sets up and adds an input packet to our TCP queue, so that it can be sent at the next availability
    """
    def add_input_event_to_tcp_queue(self, inputPacket):

        if inputPacket == None or (inputPacket[0] != Draxboard.INPUT_EVENT_ID and inputPacket[0] != Draxboard.INPUT_REQUEST_EVENT_ID):
            print ("Invalid Input Event Packet. Please Be sure you are correctly interpreting our input packets")
            return
        inputData = [inputPacket[Draxboard.DOOR_STATE_INDEX], inputPacket[Draxboard.INPUT_INDEX]]

        if DragonMasterDeviceManager.DragonMasterDeviceManager.DEBUG_SHOW_DRAX_BUTTONS:
            print (str(self.playerStationHash) + ": " + str(inputData))#For debug purposes only

        self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.DRAX_INPUT_EVENT, inputData, self.playerStationHash)
        return

    """
    Toggles the draxboard output state. This can control certain functions of the draxboard such as
    the bell, joystick vibrators, button lights, etc

    There are 3 types of toggles
        Type 0 - output that is passed through is what the state will be
        Type 1 - output bit enable (Use this to toggle only one bit on)
        Type 2 - output bit disable (Use this to toggle one bit off)

    NOTE: Any other value aside from 0-2 will result in this method not running
    """
    def toggle_output_state_of_drax(self, outputToggleu32, toggleMessageType=0):
        if toggleMessageType == 0:
            pass
            # self.draxOutputState = outputToggleu32
        elif toggleMessageType == 1:#Output bit enable
            outputToggleu32 = self.draxOutputState | outputToggleu32
        elif toggleMessageType == 2:#Output bit disable
            outputToggleu32 = self.draxOutputState & (~outputToggleu32)
        else:
            print ("Message type was not valid in toggle_output_state_of_drax")
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

        self.write_to_serial(outputMessageArray)
        self.draxOutputState = outputToggleu32
        return


    """
    Sends a packet to our TCP Manager that contains the output state of the draxboard
    """
    def send_current_drax_output_state(self, byte1, byte2):
        packetToSend = [byte1, byte2]
        self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.DRAX_OUTPUT_EVENT, packetToSend, self.playerStationHash)
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
    Due to the nature of the Omnidongle communcation, we will not be polling the device for events. Instead we will wait for a response from the dongle immediately after sending a
    packet to the device
    """
    def poll_serial_thread(self):
        self.pollingDevice = True
        self.serialState = SerialDevice.SERIAL_WAIT_FOR_EVENT
        try:
            while self.pollingDevice:
                if self.serialObject.in_waiting:#This is strictly just here to throw an exception if the device is ever disconnected. That way we can properly remove from the device manager
                    pass
                sleep(.1)#Polls around 10 times per second to ensure that the dongle is still connected

        except Exception as e:
            print ("There was an error polling device " + self.to_string())
            print (e)
            self.on_poll_serial_errored()
            self.pollingDevice = False  # Thread will end if there is an error polling for a device



        print (self.to_string() + " no longer polling for events")#Just want this for testing. want to remove later
        return

    """

    """
    def on_data_received_event(self, firstByteOfPacket):
        print (firstByteOfPacket)

        return

    def to_string(self):
        return self.associatedReliancePrinter.to_string()

    def on_poll_serial_errored(self):
        self.dragonMasterDeviceManager.remove_device(self.associatedReliancePrinter)

    """
    Disconnects both our serial
    """
    def disconnect_device(self):
        if not self.pollingDevice:
            return
        super().disconnect_device()

    #region reliace commands


    """
    Returns the state of the printer as a byte value. The value will be interpreted by Unity as to whether or not it is in a
    errored state or not. If there is ever an issue retrieving this command it is very likely that the printer was disconnected

    TODO: Change how we get printer status now
    """
    def get_printer_status(self):
        self.serialObject.read(self.serialObject.in_waiting)

        self.write_to_serial(ReliancePrinterSerial.PRINTER_STATUS_REQUEST)
        printerStatus = self.serialObject.read(6)

        self.write_to_serial(ReliancePrinterSerial.PAPER_STATUS_REQUEST)
        printerStatus += self.serialObject.read(1)

        return printerStatus

    """
    Call this command to cut the printed paper from the reliance printer
    """
    def cut(self):
        self.write_to_serial(ReliancePrinterSerial.PAPER_PRESENT_TO_CUSTOMER)
        return

    """
    Call this method to retract the paper that has been printed
    """
    def retract(self):
        self.write_to_serial(ReliancePrinterSerial.PAPER_RETRACT)
        return

    #endregion relinace commands
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
    Due to the nature of the Omnidongle communcation, we will not be polling the device for events. Instead we will wait for a response from the dongle immediately after sending a
    packet to the device
    """
    def poll_serial_thread(self):
        self.pollingDevice = True
        self.serialState = SerialDevice.SERIAL_WAIT_FOR_EVENT
        try:
            while self.pollingDevice:
                if self.serialObject.in_waiting:#This is strictly just here to throw an exception if the device is ever disconnected. That way we can properly remove from the device manager
                    pass
                sleep(.1)#Polls around 10 times per second to ensure that the dongle is still connected

        except Exception as e:
            print ("There was an error polling device " + self.to_string())
            print (e)
            self.on_poll_serial_errored()
            self.pollingDevice = False  # Thread will end if there is an error polling for a device



        print (self.to_string() + " no longer polling for events")#Just want this for testing. want to remove later
        return


    """
    The parent path for our Omnidongle is not important as it is not assigned to any
    Player Station
    """
    def fetch_parent_path(self, deviceElement):
        devToReturn = None
        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if dev.device_path.__contains__(deviceElement.location) and dev.device_path.__contains__(deviceElement.name):
                devToReturn = dev.parent.parent.parent.parent.device_path
        print (devToReturn)
        return devToReturn

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
    Sends a packet to our omnidongle. After we have sent a message to our omnidongle we will wait for a response to return to our unity application
    If we do not receive a message we should probably throw an error of some kind here. The dongle should always return something
    """
    def send_data_to_omnidongle_wait_for_response(self, packetToSend):
        if (packetToSend == None):
            print ("Packet to send was None")
            return
        if (len(packetToSend) <= 1):
            print ("Our packet length was too short")
            return

        self.write_to_serial(packetToSend)
        firstByteOfPacket = self.serialObject.read(1)
        if firstByteOfPacket == None:
            print ("OMNIERROR: No packet was returned after a timeout")
            return

        sleep(.025)#Give it a small buffer time before reading the packet in. Omnidonge message can get very long and we may miss something if we start reading immediately
        fullOmnidongleResponse = firstByteOfPacket + self.serialObject.read(self.serialObject.in_waiting)
        self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.OMNI_EVENT , fullOmnidongleResponse)#returns the response from our omnidongle

    """
    Returns the type of device as well as the comport that this device is associated with
    """
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
def get_all_connected_bill_acceptors():
    dbv400Elements = []
    iVizionElements = []
    dbv500Elements = []
    allPorts = serial.tools.list_ports.comports()
    for element in allPorts:
        if element.description.__contains__(DBV400.DBV_DESCRIPTION):
            dbv400Elements.append(element)
        if element.description.__contains__(iVizion.DBV_DESCRIPTION):
            iVizionElements.append(element)
        if element.description.__contains__(DBV500.DBV_DESCRIPTION):
            dbv500Elements.append(element)

    return dbv400Elements, iVizionElements, dbv500Elements

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
            relianceElements.append(element)

    return relianceElements

#End Search Device Methods