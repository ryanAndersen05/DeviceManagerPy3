#external lib imports
import socket
import pyudev
from sys import stdin

#std lib imports
import queue
import threading
from time import sleep

#internal project imports
import DragonMasterSerialDevice
import DragonMasterDevice



"""
@author Ryan Andersen EQ Games (404-643-1783)


Our device manager class that will find and hold all of our connected devices and manage their current state
It will manages messages between our Unity Application and assign commands to the correct devices.
"""
class DragonMasterDeviceManager:
    VERSION = "2.0.0"
    KILL_DEVICE_MANAGER_APPLICATION = False #Setting this value to true will kill the main thread of our Device Manager application effectively closing all other threads

    #region TCP Device Commands
    #This command will be sent as a single byte event simply to inform python that we are still connected to the our Unity application
    STATUS_FROM_UNITY = 0x00 #Periodic update that we should receive from Unity to enusre the game is still running. We will close the application if we have not received a message in 60+ seconds
    DEVICE_CONNECTED = 0x01 #When a new device has successfully been connected to our manager we will send this event to Unity
    DEVICE_DISCONNECTED = 0x02 #When a new device is successfully removed from our manager we will send this message to Unity
    OMNI_EVENT = 0x03 #For messages that we send/receive to our omnidongle
    RETRIEVE_CONNECTED_DEVICES = 0x04 #This will return a device connected event for every currently connected device. This is good on soft reboot when our IO manager does not know what devices are currently connected

    ##DRAX COMMANDS
    DRAX_ID = 0x10

    #Send Events
    DRAX_INPUT_EVENT = 0x11#For button events that we will send to our Unity App

    #Receive Events
    DRAX_OUTPUT_EVENT = 0x12 #The short that is passed in using this command is what we will set our drax output state to be
    DRAX_OUTPUT_BIT_ENABLE_EVENT = 0x13 #Enables the bits that are passed in. Can be multiple bits at once
    DRAX_OUTPUT_BIT_DISABLE_EVENT = 0x14 #Disables the bits that are passed in. Can be multiple bits at once
    DRAX_HARD_METER_EVENT = 0X15 #Event to Increment our hard meters taht are attached to our draxboards

    ##JOYSTICK COMMANDS
    JOYSTICK_ID = 0X20
    JOYSTICK_INPUT_EVENT = 0X21#Input event from the joystick. Sends the x and y values that are currently set on the joystick

    ##PRINTER COMMANDS
    PRINTER_ID = 0X40

    #Receive Events
    PRINTER_CASHOUT_TICKET = 0X41 #Command to print a cashout ticket
    PRINTER_AUDIT_TICKET = 0X042 #Command to print an audit ticket
    PRINTER_CODEX_TICKET = 0X43 #Command to print a codex ticket
    PRINTER_TEST_TICKET = 0X44 #Command to print a test ticket
    PRINTER_REPRINT_TICKET = 0x45 #Command to print a reprint ticket

    #Send Events
    PRINT_COMPLETE_EVENT = 0X45 #Upone completing any print job, you should receive a PRINT_COMPLETE_EVENT message to verify that we successfully printed a ticket
    PRINT_ERROR_EVENT = 0x46 #If there was an error at some point in the print job, we will send this message instead
    PRINTER_STATE_EVENT = 0x47 #Returns the state of the printer

    #Printer Types
    CUSTOM_TG02 = 0X01
    RELIANCE_PRINTER = 0X02
    PYRAMID_PRINTER = 0X03

    ##BILL ACCEPTOR COMMANDS
    BILL_ACCEPTOR_ID = 0X80

    #Send Events
    BA_BILL_INSERTED_EVENT = 0X81 #Bill was inserted event
    BA_BILL_ACCEPTED_EVENT = 0X82 #Bill was accepted event
    BA_BILL_REJECTED_EVENT = 0X83 #Bill was rejected event
    BA_BILL_RETURNED_EVENT = 0x84 #Bill was returned event
    BA_BILL_STATE_UPDATE_EVENT = 0x85

    #Receive Events
    BA_ACCEPT_BILL_EVENT = 0X86 #Command to accept the bill that is currently in escrow
    BA_REJECT_BILL_EVENT = 0X87 #Command to reject the bill that is currently in escrow
    BA_IDLE_EVENT = 0X88 #Command to set the BA to idle
    BA_INHIBIT_EVENT = 0X89 #Command to set the BA to inhibit
    BA_RESET_EVENT = 0X8a #Command to reset the BA (Good if there is some error that isn't resolved automatically)

    #endregion TCP Device Commands


    #region debug variables
    DEBUG_PRINT_EVENTS_SENT_TO_UNITY = False #Mark this true to show events that we enque to send to Unity
    DEBUG_PRINT_EVENTS_RECEIVED_FROM_UNITY = False #Mark this true to show events that we have received from Unity
    DEBUG_TRANSLATE_PACKETS = False #Mark this true if you would like the packet names to be shown in English rather that Raw byte commands

    
    #endregion debum variables


    def __init__(self,):
        self.tcpManager = TCPManager(self)
        self.CONNECTED_OMNIDONGLE = None #Since there should only be one omnidongle in our machine, we will only search until we find the first connection
        self.allConnectedDevices = [] #(DragonMasterDevice)
        self.playerStationDictionary = {}#Key: Parent USB Device Path (string) | Value: Player Station (PlayerStation)
        self.playerStationHashToParentDevicePath = {}#Key: Hash Value (uint) | Value: Parent USB Device Path (string)
        

        self.searchingForDevices = False

        #Start a thread to search for newly connected devices
        deviceAddedThread = threading.Thread(target=self.device_connected_thread,)
        deviceAddedThread.daemon = True
        deviceAddedThread.start()

        debugThread = threading.Thread(target=debug_command_thread, args=(self,))
        debugThread.daemon = True
        debugThread.start()
        
        sleep(.3)
        self.search_for_devices()
        
        # while (True):
        #     self.search_for_devices()
        #     sleep(5)
        return


    #region Threaded events
    """
    This thread is used to poll our application to search for new devices every time a new plugged in device is detected
    """
    def device_connected_thread(self):
        context = pyudev.Context()
        monitor = pyudev.Monitor.from_netlink(context)
        monitor.filter_by(subsystem='usb')

        for device in iter(monitor.poll, None):
            if device.action == 'add':
                self.search_for_devices()
        return


    """
    This thread will be used to periodically poll for newly connected devices. This is more used as a back up incase our
    newly connected event thread fails to detect a new connection
    """
    def periodically_poll_for_devices_thread(self):
        
        return

    #endregion threaded events


    #region Device Management
    

    """
    This method will search for all valid devices that are connected to our machine
    """
    def search_for_devices(self):
        if (self.searchingForDevices):
            print ("We skipped searching for devices. We are already searching")
            return
        self.searchingForDevices = True
        try:
            allConnectedJoysticks, allBaoLinJoysticks = DragonMasterDevice.get_all_connected_joystick_devices()
            allConnectedDraxboards = DragonMasterSerialDevice.get_all_connected_draxboard_elements()
            allConnectedCustomTG02Printers = DragonMasterDevice.get_all_connected_custom_tg02_printer_elements()
            allConnectedReliancePrinters = DragonMasterDevice.get_all_connected_reliance_printer_elements()

            allConnectedDBV400Elements = DragonMasterSerialDevice.get_all_connected_dbv400_comports()
            
            self.deviceContext = pyudev.Context() #we set our device context
            if self.CONNECTED_OMNIDONGLE == None:
                omnidongleElement = DragonMasterSerialDevice.get_omnidongle_comports()
                if omnidongleElement:
                    self.add_new_device(DragonMasterSerialDevice.Omnidongle(self), omnidongleElement)

            for draxElement in allConnectedDraxboards:
                if draxElement and not self.device_manager_contains_draxboard(draxElement):
                    self.add_new_device(DragonMasterSerialDevice.Draxboard(self), draxElement)

            for joystick in allConnectedJoysticks:
                if (joystick != None and not self.device_manager_contains_joystick(joystick)):
                    self.add_new_device(DragonMasterDevice.Joystick(self), joystick)

            for printer in allConnectedCustomTG02Printers:
                if (printer != None and not self.device_manager_contains_printer(printer)):
                    self.add_new_device(DragonMasterDevice.CustomTG02(self), printer)

            for printer in allConnectedReliancePrinters:
                if printer != None and not self.device_manager_contains_printer(printer):
                    self.add_new_device(DragonMasterDevice.ReliancePrinter(self), printer)

            for dbv in allConnectedDBV400Elements:
                if dbv and not self.device_manager_contains_dbv400(dbv):
                    print ("Found")
                    self.add_new_device(DragonMasterSerialDevice.DBV400(self), dbv)
        except Exception as e:
            print ("There was an error while searching for devices.")
            print (e)
        self.searchingForDevices = False
        return


    """
    Adds a new device to our device manager. This will fail to add a device if the device fails to
    start up appropriately
    """
    def add_new_device(self, deviceToAdd, deviceElementNode):
        if (self.allConnectedDevices.__contains__(deviceToAdd)):
            print ("Device was already added to our device manager. Please double check how we added a device twice")
            return
        if (deviceToAdd.start_device(deviceElementNode)):
            self.allConnectedDevices.append(deviceToAdd)
            self.add_new_device_to_player_station_dictionary(deviceToAdd)
            self.send_device_connected_event(deviceToAdd)
            
            print (deviceToAdd.to_string() + " was successfully added to our device manager")
        else:
            deviceToAdd.disconnect_device()#We will run a disconnect device to ensure that we fully disconnect all processes that may be running in our device
            print ("Device Failed Start")
        return



    """
    If a device was connected this method should be called to notify our Unity application of which device was connected
    """
    def send_device_connected_event(self, deviceThatWasAdded):
        deviceTypeID = 0x00
        if isinstance(deviceThatWasAdded, DragonMasterDevice.Joystick):
            deviceTypeID = DragonMasterDeviceManager.JOYSTICK_ID
            pass
        if isinstance(deviceThatWasAdded, DragonMasterDevice.Printer):
            deviceTypeID = DragonMasterDeviceManager.PRINTER_ID
            pass
        if isinstance(deviceThatWasAdded, DragonMasterSerialDevice.Draxboard):
            deviceTypeID = DragonMasterDeviceManager.DRAX_ID
            pass
        if isinstance(deviceThatWasAdded, DragonMasterSerialDevice.DBV400):
            deviceTypeID = DragonMasterDeviceManager.BILL_ACCEPTOR_ID
            pass
        if isinstance(deviceThatWasAdded, DragonMasterSerialDevice.Omnidongle):
            deviceTypeID = DragonMasterDeviceManager.OMNI_EVENT
            pass
        
        self.add_event_to_send(DragonMasterDeviceManager.DEVICE_CONNECTED, [deviceTypeID], self.get_player_station_hash_for_device(deviceThatWasAdded))
        return
        # print ("Device Added ID: " + str(deviceTypeID))

    """
    If a device was removed we should call this method, so that we appropriately notify our Unity Applcation
    """
    def send_device_disconnected_event(self, deviceThatWasRemoved):
        deviceTypeID = 0x00
        if isinstance(deviceThatWasRemoved, DragonMasterDevice.Joystick):
            deviceTypeID = DragonMasterDeviceManager.JOYSTICK_ID
            pass
        if isinstance(deviceThatWasRemoved, DragonMasterDevice.Printer):
            deviceTypeID = DragonMasterDeviceManager.PRINTER_ID
            pass
        if isinstance(deviceThatWasRemoved, DragonMasterSerialDevice.Draxboard):
            deviceTypeID = DragonMasterDeviceManager.DRAX_ID
            pass
        if isinstance(deviceThatWasRemoved, DragonMasterSerialDevice.DBV400):
            deviceTypeID = DragonMasterDeviceManager.BILL_ACCEPTOR_ID
            pass
        if isinstance(deviceThatWasRemoved, DragonMasterSerialDevice.Omnidongle):
            deviceTypeID = DragonMasterDeviceManager.OMNI_EVENT
            pass
        self.add_event_to_send(DragonMasterDeviceManager.DEVICE_DISCONNECTED, [deviceTypeID], self.get_player_station_hash_for_device(deviceThatWasRemoved))
        # print ("Device Removed ID: " + str(deviceTypeID))
        return


    """
    Adds a device to the player station dictionary
    """
    def add_new_device_to_player_station_dictionary(self, deviceToAdd):
        if deviceToAdd.deviceParentPath == None:
                if not isinstance(deviceToAdd, DragonMasterSerialDevice.Omnidongle):
                    print ("Error: " + deviceToAdd.to_string() + " does not contain a parent device path. Please be sure to set one up")
        else:
            if deviceToAdd.deviceParentPath not in self.playerStationDictionary:
                self.playerStationDictionary[deviceToAdd.deviceParentPath] = PlayerStationContainer()
            
            previouslyConnectedDevice = None#Used to warn us that there was already a device connected to this player station
            if isinstance(deviceToAdd, DragonMasterDevice.Joystick):
                previouslyConnectedDevice = self.playerStationDictionary[deviceToAdd.deviceParentPath].connectedJoystick
                self.playerStationDictionary[deviceToAdd.deviceParentPath].connectedJoystick = deviceToAdd
            elif isinstance(deviceToAdd, DragonMasterDevice.Printer):
                previouslyConnectedDevice = self.playerStationDictionary[deviceToAdd.deviceParentPath].connectedPrinter
                self.playerStationDictionary[deviceToAdd.deviceParentPath].connectedPrinter = deviceToAdd
            elif isinstance(deviceToAdd, DragonMasterSerialDevice.DBV400):
                previouslyConnectedDevice = self.playerStationDictionary[deviceToAdd.deviceParentPath].connectedBillAcceptor
                self.playerStationDictionary[deviceToAdd.deviceParentPath].connectedBillAcceptor = deviceToAdd
            elif isinstance(deviceToAdd, DragonMasterSerialDevice.Draxboard):
                previouslyConnectedDevice = self.playerStationDictionary[deviceToAdd.deviceParentPath].connectedDraxboard
                self.playerStationDictionary[deviceToAdd.deviceParentPath].connectedDraxboard = deviceToAdd
                self.playerStationHashToParentDevicePath[deviceToAdd.playerStationHash] = deviceToAdd.deviceParentPath

            # print (deviceToAdd.deviceParentPath)
            print (self.playerStationDictionary[deviceToAdd.deviceParentPath].to_string())

            if previouslyConnectedDevice != None:
                print ("Warning: There are two or more of the same devices connected to our our player station")
                print ("Previously Connected: " + previouslyConnectedDevice.to_string() + " Newly Added: " + deviceToAdd.to_string())

        return

    """
    This method will remove a device from our device manager. This will also process our disconnect command in the device
    that is passed through to ensure that we are properly disconnected from the device manager
    """
    def remove_device(self, deviceToRemove):
        if deviceToRemove == None:
            return

        if self.allConnectedDevices.__contains__(deviceToRemove):
            deviceToRemove.disconnect_device()
            self.remove_device_from_player_station_dictionary(deviceToRemove)
            self.allConnectedDevices.remove(deviceToRemove)
            self.send_device_disconnected_event(deviceToRemove)
            print (deviceToRemove.to_string() + " was successfully removed")
        else:
            if not isinstance(deviceToRemove, DragonMasterSerialDevice.ReliancePrinterSerial):#reliance serial is the one excpetion where we don't remove it normally
                print (deviceToRemove.to_string() + " was not found in our device list. Perhaps it was already removed")


        return

    """
    Safely removes a device from our player station device dictionary
    """
    def remove_device_from_player_station_dictionary(self, deviceToRemove):
        if deviceToRemove == None:
            print ("Device to remove was None...")
            return


        if deviceToRemove.deviceParentPath == None:
            if not isinstance(deviceToRemove, DragonMasterSerialDevice.Omnidongle):
                print ("The device path was None. Something was not properly set up...")
            return

        if deviceToRemove.deviceParentPath not in self.playerStationDictionary:
            print ("Warning: Parent path was not found in playerstation dictionary...")
            return
        
        if isinstance(deviceToRemove, DragonMasterDevice.Joystick):
            self.playerStationDictionary[deviceToRemove.deviceParentPath].connectedJoystick = None
            return
        elif isinstance(deviceToRemove, DragonMasterDevice.Printer):
            self.playerStationDictionary[deviceToRemove.deviceParentPath].connectedPrinter = None
            return
        elif isinstance(deviceToRemove, DragonMasterSerialDevice.Draxboard):
            self.playerStationDictionary[deviceToRemove.deviceParentPath].connectedDraxboard = None
            return
        elif isinstance(deviceToRemove, DragonMasterSerialDevice.DBV400):
            self.playerStationDictionary[deviceToRemove.deviceParentPath].connectedBillAcceptor = None
            return
        return


    """
    Returns an int value that represents the player station that the device is connected.

    NOTE: This has will return 0 if there is no draxboard connected to the player station. This should only be true if teh draxboard
    has completely malfunctioned or you are connecting the device to a random port that is not through the draxboard usb hub
    """
    def get_player_station_hash_for_device(self, device):
        playerStationParentPath = device.deviceParentPath

        if playerStationParentPath == None or playerStationParentPath not in self.playerStationDictionary:
            return 0

        playerStation = self.playerStationDictionary[playerStationParentPath]
        
        if playerStation.connectedDraxboard == None:
            return 0

        return playerStation.connectedDraxboard.playerStationHash

    """

    """
    def get_parent_usb_path_from_player_station_hash(self, pStationHash):
        if pStationHash in self.playerStationHashToParentDevicePath:
            return self.playerStationHashToParentDevicePath[pStationHash]
        return None

    #endregion Device Management


    #region TCP Received Data Events

    """
    This method will be called to interpret all the packets that we receive from our Unity application
    """
    def interpret_event_from_unity(self, eventMessage):
        if eventMessage == None or len(eventMessage) <= 0:
            print ("The event message that was passed in was empty...")
            return


        if eventMessage == DragonMasterDeviceManager.RETRIEVE_CONNECTED_DEVICES:
            self.on_retrieve_connected_devices()
            return
        elif eventMessage == DragonMasterDeviceManager.STATUS_FROM_UNITY:
            self.on_status_from_unity()
            return
        elif eventMessage == DragonMasterDeviceManager.OMNI_EVENT:
            self.on_omnidongle_event_received(eventMessage)
            return
        
        #All event functions below this poinr need to have a hash
        if len(eventMessage) < 5:
            print ("The event message was too short...")
            return 
        playerStationHash = convert_byte_array_to_value(eventMessage[1:4])
        #Drax Outputs
        if eventMessage == DragonMasterDeviceManager.DRAX_HARD_METER_EVENT:
            self.on_drax_hard_meter_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.DRAX_OUTPUT_EVENT:
            self.on_drax_output_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.DRAX_OUTPUT_BIT_ENABLE_EVENT:
            self.on_drax_output_bit_enable_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.DRAX_OUTPUT_BIT_DISABLE_EVENT:
            self.on_drax_output_bit_disable_event(playerStationHash, eventMessage[5:])
            return

        #Printer Outputs
        elif eventMessage == DragonMasterDeviceManager.PRINTER_CASHOUT_TICKET:
            self.on_print_cashout_ticket_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.PRINTER_AUDIT_TICKET:
            self.on_print_audit_ticket_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.PRINTER_CODEX_TICKET:
            self.on_print_codex_ticket_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.PRINTER_TEST_TICKET:
            self.on_print_test_ticket_event(playerStationHash, eventMessage[5:])
            return
            
        #Bill Acceptor Outputs
        elif eventMessage == DragonMasterDeviceManager.BA_IDLE_EVENT:
            self.on_ba_idle_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.BA_INHIBIT_EVENT:
            self.on_ba_inhibit_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.BA_RESET_EVENT:
            self.on_ba_reset_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.BA_ACCEPT_BILL_EVENT:
            self.on_ba_accept_bill_event(playerStationHash, eventMessage[5:])
            return
        elif eventMessage == DragonMasterDeviceManager.BA_REJECT_BILL_EVENT:
            self.on_ba_reject_bill_event(playerStationHash, eventMessage[5:])
            return

    """
    This will send all the currently connected devices to our unity application. Helpful if our game restarts while the machine is still running
    """
    def on_retrieve_connected_devices(self):
        for dev in self.allConnectedDevices:
            self.send_device_connected_event(dev)
        return

    """
    We call this method whenever we receive a message from unity telling us that we are completely connected
    """
    def on_status_from_unity(self):

        return

    """
    Sends an event to the current connected Omnidongle device
    """
    def on_omnidongle_event_received(self, eventMessage):
        if DragonMasterDeviceManager.CONNECTED_OMNIDONGLE != None:
            DragonMasterDeviceManager.CONNECTED_OMNIDONGLE.send_data_to_omnidongle(eventMessage[1:])
        return

    #region draxboard tcp events

    def on_drax_hard_meter_event(self, playerStationHash, eventData):
        draxboard = self.get_draxboard_from_player_station_hash(playerStationHash)
        if draxboard == None:
            return
        if len(eventData) < 2:
            return
        draxboard.increment_meter_ticks(eventData[0], eventData[1])        
        return

    """
    This method should be called upon receiving an event from unity to toggle the output of the Draxboard
    """
    def on_drax_output_event(self, playerStationHash, eventData):
        draxboard = self.get_draxboard_from_player_station_hash(playerStationHash)
        if draxboard == None:
            return
        if len(eventData) < 2:
            return
        draxboard.toggle_output_state_of_drax(eventData[0] << 8 + eventData[1], 0)
        return

    """
    If we want to enable one single bit we can call this method to set that bit to true in the Drax
    """
    def on_drax_output_bit_enable_event(self, playerStationHash, eventData):
        draxboard = self.get_draxboard_from_player_station_hash(playerStationHash)
        if draxboard == None:
            return
        if len(eventData) < 2:
            return
        draxboard.toggle_output_state_of_drax(eventData[0] << 8 + eventData[1], 1)
        return

    """
    
    """
    def on_drax_output_bit_disable_event(self, playerStationHash, eventData):
        draxboard = self.get_draxboard_from_player_station_hash(playerStationHash)
        if draxboard == None:
            return
        if len(eventData):
            return
        draxboard.toggle_output_state_of_drax(eventData[0] << 8 + eventData[1], 2)
        return
    #endregion draxboard tcp events

    #region bill acceptor tcp events
    """
    This method should be called when a bill acceptor idle event is triggered from Unity
    """
    def on_ba_idle_event(self, playerSationHash, eventData):

        return

    """
    This method should be called when a bill acceptor inhibit event is called from Unity
    """
    def on_ba_inhibit_event(self, playerStationHash, eventData):

        return

    """
    This method should be called when a bill acceptor reset event is called from Unity
    """
    def on_ba_reset_event(self, playerStationHash, eventData):

        return

    """
    If there is a bill in pending this message should be sent to our bill acceptor to appropriately accept it
    """
    def on_ba_accept_bill_event(self, playerStationHash, eventData):

        return

    """
    If there is a bill pending in our bill acceptor this should be called to properly reject the bill
    """
    def on_ba_reject_bill_event(self, playerStationHash, eventData):

        return
    #endregion bill acceptor tcp events

    #region printer tcp events
    """
    Method that should be called to print out a cashout ticket
    """
    def on_print_cashout_ticket_event(self, playerStationHash, eventData):

        return

    """
    Method that should be called to print out a codex ticket
    """
    def on_print_codex_ticket_event(self, playerStationHash, eventData):

        return

    """
    Method that should be called to print out an audit ticket
    """
    def on_print_audit_ticket_event(self, playerStationHash, eventData):

        return

    """
    Method that should be called when attempting to print out a test ticket from our 
    """
    def on_print_test_ticket_event(self, eventData):

        return

    """
    This method should be called whenever a reprint is requested from our Unity application
    """
    def on_print_reprint_ticket_event(self, playerStationHash, eventData):

        return

    #endregion printer tcp events

    #endregion TCP Received Data Events

    #region TCP Communication
    """
    Queue up an event to send to our Unity Application. This should always be of the type
    byteArray

    inputs:
    eventID - the event id of the packet. This is the byte that defines the action that will be taken upon being received by our unity application
    eventData - any required data for the packet we are sending
    playerStationHash - if value is left as none it will not be added to the packet. But devices that are associated with a specific player station
    """
    def add_event_to_send(self, eventID, eventData, playerStationHash = None):
        messageToSend = []
        messageToSend.append(eventID)
        if playerStationHash != None:
            messageToSend += convert_value_to_byte_array(playerStationHash, numberOfBytes=4)
        messageToSend += eventData
        
        
        
        self.tcpManager.add_event_to_send(messageToSend)
        return

    """
    Upon receiving an event from our Unity Application, we will process the command through this method

    Packets that are received will contain the following layout:
    [Function, playerStationID, data....]
    """
    def execute_received_event(self, eventList):
        if (len(eventList) <= 0):
            return

        for event in eventList:
            self.interpret_event_from_unity(event)
            pass
        return
        
    #endregion TCP Communication
    pass

    #region get device methods
    """
    Returns a draxboard using the player station hash
    """
    def get_draxboard_from_player_station_hash(self, playerStationHash):
        parentUSBPath = self.get_parent_usb_path_from_player_station_hash(playerStationHash)
        if  parentUSBPath == None:
            return None
        if parentUSBPath not in self.playerStationDictionary:
            return None
        return self.playerStationDictionary[parentUSBPath].connectedDraxboard

    """
    Returns a bill acceptor object using the player station hash
    """
    def get_bill_acceptor_from_player_station_hash(self, playerStationHash):
        parentUSBPath = self.get_parent_usb_path_from_player_station_hash(playerStationHash)
        if  parentUSBPath == None:
            return None
        if parentUSBPath not in self.playerStationDictionary:
            return None
        return self.playerStationDictionary[parentUSBPath].connectedBillAcceptor

    """
    Returns a printer device object using the player station hash
    """
    def get_printer_from_player_station_hash(self, playerStationHash):
        parentUSBPath = self.get_parent_usb_path_from_player_station_hash(playerStationHash)
        if  parentUSBPath == None:
            return None
        if parentUSBPath not in self.playerStationDictionary:
            return None
        return self.playerStationDictionary[parentUSBPath].connectedPrinter

    """
    Returns a joystick device object using the palyer station hash
    """
    def get_joystick_from_player_station_hash(self, playerStationHash):
        parentUSBPath = self.get_parent_usb_path_from_player_station_hash(playerStationHash)
        if  parentUSBPath == None:
            return None
        if parentUSBPath not in self.playerStationDictionary:
            return None
        return self.playerStationDictionary[parentUSBPath].connectedJoystick
        
    #endregion get device methods

    #region Contains Methods

    """
    Returns whether or not the joystick that is passed into the method was already added to our
    device manager list
    """
    def device_manager_contains_joystick(self, joystickDevice):
        for dev in self.allConnectedDevices:
            if isinstance(dev, DragonMasterDevice.Joystick):
                if dev.joystickDevice.phys == joystickDevice.phys:
                    return True
        return False

    """
    Returns whether or not the draxboard that was passed into the method was already added to our
    device manager list
    """
    def device_manager_contains_draxboard(self, draxboardElement):
        for dev in self.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.Draxboard):
                if dev.comport == draxboardElement.device:
                    return True
        return False


    """
    Returns whether or not the draxboard that was passed into the method was already added to our
    device manager list
    """
    def device_manager_contains_dbv400(self, dbvElement):
        print (dbvElement)
        for dev in self.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.DBV400):
                if dev.comport == dbvElement.device:
                    return True
        return False

    """
    Returns whether or not the printer that is passed through was already added to our device manager
    """
    def device_manager_contains_printer(self, printerElement):
        for dev in self.allConnectedDevices:
            if isinstance(dev, DragonMasterDevice.Printer):
                if dev.printerObject != None and dev.printerObject.device.port_numbers == printerElement.port_numbers\
                    and dev.printerObject.device.bus == printerElement.bus:
                    return True
        return False
#endregion Contains Methods

#region helper classes
    """
    Method that checks to see if there are any joystick events that we should be sending off
    """
    def check_for_joystick_events(self):
        for key in self.playerStationDictionary:
            if self.playerStationDictionary[key].connectedJoystick != None:
                self.playerStationDictionary[key].connectedJoystick.send_updated_joystick_to_unity_application()


"""
This class acts as a container of all the devices that are connected to this device
"""
class PlayerStationContainer:
    
    def __init__(self):
        self.connectedDraxboard = None
        self.connectedBillAcceptor = None
        self.connectedJoystick = None
        self.connectedPrinter = None    

    def to_string(self):
        playerStationString = '-' * 32
        if self.connectedJoystick:
            playerStationString += '\nJOY   |' + self.connectedJoystick.to_string()
        if self.connectedDraxboard:
            playerStationString += '\nDRAX  |' + self.connectedDraxboard.to_string()
        if self.connectedPrinter:
            playerStationString += '\nPRINT |' + self.connectedPrinter.to_string()
        if self.connectedBillAcceptor:
            playerStationString += '\nDBV   |' + self.connectedBillAcceptor.to_string()
        playerStationString += '\n' + '-' * 32
        return playerStationString
        

#endregion helper classes


#######################################################################################################################################################
"""
Class that handles all of our TCP communication. This will send and receive packets between our Unity application

Note: Packets should be sent in the form of [Function, playerStationID, Data.....]
"""
class TCPManager:
    MAX_THREADING_COUNT = 500
    HOST_ADDRESS = "127.0.0.1"
    SEND_PORT = 25001
    RECEIVE_PORT = 35001

    MAX_RECV_BUFFER = 1024

    def __init__(self, deviceManager):
        self.sendingEventsToOurUnityApplication = False
        self.tcpEventQueue = queue.Queue()#Queue of events that we want to send to Unity

        #REMEBER TO UNCOMMENT
        self.start_new_socket_receive_thread()
        self.start_new_socket_send_thread()
        self.deviceManager = deviceManager
        


    """
    This enqueues an event to send to our unity application
    """
    def add_event_to_send(self, messageToQueueForSend):
        if messageToQueueForSend == None:
            print("message to send was none... what happened")
            return
        self.tcpEventQueue.put(messageToQueueForSend)
        return

    """
    Start a new instance of a socket thread that will send data to our Unity Application
    """
    def start_new_socket_send_thread(self):
        sendThread = threading.Thread(target=self.socket_send)
        sendThread.daemon = True
        sendThread.start()
        return

    """
    Start a new instance of a socket thread that will receive data from our unity application
    """
    def start_new_socket_receive_thread(self):
        receiveThread = threading.Thread(target=self.socket_receive)
        receiveThread.daemon = True
        receiveThread.start()
        return


    """
    This method sends all of the events that are currently in our event queue to our
    Unity Application
    """
    def socket_send(self):
        
        totalCount = 0
        
        while (totalCount < TCPManager.MAX_THREADING_COUNT):
            try:
                socketSend = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                socketSend.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                socketSend.bind((TCPManager.HOST_ADDRESS, TCPManager.SEND_PORT))
                socketSend.listen(1)
                conn, addr = socketSend.accept()

                if conn != None:
                    bytesToSend = []
                    while not self.tcpEventQueue.empty():
                        eventToAdd = self.tcpEventQueue.get()
                        eventToAdd.insert(0, len(eventToAdd))
                        eventToAdd.append(self.calculate_checksum_of_packet(eventToAdd))

                        bytesToSend = bytesToSend + eventToAdd
                        
                        if (DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_SENT_TO_UNITY):
                            print (eventToAdd)
                        
                    convertedByteArrayToSend = bytearray(bytesToSend)#Converting our array into a byte array to send through our TCP socket
                    
                    conn.send(convertedByteArrayToSend)
                    conn.close()

                    self.deviceManager.check_for_joystick_events()#Potentially we might want to look into some other form of sending joystick events...
                socketSend.close()
            except Exception as e:
                print ("Error for socket send")
                print (e)
                if socketSend != None:
                    socketSend.close()

            sleep(.01)
            totalCount += 1
            pass
        self.start_new_socket_send_thread()
        return


    """
    This method will be called to receive 
    """
    def socket_receive(self):
        totalCount = 0
        
        while (totalCount < TCPManager.MAX_THREADING_COUNT):
            try:
                socketRead = socket.socket()
                socketRead.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
                socketRead.connect((TCPManager.HOST_ADDRESS, TCPManager.RECEIVE_PORT))

                buff = socketRead.recv(TCPManager.MAX_RECV_BUFFER)
                fullResponse = buff
                while buff:
                    buff = socketRead.recv(TCPManager.MAX_RECV_BUFFER)
                    if (buff):
                        fullResponse = fullResponse + buff
                if (len(fullResponse) > 0):
                    self.deviceManager.execute_received_event(self.separate_events_received_into_list(fullResponse))
                socketRead.shutdown(socket.SHUT_RDWR)
            except Exception as e:
                # print ("Receive Error")
                if socketRead != None:
                    socketRead.close()
                
                # print (e)
            sleep(.02)
            totalCount += 1
            pass

        self.start_new_socket_receive_thread()
        return

    """
    Separates the events into a list. Upon receiving a packet, it is typically sent as one long bytearray.
    this will break up our events into a list of byte arrays that can be read as events. We will remove the 
    byte that shows the size of the packet. 
    """
    def separate_events_received_into_list(self, fullEventData):
        if (len(fullEventData) == 0):
            return
        eventMessages = []
        while (len(fullEventData) > 0):
            endOfMessage = 1 + fullEventData[0]
            if (len(fullEventData) > endOfMessage):
                endOfMessage = len(fullEventData)
            eventMessages.append(fullEventData[1:endOfMessage])
            fullEventData = fullEventData[endOfMessage - 1:]
        
        for eventMessage in eventMessages:
            self.deviceManager.interpret_event_from_unity(eventMessage)
        return
    pass

    """
    This method will calculate the checksum value that should be appended to the packet that we are delivering to our Unity Application
    """
    def calculate_checksum_of_packet(self, packetBeforeChecksumByte):
        checkSumValue = 0
        for val in packetBeforeChecksumByte:
            checkSumValue ^= val
        return checkSumValue

"""
Converts a byte array to a value using little endian

NOTE: Little Endian -
input:[0x01, 0x23, 0x45, 0x67]
output:0x01234567
"""
def convert_byte_array_to_value(byteArray):
    if len(byteArray) < 4:
        print("The byte array that was passed in did not meet our 4 byte requirement")
        return
        
    uintValue = 0
    for i in range(len(byteArray)):
        uintValue += (byteArray[i] << (i * 8))
    return uintValue


"""
This method converts a whole number value into a byte array. This should come in easy for TCP commands

input: valueToConvert = 0x301a, numberOfBytes = 4
output: [0x00, 0x00, 0x30, 0x1a]
"""
def convert_value_to_byte_array(valueToConvert, numberOfBytes=4):
    convertedByteArray = []
    for i in range(numberOfBytes - 1, -1, -1):
        byteVal = ((valueToConvert >> (i * 8)) & 0xff)
        convertedByteArray.append(byteVal)

    return convertedByteArray



#region string helper methods
"""
Returns a new string that is of the desired length. Fills in remaining space with
spacingChar value. Make sure that spacingChar is of length 1 if you want accurately spaced
string
"""
def set_string_length(string1, lengthOfString = 60, spacingChar = ' '):
    remainingLength = lengthOfString - len(string1)
    newStringToReturn = ''
    if remainingLength > 0:
        newStringToReturn = spacingChar * int(remainingLength / 2)
    newStringToReturn = newStringToReturn + string1
    remainingLength = lengthOfString - len(newStringToReturn)
    if remainingLength > 0:
        newStringToReturn += spacingChar * remainingLength

    return newStringToReturn


"""
Returns a new string that is of size lengthOfString. Fills the remaining space between string1 and string2
with the char spacingChar. Please make sure that the variable spacingChar is of length = 1 if you want
accurately sized string.
"""
def set_string_length_multiple(string1, string2, lengthOfString = 60, spacingChar = ' '):
    remainingLength = lengthOfString - len(string1) - len(string2)

    if remainingLength > 0:
        return string1 + (spacingChar * remainingLength) + string2
    else:
        return string1 + string2

#endregion string helper methods


#region debug methods

def debug_command_thread(deviceManager):

    while(True):
        commandToRead = stdin.readline()
        if commandToRead != None:
            interpret_debug_command(commandToRead,deviceManager)


"""
Pass in the debug command that was entered into the terminal to here and it will perform the appropriate action if there is a valid function associated
with it
"""
def interpret_debug_command(commandToRead, deviceManager):
    # debug command format: COMPORT COMMAND
    # ex: 0 RESET #This would correlate to Serial Port 0
    serialKey = "/dev/ttyACM"
    commandSplit = commandToRead.split()
    if commandSplit == None or len(commandSplit) == 0:
        print ("Command Entered was too short")
        return
    command = commandSplit[0]
    command = command.lower()

    #GENERAL DEBUG
    if command == "help":
        debug_help_message()
        return
    elif command == "quit":
        #Setting this value to true will kill the main thread of the python application
        DragonMasterDeviceManager.KILL_DEVICE_MANAGER_APPLICATION = True
        return
    elif command == "test":
        debug_test_event(deviceManager)
        return
    elif command == "status":
        debug_status_message(deviceManager)
        return
    elif command == "version":
        print("Version: v" + DragonMasterDeviceManager.VERSION)
        return
    #DRAX DEBUG
    elif command == "bitenable":
        if len(commandSplit) >= 3:
            debug_bitenable_drax(deviceManager, commandSplit[1], commandSplit[2])
            return
        elif len(commandSplit) >= 2:
            debug_bitenable_drax(deviceManager, commandSplit[1])
            return
        else:
            debug_bitenable_drax(deviceManager)
            return
    elif command == "bitdisable":
        if len(commandSplit) >= 3:
            debug_bitdisable_drax(deviceManager, commandSplit[1], commandSplit[2])
            return
        elif len(commandSplit) >= 2:
            debug_bitdisable_drax(deviceManager, commandSplit[1])
            return
        else:
            debug_bitdisable_drax(deviceManager)
            return
    elif command == "draxout":
        if len(commandSplit) >= 3:
            debug_draxout(deviceManager, commandSplit[1], commandSplit[2])
            return
        elif len(commandSplit) >= 2:
            debug_draxout(deviceManager, commandSplit[1])
            return
        else:
            debug_draxout(deviceManager)
            return
    elif command == "meter":
        if len(commandSplit) >= 4:
            debug_draxout(deviceManager, commandSplit[1], commandSplit[2], commandSplit[3])
        elif len(commandSplit) >= 3:
            debug_draxout(deviceManager, commandSplit[1], commandSplit[2])
            return
        elif len(commandSplit) >= 2:
            debug_draxout(deviceManager, commandSplit[1])
            return
        else:
            debug_draxout(deviceManager)
            return
    #PRINT DEBUG
    elif command == "print":

        return
    elif command == "rprint":

        return
    elif command == 'tprint':
        
        return
    elif command == 'cprint':

        return
    elif command == 'aprint':

        return
    #BILL ACCEPTOR DEBUG
    if (len(commandSplit) < 2):
        return
    comPort = serialKey + commandSplit[0]
    for device in deviceManager.allConnectedDevices:
        if isinstance(device, DragonMasterDevice.DragonMasterSerialDevice.DBV400):
            if device.comport == comPort:
                interpret_DBV_command(device,commandSplit[1])
                return
    return
    

"""
Prints out the current state of every device that is currently connected to our machine
"""
def debug_status_message(deviceManager):
    print ()
    if deviceManager.CONNECTED_OMNIDONGLE != None:
        print ("Connected Omnidongle: " + deviceManager.CONNECTED_OMNIDONGLE.to_string())
    else:
        print ("No Omnidongle Is Connected")
    print ('-' * 60)

    if len(deviceManager.allConnectedDevices) == 0:
        print ("No devices connected...")
        return

    for key in deviceManager.playerStationDictionary:
        print (deviceManager.playerStationDictionary[key].to_string())
    
    return

"""
Function to test our threaded device events
"""
def debug_test_event(deviceManager):
    for dev in deviceManager.allConnectedDevices:
        for i in range(3):
            dev.add_event_to_queue(dev.to_string)


"""
Prints out a help message to the user to have easy access to what commands to what
"""
def debug_help_message():
    print (set_string_length("help", 60, '-'))
    print ("You can find the player station associated with each device with the command 'status'")
    print ("FORMAT FOR ALL DEVICE COMMANDS: 'command playerstation data...'")
    print ("NOTE: If you only enter the command it will perform a default function to ALL devices that correspond to that function")
    print ("NOTE: To send commands to all playerstation enter -1. Otherwise enter the player station number associated with the device you would like to test")
    print ('-' * 60)
    print ('**General Commands**')
    print ("'quit' - This will exit the python appliation by killing the main thread")
    print ("'status' - Displays all connected devices and their current state")
    print ("'version' - Prints the current version of our python application.")
    print ("'msgout' - This will enable/disable displaying messages that are received from our Unity Application")
    print ("'msgin' - This will enable/disable the messages that we queue to send to our Unity Application")
    print ("'msgtrans' - Translates the packets that we are sending and receiving from Unity")
    print ('-' * 60)
    print ("**Draxboard Commands")
    print ("'bitenable - enter 0-15 to enable a specific output on our Draxboard (data=[bitToToggle])")
    print ("'bitdisable - enter 0-15 to disable a specific output on our Draxboard (data=[bitToToggle])")
    print ("'draxout' - enter a ushort value and the draxboard output will be set to that state (data=[ushortOutputState])")
    print ("'meter' - increments the hard meters attached to our draxboards (data=[meterID, #ofTicks])")
    print ('-' * 60)
    print ("**JOYSTICK COMMANDS**")
    print ("'displayjoy' - This will print out all joystick values that are gathered. To turn off reenter the command (data=[])")
    print ('-' * 60)
    print ("**Printer Commands**")
    print ("'print' - Prints a sample voucher ticket (data=[])")
    print ("'rprint' - Prints a sample reprint ticket (data=[])")
    print ("'tprint' - Prints a test ticket as it would be displayed from our Unity Application (data=[])")
    print ("'cprint' - Prints a sample Codex Ticket (data=[])")
    print ("'aprint' - Prints a sample Audit Ticket (data=[])")
    print ('-' * 60)
    print ("**Bill Acceptor Commands**")
    print ("'reset' - sends a command to reset a bill acceptor")
    print ("'idle' - sends an idle command to a bill acceptor")
    print ("'inhibit' - sends an inhibit request to a bill acceptor")
    print ("'stack' - sends a command to stack a bill if it is currently held in escrow")
    print ("'reject' - sends a command to reject a bill that is currently in escrow")
    print ('-' * 60)

    return

#region debug drax functions
"""
Debug method used to enable a bit on the draxboard output
"""
def debug_bitenable_drax(deviceManager, playerstation = -1, bitToEnable = 0):
    
    return

"""
Debug method used to disable a bit on the draxboard output
"""
def debug_bitdisable_drax(deviceManager, playerstation = -1, bitToDisable = 0):

    return


"""
Debug method used to set that Draxboard output state
"""
def debug_draxout(deviceManager, playerstation = -1, outputStat = 0):

    return

"""
Debug method used to increment the hard meters that are attached to the draxboards
"""
def debug_meter_increment(deviceManager, playerstation = -1, meterID=0, incrementValue=1):

    return
#endregion debug drax functions
                

def interpret_DBV_command(dbv, command):
    command = command.upper()
    if command == "RESET":
        dbv.reset_dbv()
    elif command == "IDLE":
        dbv.idle_dbv()
    elif command == "INHIBIT":
        dbv.inhibit_dbv()
    elif command == "STATE":
        dbv.get_dbv_state()
    elif command == "STACK":
        dbv.stack_bill()
    elif command == "REJECT":
        dbv.reject_bill()
    

"""
Debug method that prints all the currently connected player station devices
"""
def debug_print_all_player_stations(deviceManager):
    widthOfPrint = 32
    print ("State Of All Collected Devices")
    print ('=' * widthOfPrint)
    for pStation in deviceManager.playerStationDictionary.values:
        print (pStation.to_string())

    print ('=' * widthOfPrint)

    return

"""

"""
def debug_set_dbv_to_idle(dbvComport):

    return

"""
Debug method that will set our dbv to the inhibit state based on the dbv comport that is passed in
"""
def debug_set_dbv_to_inhibit(dbvComport):

    return

"""
Debug method that will reset our DBV based on the comport
"""
def debug_reset_dbv(dbvComport):
    
    return

"""
Returns a string representation of the commands that are being sent and received. This is relly only for debugging purposes
"""
def byte_command_to_string(byteCommand):
    if byteCommand == DragonMasterDeviceManager.STATUS_FROM_UNITY:
        return "STATUS"
    elif byteCommand == DragonMasterDeviceManager.DEVICE_CONNECTED:
        return "DEVICE_CONNECTED"
    elif byteCommand == DragonMasterDeviceManager.DEVICE_DISCONNECTED:
        return "DEVICE_DISCONNECTED"
    elif byteCommand == DragonMasterDeviceManager.OMNI_EVENT:
        return "OMNI_EVENT"
    elif byteCommand == DragonMasterDeviceManager.RETRIEVE_CONNECTED_DEVICES:
        return "RETRIEVE_ALL_DEVICES"
    elif byteCommand == DragonMasterDeviceManager.DRAX_INPUT_EVENT:
        return "DRAX_INPUT"
    elif byteCommand == DragonMasterDeviceManager.DRAX_OUTPUT_EVENT:
        return "DRAX_OUTPUT"
    elif byteCommand == DragonMasterDeviceManager.DRAX_OUTPUT_BIT_ENABLE_EVENT:
        return "DRAX_BIT_ENABLE"
    elif byteCommand == DragonMasterDeviceManager.DRAX_OUTPUT_BIT_DISABLE_EVENT:
        return "DRAX_BIT_DISABLE"
    elif byteCommand == DragonMasterDeviceManager.DRAX_HARD_METER_EVENT:
        return "DRAX_HARD_METER"
    elif byteCommand == DragonMasterDeviceManager.JOYSTICK_INPUT_EVENT:
        return "JOYSTICK_AXIS"
    elif byteCommand == DragonMasterDeviceManager.PRINTER_CASHOUT_TICKET:
        return "PRINT_CASHOUT"
    elif byteCommand == DragonMasterDeviceManager.PRINTER_AUDIT_TICKET:
        return "PRINT_AUDIT"
    elif byteCommand == DragonMasterDeviceManager.PRINTER_CODEX_TICKET:
        return "PRINT_CODEX"
    elif byteCommand == DragonMasterDeviceManager.PRINTER_TEST_TICKET:
        return "PRINT_TEST"
    elif byteCommand == DragonMasterDeviceManager.PRINTER_REPRINT_TICKET:
        return "PRINT_REPRINT"
    elif byteCommand == DragonMasterDeviceManager.PRINT_COMPLETE_EVENT:
        return "PRINT_COMPLETE"
    elif byteCommand == DragonMasterDeviceManager.PRINT_ERROR_EVENT:
        return "PRINT_ERROR_DURING_PRINT"
    elif byteCommand == DragonMasterDeviceManager.PRINTER_STATE_EVENT:
        return "PRINT_STATE"
    elif byteCommand == DragonMasterDeviceManager.BA_BILL_INSERTED_EVENT:
        return "BA_BILL_INSERT"
    elif byteCommand == DragonMasterDeviceManager.BA_BILL_ACCEPTED_EVENT:
        return "BA_BILL_ACCEPTED"
    elif byteCommand == DragonMasterDeviceManager.BA_BILL_REJECTED_EVENT:
        return "BA_BILL_REJECTED"
    elif byteCommand == DragonMasterDeviceManager.BA_BILL_RETURNED_EVENT:
        return "BA_BILL_RETURNED"
    elif byteCommand == DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT:
        return "BA_BILL_STATE"
    elif byteCommand == DragonMasterDeviceManager.BA_ACCEPT_BILL_EVENT:
        return "BA_ACCEPT_BILL"
    elif byteCommand == DragonMasterDeviceManager.BA_REJECT_BILL_EVENT:
        return "BA_REJECT_BILL"
    elif byteCommand == DragonMasterDeviceManager.BA_IDLE_EVENT:
        return "BA_IDLE"
    elif byteCommand == DragonMasterDeviceManager.BA_INHIBIT_EVENT:
        return "BA_INHIBIT"
    elif byteCommand == DragonMasterDeviceManager.BA_RESET_EVENT:
        return "BA_RESET"

    return "Byte Command Unknown..."


#endregion debug methods
