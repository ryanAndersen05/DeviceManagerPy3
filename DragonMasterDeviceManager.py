#external lib imports
import socket
import pyudev
import sys
from sys import stdin
import re

#std lib imports
import queue
import threading
from time import sleep
import pytz
import os
import time
import datetime

#internal project imports
import DragonMasterSerialDevice
import DragonMasterDevice



"""
@author Ryan Andersen, EQ Games, Phone #: (404-643-1783)


Our device manager class that will find and hold all of our connected devices and manage their current state
It will manages messages between our Unity Application and assign commands to the correct devices.
"""
class DragonMasterDeviceManager:
    VERSION = "2.3.0"
    KILL_DEVICE_MANAGER_APPLICATION = False #Setting this value to true will kill the main thread of our Device Manager application effectively closing all other threads
    DRAGON_MASTER_VERSION_NUMBER = "CFS101 0000"
    #region TCP Device Commands
    #This command will be sent as a single byte event simply to inform python that we are still connected to the our Unity application
    STATUS_FROM_UNITY = 0x00 #Periodic update that we should receive from Unity to enusre the game is still running. We will close the application if we have not received a message in 60+ seconds
    DEVICE_CONNECTED = 0x01 #When a new device has successfully been connected to our manager we will send this event to Unity
    DEVICE_DISCONNECTED = 0x02 #When a new device is successfully removed from our manager we will send this message to Unity
    OMNI_EVENT = 0x03 #For messages that we send/receive to our omnidongle
    RETRIEVE_CONNECTED_DEVICES = 0x04 #This will return a device connected event for every currently connected device. This is good on soft reboot when our IO manager does not know what devices are currently connected
    KILL_APPLICATION_EVENT = 0x05 #This event will trigger an event to kill the main thread, effectively shutting down the entire application

    ##DRAX COMMANDS
    DRAX_ID = 0x10

    #Send Events
    DRAX_INPUT_EVENT = 0x11#For button events that we will send to our Unity App

    #Receive Events
    DRAX_OUTPUT_EVENT = 0x12 #The short that is passed in using this command is what we will set our drax output state to be
    DRAX_OUTPUT_BIT_ENABLE_EVENT = 0x13 #Enables the bits that are passed in. Can be multiple bits at once
    DRAX_OUTPUT_BIT_DISABLE_EVENT = 0x14 #Disables the bits that are passed in. Can be multiple bits at once
    DRAX_HARD_METER_EVENT = 0X15 #Event to Increment our hard meters taht are attached to our draxboards
    DRAX_METER_ERROR = 0X16 #This message will be sent if there is an error attempting to increment
    DRAX_STATUS_EVENT = 0x17#This method should be sent whenever we receive a status event from our Draxboard which essentially tells us the version number and player station number (if valid)

    ##JOYSTICK COMMANDS
    JOYSTICK_ID = 0X20
    JOYSTICK_INPUT_EVENT = 0X21#Input event from the joystick. Sends the x and y values that are currently set on the joystick
    #Joystick Type
    ULTIMARC_JOYSTICK = 0x01
    BAOLIAN_JOYSTICK = 0x02

    ##PRINTER COMMANDS
    PRINTER_ID = 0X40

    #Receive From Unity Events
    PRINTER_CASHOUT_TICKET = 0X41 #Command to print a cashout/voucher ticket
    PRINTER_AUDIT_TICKET = 0X042 #Command to print an audit ticket
    PRINTER_CODEX_TICKET = 0X43 #Command to print a codex ticket
    PRINTER_TEST_TICKET = 0X44 #Command to print a test ticket
    PRINTER_REPRINT_TICKET = 0x45 #Command to print a reprint ticket

    #Send To Unity Events
    PRINT_COMPLETE_EVENT = 0X46 #Upon completing any print job, you should receive a PRINT_COMPLETE_EVENT message to verify that we successfully printed a ticket
    PRINT_ERROR_EVENT = 0x47 #If there was an error at some point in the print job, we will send this message instead
    PRINTER_STATE_EVENT = 0x48 #Returns the state of the printer

    #Printer Types (Returning a type of 0 represents an invalid printer type)
    CUSTOM_TG02 = 0X01 
    RELIANCE_PRINTER = 0X02
    PYRAMID_PRINTER = 0X03

    ##BILL ACCEPTOR COMMANDS
    BILL_ACCEPTOR_ID = 0X80

    #Send To Unity Events
    BA_BILL_INSERTED_EVENT = 0X81 #Bill was inserted event
    BA_BILL_ACCEPTED_EVENT = 0X82 #Bill was accepted event
    BA_BILL_REJECTED_EVENT = 0X83 #Bill was rejected event
    BA_BILL_RETURNED_EVENT = 0x84 #Bill was returned event
    BA_BILL_STATE_UPDATE_EVENT = 0x85 #Event to Send the status of the bill acceptor
    #Bill Acceptor type
    BA_DBV_400 = 0x01
    BA_iVIZION = 0x02
    BA_DBV_500 = 0x03

    #Receive From Unity Events
    BA_ACCEPT_BILL_EVENT = 0X86 #Command to accept the bill that is currently in escrow
    BA_REJECT_BILL_EVENT = 0X87 #Command to reject the bill that is currently in escrow
    BA_IDLE_EVENT = 0X88 #Command to set the BA to idle
    BA_INHIBIT_EVENT = 0X89 #Command to set the BA to inhibit
    BA_RESET_EVENT = 0X8a #Command to reset the BA (Good if there is some error that isn't resolved automatically)
    #endregion TCP Device Commands

    #region const variables
    STATUS_MAX_SECONDS_TO_WAIT = 65
    #endregion const variables

    #region debug variables
    DEBUG_MODE = True

    DEBUG_PRINT_EVENTS_SENT_TO_UNITY = False #Mark this true to show events that we enque to send to Unity
    DEBUG_PRINT_EVENTS_RECEIVED_FROM_UNITY = False #Mark this true to show events that we have received from Unity
    DEBUG_TRANSLATE_PACKETS = False #Mark this true if you would like the packet names to be shown in English rather that Raw byte commands
    DEBUG_DISPLAY_JOY_AXIS = False #Mark this true to display all joystick axes values that are collected.
    DEBUG_SHOW_DRAX_BUTTONS = False #Displays the buttons that are pressed on each 
    DEBUG_LOG_DRAX = False #This will log the byte packets that we send and receive from our draxboard devices
    DEBUG_LOG_OMNIDONGLE = False #This will log the byte packets that we send and receive from our omnidongle device


    #endregion debug variables


    def __init__(self,):

        self.tcpManager = TCPManager(self)

        self.CONNECTED_OMNIDONGLE = None #Since there should only be one omnidongle in our machine, we will only search until this value is no longer None
        self.allConnectedDevices = [] #(DragonMasterDevice)
        self.playerStationDictionary = {}#Key: Parent USB Device Path (string) | Value: Player Station (PlayerStation)
        self.playerStationHashToParentDevicePath = {}#Key: Hash Value (uint) | Value: Parent USB Device Path (string)
        self.statusMessageReceived = False #As long as the variable is marked true before we check the status of the Unity application, it means that the game is functioning correctly and we will wait another minute
        

        self.searchingForDevices = False
        get_latest_firmware_version()
        #Start a thread to search for newly connected devices
        deviceAddedThread = threading.Thread(target=self.device_connected_thread,)
        deviceAddedThread.daemon = True
        deviceAddedThread.start()

        sleep(.1)
        print()
        self.search_for_devices()

        periodicallySearchForNewDevicesThread = threading.Thread(target=self.periodically_poll_for_devices_thread)
        periodicallySearchForNewDevicesThread.daemon = True
        periodicallySearchForNewDevicesThread.start()

        #Begins a thread that allows a user to enter debug commands into a terminal if there is one available. This will not work if run through the bash script
        if DragonMasterDeviceManager.DEBUG_MODE:
            print ()
            print ("DEBUG MODE IS ON")
            debugThread = threading.Thread(target=debug_command_thread, args=(self,))
            debugThread.daemon = True
            debugThread.start()
        
        
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
        while (True):
            sleep(10)
            if not self.searchingForDevices:
                try:
                    self.search_for_devices()
                except Exception as e:
                    print ("There was an error with our periodic polling")
                    print (e)
        return

    """
    There have been events where our Unity application has stopped responding. In this case the game will not shut itself down
    and therefore will never restart and try again. With this watchdog thread, if we do not receive a message from Unity after
    1 minute has passed, then we will assume it has stopped responding and attempt to shut it down.

    TODO: Make sure to add terminal message to shutdown the game if a status has not been received
    """
    def periodically_check_that_unity_is_still_running(self):
        while (not DragonMasterDeviceManager.KILL_APPLICATION_EVENT):
            sleep(DragonMasterDeviceManager.STATUS_MAX_SECONDS_TO_WAIT)
            if self.statusMessageReceived:
                self.statusMessageReceived = False
            else:
                print ("Do something here to shut off the game... it has not been responding")

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

        originalCountOfDevices = len(self.allConnectedDevices) #this is only used for debugging. can be ignored

        try:
            allConnectedJoysticks, allBaoLianJoysticks = DragonMasterDevice.get_all_connected_joystick_devices()
            allConnectedDraxboards = DragonMasterSerialDevice.get_all_connected_draxboard_elements()
            allConnectedCustomTG02Printers = DragonMasterDevice.get_all_connected_custom_tg02_printer_elements()
            allConnectedReliancePrinters = DragonMasterDevice.get_all_connected_reliance_printer_elements()
            allConnectedDBV400Elements, allConnectediVizionElements, allConnectedDBV500Elements = DragonMasterSerialDevice.get_all_connected_bill_acceptors()

            self.deviceContext = pyudev.Context() #we set our device context primarily to find the most up to date usb device paths
            
            #This is a special case. In which we will only look for omnidongle devices if there is not one that is already connected. We should only ever talk to one omnidongle device at a time 
            if self.CONNECTED_OMNIDONGLE == None:
                omnidongleElement = DragonMasterSerialDevice.get_omnidongle_comports()
                if omnidongleElement:
                    self.add_new_device(DragonMasterSerialDevice.Omnidongle(self), omnidongleElement)

            #Connects all instances of our Draxboard device
            for draxElement in allConnectedDraxboards:
                if draxElement and not self.device_manager_contains_draxboard(draxElement):
                    self.add_new_device(DragonMasterSerialDevice.Draxboard(self), draxElement)

            #Add our Ultimarc joysticks here
            for joystick in allConnectedJoysticks:
                if (joystick != None and not self.device_manager_contains_joystick(joystick)):
                    self.add_new_device(DragonMasterDevice.UltimarcJoystick(self), joystick)

            #Add our Bao Lian Joysticks here
            for joystick in allBaoLianJoysticks:
                if joystick != None and not self.device_manager_contains_joystick(joystick):
                    self.add_new_device(DragonMasterDevice.BaoLianJoystick(self), joystick)

            #Custom TG02 printers will be added here
            for printer in allConnectedCustomTG02Printers:
                if (printer != None and not self.device_manager_contains_printer(printer)):
                    self.add_new_device(DragonMasterDevice.CustomTG02(self), printer)

            #Reliance printers will be added here
            for printer in allConnectedReliancePrinters:
                if printer != None and not self.device_manager_contains_printer(printer):
                    self.add_new_device(DragonMasterDevice.ReliancePrinter(self), printer)

            #Add our DBV 400 Bill Acceptors here
            for dbv in allConnectedDBV400Elements:
                if dbv and not self.device_manager_contains_bill_acceptor(dbv):
                    self.add_new_device(DragonMasterSerialDevice.DBV400(self), dbv)

            #Add iVizion Bill Acceptors here
            for ivizion in allConnectediVizionElements:
                if ivizion and not self.device_manager_contains_bill_acceptor(ivizion):
                    self.add_new_device(DragonMasterSerialDevice.iVizion(self), ivizion)

            for dbv500 in allConnectedDBV500Elements:
                if dbv500 and not self.device_manager_contains_bill_acceptor(dbv500):
                    self.add_new_device(DragonMasterSerialDevice.DBV500(self), dbv500)

            
        except Exception as e:
            print ("There was an error while searching for devices.")
            print (e)

        if len(self.allConnectedDevices) != originalCountOfDevices:#For Debugging
            print('-' * 60)
            print ("Total Devices Connected: " + str(len(self.allConnectedDevices)))
        self.searchingForDevices = False
        return


    """
    Adds a new device to our device manager. This will fail to add a device if the device fails to
    start up appropriately

    @type deviceToAdd: DragonMasterDevice
    @param deviceToAdd: The device that we are going to add to our device manager
    """
    def add_new_device(self, deviceToAdd, deviceElementNode):
        if (self.allConnectedDevices.__contains__(deviceToAdd)):
            print ("Device was already added to our device manager. Please double check how we added a device twice")
            return
        if (deviceToAdd.start_device(deviceElementNode)):
            self.allConnectedDevices.append(deviceToAdd)
            self.add_new_device_to_player_station_dictionary(deviceToAdd)
            self.send_device_connected_event(deviceToAdd)
            
            print (deviceToAdd.to_string() + " was successfully ADDED to our device manager")
        else:
            deviceToAdd.disconnect_device()#We will run a disconnect device to ensure that we fully disconnect all processes that may be running in our device
            print ("Device Failed Start")
        return



    """
    If a device was connected this method should be called to notify our Unity application of which device was connected.
    An event from this method can include things that should be known about the device on start.
    
    For example, if a draxboard is connected, the Version number of the draxboard can be included in the device connected packet. The first byte of data should always be the device ID though.
    This just clarifies what type of device we are connecting (i.e. Draxboard, Joystick, BA, etc... the more general idea of the device)

    @type deviceThatWasAdded: DragonMasterDevice
    @param deviceThatWasAdded: The newly connected device.
    """
    def send_device_connected_event(self, deviceThatWasAdded):
        deviceData = []
        if isinstance(deviceThatWasAdded, DragonMasterDevice.Joystick):
            deviceData.append(DragonMasterDeviceManager.JOYSTICK_ID)#DeviceTypeID
            deviceData.append(deviceThatWasAdded.get_joystick_id())#Byte that identifies the type of joystick that is connected for our Unity application
            pass
        elif isinstance(deviceThatWasAdded, DragonMasterDevice.Printer):
            deviceData.append(DragonMasterDeviceManager.PRINTER_ID)#DeviceTypeID
            deviceData.append(deviceThatWasAdded.get_printer_id())
            pass
        elif isinstance(deviceThatWasAdded, DragonMasterSerialDevice.Draxboard):
            deviceData.append(DragonMasterDeviceManager.DRAX_ID)#DeviceTypeID
            #TODO: Think about how these values below can be guaranteed to be collected before we get to this point
            deviceData.append(deviceThatWasAdded.versionNumberHigh)
            deviceData.append(deviceThatWasAdded.versionNumberLow)
            deviceData.append(deviceThatWasAdded.playerStationNumber)
            pass
        elif isinstance(deviceThatWasAdded, DragonMasterSerialDevice.DBV400):
            deviceData.append(DragonMasterDeviceManager.BILL_ACCEPTOR_ID)#DeviceTypeID
            deviceData.append(deviceThatWasAdded.get_ba_type())#The Bill Acceptor Type. In the future, we plan on adding new types of Bill Acceptors
            deviceData += deviceThatWasAdded.dbvVersionBytes #append the version of our DBV-400
            pass
        elif isinstance(deviceThatWasAdded, DragonMasterSerialDevice.Omnidongle):
            deviceData.append(DragonMasterDeviceManager.OMNI_EVENT)#DeviceTypeID
            pass
        
        self.add_event_to_send(DragonMasterDeviceManager.DEVICE_CONNECTED, deviceData, self.get_player_station_hash_for_device(deviceThatWasAdded))
        return
        # print ("Device Added ID: " + str(deviceTypeID))

    """
    If a device was removed we should call this method, so that we appropriately notify our Unity Applcation

    @type deviceThatWasRemoved: DragonMasterDevice
    @param deviceThatWasRemoved: The disconnected device
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
    Adds a device to the player station dictionary and our device list

    @type deviceToAdd: DragonMasterDevice
    @param deviceToAdd: The device that we will add to our DragonMasterDeviceManager
    """
    def add_new_device_to_player_station_dictionary(self, deviceToAdd):
        if deviceToAdd.deviceParentPath == None:
                if not isinstance(deviceToAdd, DragonMasterSerialDevice.Omnidongle):#The omnidongle is the only device where we don't care what the parent path is set to
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
                self.playerStationDictionary[deviceToAdd.deviceParentPath].persistedPlayerStationHash = deviceToAdd.playerStationHash
                self.playerStationHashToParentDevicePath[deviceToAdd.playerStationHash] = deviceToAdd.deviceParentPath

            # print (deviceToAdd.deviceParentPath)
            #print (self.playerStationDictionary[deviceToAdd.deviceParentPath].to_string())

            if previouslyConnectedDevice != None:
                print ("Warning: There are two or more of the same devices connected to our our player station")
                print ("Previously Connected: " + previouslyConnectedDevice.to_string() + " Newly Added: " + deviceToAdd.to_string())

        return

    """
    This method will remove a device from our device manager. This will also process our disconnect command in the device
    that is passed through to ensure that we are properly disconnected from the device manager

    @type deviceToRemove: DragonMasterDevice
    @param deviceToRemove: The device that we will remove from our DragonMasterDeviceManager
    """
    def remove_device(self, deviceToRemove):
        if deviceToRemove == None:
            return

        if self.allConnectedDevices.__contains__(deviceToRemove):
            deviceToRemove.disconnect_device()
            self.remove_device_from_player_station_dictionary(deviceToRemove)
            self.allConnectedDevices.remove(deviceToRemove)
            self.send_device_disconnected_event(deviceToRemove)
            print (deviceToRemove.to_string() + " was successfully REMOVED")
        else:
            if not isinstance(deviceToRemove, DragonMasterSerialDevice.ReliancePrinterSerial):#reliance serial is the one excpetion where we don't remove it normally
                print (deviceToRemove.to_string() + " was not found in our device list. Perhaps it was already removed")


        return

    """
    Safely removes a device from our player station device dictionary.

    @type deviceToRemove: DragonMasterDevice
    @param deviceToRemove: device object that will be removed from our DragonMasterDeviceManager deviceList
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
    As long as there was a Draxboard this will return the associated player station hash that is tied to the draxboard device. If there has not been
    a draxboard connected to this player station, it will simply return a 0 value. This is defined as invalid in most functions in our unity application

    @type device: DragonMasterDevice
    @param device: a DragonMasterDevice that will return a playerstation hash if one is valid
    """
    def get_player_station_hash_for_device(self, device):
        playerStationParentPath = device.deviceParentPath

        if playerStationParentPath == None or playerStationParentPath not in self.playerStationDictionary:
            return 0

        playerStation = self.playerStationDictionary[playerStationParentPath]
        
        return playerStation.persistedPlayerStationHash

    """
    Returns the usb path, using the playerstation hash

    @type playerStationHash: uint
    @param playerStationHash: The hash of the playerplayerStation

    @rtype PlayerStationContainer
    @returns: a PlayerStationContainer object associated with the player station hash that is passed in. None if there is no associated player station container to go along with the 
    hash that is passed in
    """
    def get_parent_usb_path_from_player_station_hash(self, playerStationHash):
        if playerStationHash in self.playerStationHashToParentDevicePath:
            return self.playerStationHashToParentDevicePath[playerStationHash]
        return None

    #endregion Device Management


    #region TCP Received Data Events

    """
    This method will be called to interpret all the packets that we receive from our Unity application

    @type eventMessage: bytes
    @param eventMessage: A list of bytes that will decipher what our DeviceManager should do
    """
    def interpret_and_process_event_from_unity(self, eventMessage):
        if eventMessage == None or len(eventMessage) <= 0:
            print ("The event message that was passed in was empty...")
            return

        if DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_RECEIVED_FROM_UNITY:
            print ("Message From Unity: " + eventMessage.hex())

        eventCommandByte = eventMessage[0]#This is the byte that identifies what type of packet we are using

        if eventCommandByte == DragonMasterDeviceManager.RETRIEVE_CONNECTED_DEVICES:
            self.on_retrieve_connected_devices()
            return
        elif eventCommandByte == DragonMasterDeviceManager.STATUS_FROM_UNITY:
            self.on_status_from_unity()
            return
        elif eventCommandByte == DragonMasterDeviceManager.OMNI_EVENT:
            self.on_omnidongle_event_received(eventMessage)
            return
        elif eventCommandByte == DragonMasterDeviceManager.KILL_APPLICATION_EVENT:
            DragonMasterDeviceManager.KILL_DEVICE_MANAGER_APPLICATION = True #This will kill the main thread at the next available time. So processes may still run for a second
            return
        
        #All event functions below this point need to have a playerStationHash as they are specific to a specific player station
        if len(eventMessage) < 5:
            print (eventMessage.hex())
            print ("The event message was too short...")
            return 
        # playerStationHash = convert_byte_array_to_value(eventMessage[1:4])
        playerStationHash = int.from_bytes(eventMessage[1:5], byteorder='big')
        #General Event Messages
        
        #Drax Outputs
        if eventCommandByte == DragonMasterDeviceManager.DRAX_HARD_METER_EVENT:
            self.on_drax_hard_meter_event(playerStationHash, eventMessage[5:])
            return
        elif eventCommandByte == DragonMasterDeviceManager.DRAX_OUTPUT_EVENT:
            self.on_drax_output_event(playerStationHash, eventMessage[5:])
            return
        elif eventCommandByte == DragonMasterDeviceManager.DRAX_OUTPUT_BIT_ENABLE_EVENT:
            self.on_drax_output_bit_enable_event(playerStationHash, eventMessage[5:])
            return
        elif eventCommandByte == DragonMasterDeviceManager.DRAX_OUTPUT_BIT_DISABLE_EVENT:
            self.on_drax_output_bit_disable_event(playerStationHash, eventMessage[5:])
            return

        #Printer Outputs
        elif eventCommandByte == DragonMasterDeviceManager.PRINTER_CASHOUT_TICKET:
            self.on_print_cashout_ticket_event(playerStationHash, eventMessage[5:])
            return
        elif eventCommandByte == DragonMasterDeviceManager.PRINTER_AUDIT_TICKET:
            self.on_print_audit_ticket_event(playerStationHash, eventMessage[5:])
            return
        elif eventCommandByte == DragonMasterDeviceManager.PRINTER_CODEX_TICKET:
            self.on_print_codex_ticket_event(playerStationHash, eventMessage[5:])
            return
        elif eventCommandByte == DragonMasterDeviceManager.PRINTER_TEST_TICKET:
            self.on_print_test_ticket_event(playerStationHash)
            return
        elif eventCommandByte == DragonMasterDeviceManager.PRINTER_STATE_EVENT:
            self.on_printer_state_request(playerStationHash)
            
        #Bill Acceptor Outputs
        elif eventCommandByte == DragonMasterDeviceManager.BA_IDLE_EVENT:
            self.on_ba_idle_event(playerStationHash)
            return
        elif eventCommandByte == DragonMasterDeviceManager.BA_INHIBIT_EVENT:
            self.on_ba_inhibit_event(playerStationHash)
            return
        elif eventCommandByte == DragonMasterDeviceManager.BA_RESET_EVENT:
            self.on_ba_reset_event(playerStationHash)
            return
        elif eventCommandByte == DragonMasterDeviceManager.BA_ACCEPT_BILL_EVENT:
            self.on_ba_stack_bill_event(playerStationHash)
            return
        elif eventCommandByte == DragonMasterDeviceManager.BA_REJECT_BILL_EVENT:
            self.on_ba_reject_bill_event(playerStationHash)
            return
        elif eventCommandByte == DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT:
            self.on_ba_request_state_event(playerStationHash)
            return
        else:
            print (str(eventCommandByte) + " has not been set up")

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

    @type eventMessage: bytes
    @param eventMessage: a list of bytes that will be sent to our omnidongle device
    """
    def on_omnidongle_event_received(self, eventMessage):
        if self.CONNECTED_OMNIDONGLE != None:

            omnidevice = self.CONNECTED_OMNIDONGLE
            omnidevice.add_event_to_queue(omnidevice.send_data_to_omnidongle_wait_for_response, eventMessage[1:])
        return

    #region draxboard tcp events

    """

    """
    def on_drax_hard_meter_event(self, playerStationHash, eventData):
        draxboard = self.get_draxboard_from_player_station_hash(playerStationHash)
        if draxboard == None:
            return
        if len(eventData) < 2:
            return
        
        draxboard.add_event_to_queue(draxboard.increment_meter_ticks, eventData[0], (eventData[1] << 8) + eventData[2])        
        return

    """
    This method should be called upon receiving an event from unity to toggle the output of the Draxboard

    @type playerStationHash: uint
    @param playerStationHash: The player station hash that indicates which draxboard will have its outputs toggled

    @type eventData: bytes
    @param eventData: list of bytes that indicate which outputs will be toggled in our Draxboard
    """
    def on_drax_output_event(self, playerStationHash, eventData):
        draxboard = self.get_draxboard_from_player_station_hash(playerStationHash)
        if draxboard == None:
            return
        if len(eventData) < 2:
            return
        draxboard.add_event_to_queue(draxboard.toggle_output_state_of_drax, (eventData[0] << 8) + eventData[1], 0)
        return

    """
    If we want to enable one single bit we can call this method to set that bit to true in the Drax

    @type playerStationHash: uint
    @param playerStationHash: The player station hash that indicates which draxboard will outputs toggled

    @type eventData: bytes
    @param eventData: The data that will indicate the bit that we will toggle on
    """
    def on_drax_output_bit_enable_event(self, playerStationHash, eventData):
        draxboard = self.get_draxboard_from_player_station_hash(playerStationHash)
        if draxboard == None:
            return
        if len(eventData) < 2:
            return
        draxboard.add_event_to_queue(draxboard.toggle_output_state_of_drax, (eventData[0] << 8) + eventData[1], 1)

        return

    """
    If we want to disable one single output bit in our draxboard, we can call this method.

    @type playerStationHash: uint
    @param playerStationHash: 

    @type eventData: bytes
    @param eventData:
    """
    def on_drax_output_bit_disable_event(self, playerStationHash, eventData):
        draxboard = self.get_draxboard_from_player_station_hash(playerStationHash)
        if draxboard == None:
            return
        if not len(eventData):
            return
        
        draxboard.add_event_to_queue(draxboard.toggle_output_state_of_drax, (eventData[0] << 8) + eventData[1], 2)
        return
    #endregion draxboard tcp events

    #region bill acceptor tcp events
    """
    This method should be called when a bill acceptor idle event is triggered from Unity
    """
    def on_ba_idle_event(self, playerStationHash):
        billAcceptor = self.get_bill_acceptor_from_player_station_hash(playerStationHash)

        if billAcceptor == None:
            return
        
        billAcceptor.add_event_to_queue(billAcceptor.idle_dbv)
        return

    """
    This method should be called when a bill acceptor inhibit event is called from Unity
    """
    def on_ba_inhibit_event(self, playerStationHash):
        billAcceptor = self.get_bill_acceptor_from_player_station_hash(playerStationHash)

        if billAcceptor == None:
            return
        
        billAcceptor.add_event_to_queue(billAcceptor.inhibit_dbv)
        return

    """
    This method should be called when a bill acceptor reset event is called from Unity
    """
    def on_ba_reset_event(self, playerStationHash):
        billAcceptor = self.get_bill_acceptor_from_player_station_hash(playerStationHash)

        if billAcceptor == None:
            return

        billAcceptor.add_event_to_queue(billAcceptor.reset_dbv)
        return

    """
    If there is a bill in pending this message should be sent to our bill acceptor to appropriately accept it
    """
    def on_ba_stack_bill_event(self, playerStationHash):
        billAcceptor = self.get_bill_acceptor_from_player_station_hash(playerStationHash)
        
        if billAcceptor == None:
            return

        billAcceptor.add_event_to_queue(billAcceptor.stack_bill)
        return

    """
    If there is a bill pending in our bill acceptor this should be called to properly reject the bill
    """
    def on_ba_reject_bill_event(self, playerStationHash):
        billAcceptor = self.get_bill_acceptor_from_player_station_hash(playerStationHash)
        
        if billAcceptor == None:
            return

        billAcceptor.add_event_to_queue(billAcceptor.reject_bill)
        return

    def on_ba_request_state_event(self, playerStationHash):
        billAcceptor = self.get_bill_acceptor_from_player_station_hash(playerStationHash)

        if billAcceptor == None:
            return
        billAcceptor.send_event_message(DragonMasterDeviceManager.BA_BILL_STATE_UPDATE_EVENT, billAcceptor.State.to_bytes(2, 'big'))
    #endregion bill acceptor tcp events

    #region printer tcp events
    """
    Method that should be called to print out a cashout ticket
    """
    def on_print_cashout_ticket_event(self, playerStationHash, eventData):
        printerDevice = self.get_printer_from_player_station_hash(playerStationHash)

        if printerDevice == None:
            return

        printerDevice.add_event_to_queue(printerDevice.print_voucher_ticket, DragonMasterDeviceManager.PRINTER_CASHOUT_TICKET, eventData)
        return

    """
    Method that should be called to print out a codex ticket
    """
    def on_print_codex_ticket_event(self, playerStationHash, eventData):
        printerDevice = self.get_printer_from_player_station_hash(playerStationHash)

        if printerDevice == None:
            return

        printerDevice.add_event_to_queue(printerDevice.print_codex_ticket, str(eventData))
        return

    """
    Method that should be called to print out an audit ticket
    """
    def on_print_audit_ticket_event(self, playerStationHash, eventData):
        printerDevice = self.get_printer_from_player_station_hash(playerStationHash)
        if printerDevice == None:
            return

        printerDevice.add_event_to_queue(printerDevice.print_audit_ticket, str(eventData))
        return

    """
    Method that should be called when attempting to print out a test ticket from our 
    """
    def on_print_test_ticket_event(self, playerStationHash):
        printerDevice = self.get_printer_from_player_station_hash(playerStationHash)
        if printerDevice == None:
            return

        printerDevice.add_event_to_queue(printerDevice.print_voucher_ticket, DragonMasterDeviceManager.PRINTER_TEST_TICKET, []) #Always want to print our voucher ticket with a value of 0 when it is a test ticket
        return

    """
    This will send an event to our Unity application to return the current state of our printer device
    """
    def on_printer_state_request(self, playerStationHash):
        printerDevice = self.get_printer_from_player_station_hash(playerStationHash)
        if printerDevice == None:
            return

        printerDevice.add_printer_state_to_send_queue()

    """
    This method should be called whenever a reprint is requested from our Unity application
    """
    def on_print_reprint_ticket_event(self, playerStationHash, eventData):
        printerDevice = self.get_printer_from_player_station_hash(playerStationHash)

        if printerDevice == None:
            return

        printerDevice.add_event_to_queue(printerDevice.print_voucher_ticket, DragonMasterDeviceManager.PRINTER_REPRINT_TICKET,eventData)
        return

    #endregion printer tcp events

    #endregion TCP Received Data Events

    #region TCP Communication
    """
    Queue up an event to send to our Unity Application. This should always be of the type
    byteArray

    @type eventID: byte
    @param eventID - the event id of the packet. This is the byte that defines the action that will be taken upon being received by our unity application
    
    @type eventData: list
    @param eventData - any required data for the packet we are sending

    @type playerStationHash: uint
    @param playerStationHash - if value is left as none it will not be added to the packet. But devices that are associated with a specific player station
    """
    def add_event_to_send(self, eventID, eventData, playerStationHash = None):
        messageToSend = []
        messageToSend.append(eventID)
        if playerStationHash != None:
            messageToSend += int.to_bytes(playerStationHash, 4, byteorder='big')
        messageToSend += eventData
        
        self.tcpManager.add_event_to_send(messageToSend)
        return

    """
    Upon receiving an event from our Unity Application, we will process the command through this method

    Packets that are received will contain the following layout:
    [Function, playerStationID(optional), data....]

    @type eventList: list
    @param eventList: list of events that have been received from our unity application and will be interpreted
    """
    def execute_received_event(self, eventList):
        if (len(eventList) <= 0):
            return

        for event in eventList:
            if not DragonMasterDeviceManager.KILL_DEVICE_MANAGER_APPLICATION:
                self.interpret_and_process_event_from_unity(event)
            pass
        return
    #endregion TCP Communication
    pass

    #region get device methods
    """
    Returns a draxboard using the player station hash

    @type playerStationHash: uint
    @param playerStationHash: the player station hash of the 

    @rtype: Draxboard(DragonMasterDevice)
    @returns: the connected draxboard
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
    def device_manager_contains_bill_acceptor(self, dbvElement):
        for dev in self.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
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
    NOTE: This does not act as an event for new joystick values, that is handled in the Joystick class. This method is used
    to collect joystick values if they are different the next time we are ready to send another TCP message to our Unity Application. This is simply
    to prevent having 5-10 messages per joystick every time we send a new message
    """
    def check_for_joystick_events(self):
        for key in self.playerStationDictionary:
            if self.playerStationDictionary[key].connectedJoystick != None:
                self.playerStationDictionary[key].connectedJoystick.send_updated_joystick_to_unity_application()
        return


"""
This class acts as a container of all the devices that are connected to this player station

TODO: Add a way to store multiple devices in the event that there are perhaps 2 joysticks connected to the same player station
This has been an issue in the past where we will try to remove a device
"""
class PlayerStationContainer:
    
    def __init__(self):
        #Whenever we connect to a new draxboard, this value will be set. As long as the drax is reconnected to the same usb port, this path should remain the same
        self.persistedPlayerStationHash = 0
        #Connected Draxboard. 
        self.connectedDraxboard = None
        #The connected bill acceptor that is associated with this player staiton
        self.connectedBillAcceptor = None
        #The connected joystick that is associated with this player station
        self.connectedJoystick = None
        #The connected printer that is associated with this player staiton
        self.connectedPrinter = None    

    """
    to_string mesage that displays all the devices that are connected to the player station. If FullStation is set to true
    this will write out MISSING for devices that are not present in this station
    """
    def to_string(self, fullStation = False):
        playerStationString = '-' * 60
        if self.persistedPlayerStationHash != 0:
            print ("Station Hash: " + str(self.persistedPlayerStationHash))
        else:
            print ("NO DRAXBOARD HAS BEEN ENUMERATED FOR THIS PLAYER STATION")
        if self.connectedJoystick:
            playerStationString += '\nJOY   |' + self.connectedJoystick.to_string()
        elif fullStation:
            playerStationString += "\nJOY   |MISSING" 
        if self.connectedDraxboard:
            playerStationString += '\nDRAX  |' + self.connectedDraxboard.to_string()
        elif fullStation:
            playerStationString += "\nDRAX  |MISSING" 
        if self.connectedPrinter:
            playerStationString += '\nPRINT |' + self.connectedPrinter.to_string()
        elif fullStation:
            playerStationString += "\nPRINT |MISSING" 
        if self.connectedBillAcceptor:
            playerStationString += '\nDBV   |' + self.connectedBillAcceptor.to_string()
        elif fullStation:
            playerStationString += "\nDBV   |MISSING" 
        playerStationString += '\n' + '-' * 60
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

        self.start_new_socket_receive_thread()
        self.start_new_socket_send_thread()
        self.deviceManager = deviceManager
        


    """
    This enqueues an event to send to our unity application

    @type messageToQueueForSend: bytes
    @param messageToQueuForSend: This is the byte packet that we want to enqueue and deliver to Unity as soon as possible
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

    Keep in mind that this method will append a byte at the beginning of the packet so that Unity can appropriately read the size of the packet

    NOTE: Adding the size should only be done in this step, You should enque packets as you would like Unity to read them, the size packets will be stripped
    once our Unity application has appropriately read them
    For example [0x01, 0x03] would indicate that an omnidongle device was connected
    Python sends the packets as [0x02, 0x01, 0x03] to say that there are two bytes to read for this packet
    Unity side will take this information and strip the 0x02 when processing the packet. So unity will see it as [0x01, 0x03]
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

                if DragonMasterDeviceManager.KILL_DEVICE_MANAGER_APPLICATION:
                    #Messages will not be sent if application is queued to end
                    print ("Killing Send thread due to Kill Application Event")
                    return
                
                if conn != None:
                    bytesToSend = []
                    while not self.tcpEventQueue.empty():
                        eventToAdd = self.tcpEventQueue.get()
                        eventToAdd.insert(0, len(eventToAdd))
                        # eventToAdd.append(self.calculate_checksum_of_packet(eventToAdd))

                        bytesToSend = bytesToSend + eventToAdd
                        
                        if (DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_SENT_TO_UNITY):
                            print ("MSGOUT: " + str(eventToAdd))
                        eventToAdd.clear()
                        
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

            # sleep(.01)
            totalCount += 1
            pass
        socketSend.close()
        self.start_new_socket_send_thread()
        return


    """
    This method will be called to receive 

    Similar to what was mentioned in the send function, when processing the received packets we will strip the size bytes before processing 
    our packets through the DeviceManager. 
    NOTE: As opposed to the above formula where we only append one byte to the beginning of our packet to indicate the size, Unity events contain 2 bytes at the start
    due to Unity events (particularly printer events) can exceed 256 bytes. 
    """
    def socket_receive(self):
        totalCount = 0
        buff = None
        while (totalCount < TCPManager.MAX_THREADING_COUNT):
            try:
                socketRead = socket.socket()

                fullResponse = bytearray()
                socketRead.connect((self.HOST_ADDRESS, self.RECEIVE_PORT))
                
                buff = socketRead.recv(1024)
                while buff:
                    fullResponse += buff
                    buff = socketRead.recv(1024)

                if (len(fullResponse) > 0):
                    self.deviceManager.execute_received_event(self.separate_events_received_into_list(fullResponse))
                socketRead.close()
            except Exception as e:
                socketRead.close()
                
            sleep(1.0 / 30.0)
            totalCount += 1
            pass

        socketRead.close()
        self.start_new_socket_receive_thread()
        return

    """
    Separates the events into a list. Upon receiving a packet, it is typically sent as one long bytearray.
    this will break up our events into a list of byte arrays that can be read as events. We will remove the 
    byte that shows the size of the packet. 

    @type fullEventData: bytes
    @param fullEventData: the complete packet that is received from our TCP buffer. This may contain multiple events within the packet
    """
    def separate_events_received_into_list(self, fullEventData):
        if fullEventData == None: 
            return []
        
        eventList = []
        startIndex = 0
        endIndex = 0
        sizeOfPacket = 0
        while startIndex < len(fullEventData):
            sizeOfPacket = fullEventData[startIndex] << 8
            sizeOfPacket += fullEventData[startIndex + 1]
            startIndex += 2 #To be clear, the first two bytes represent the size of the packet, which we will strip when processing our data packets
            endIndex = startIndex + sizeOfPacket

            eventData = fullEventData[startIndex:endIndex]
            eventList.append(eventData)
            startIndex = endIndex
            pass
        return eventList
    pass

    """
    This method will calculate the checksum value that should be appended to the packet that we are delivering to our Unity Application
    """
    def calculate_checksum_of_packet(self, packetBeforeChecksumByte):
        checkSumValue = 0
        for val in packetBeforeChecksumByte:
            checkSumValue ^= val
        return checkSumValue


#region firmware update methods
"""
Returns the current firmware of the DBV-400. The version that is collected here should be applied to all connected DBV-400 devices
"""
def get_latest_firmware_version():
    try:
        binFile = open(DragonMasterSerialDevice.DBV400.FIRMWARE_UPDATE_FILE_PATH, 'rb')
        
        DragonMasterSerialDevice.DBV400.DOWNLOAD_PACKET_DATA = binFile.read()
        verSearchString = "DBV-400-SU USA ID008 "
        packetDataAsString = str(DragonMasterSerialDevice.DBV400.DOWNLOAD_PACKET_DATA)
        x = re.search(verSearchString, packetDataAsString)
        if x:
            DragonMasterSerialDevice.DBV400.LATEST_DBV_FIRMWARE = packetDataAsString[x.span()[1]:x.span()[1] + 15]
            print (DragonMasterSerialDevice.DBV400.LATEST_DBV_FIRMWARE)
    except Exception as e:
        print ("There was a problem retrieving our DBV Firmware Version")
        print (e)

    return

#endregion firmware update methods

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



"""
This thread will allow testers to enter debug commands

Once the thread has exited there is no way to restart the debug thread until the application is reset

@type deviceManager: DragonMasterDeviceManager
@param deviceManager: The dragon master device manager object that we are debugging
"""
def debug_command_thread(deviceManager):
    while(True):
        commandToRead = input("Enter Command: ")
        if commandToRead != None:
            exitDebugThread = interpret_debug_command(commandToRead,deviceManager)
            if exitDebugThread:
                return


"""
Pass in the debug command that was entered into the terminal to here and it will perform the appropriate action if there is a valid function associated
with it

@type commandToRead: str
@param commandToRead: the command that was entered by our user from the terminal

@type deviceManager: DragonMasterDeviceManager
@param deviceManager: The DragonMasterDeviceManager
"""
def interpret_debug_command(commandToRead, deviceManager):
    # debug command format: COMPORT COMMAND
    # ex: 0 RESET #This would correlate to Serial Port 0
    
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
        return True
    elif command == "test":
        debug_test_event(deviceManager)
        return
    elif command == "status":
        debug_status_message(deviceManager)
        return
    elif command == "version":
        print ('-' * 60)
        print ("Python Ver: " + sys.version)
        print("Device Manager Ver: v" + DragonMasterDeviceManager.VERSION)
        print ('-' * 60)
        return
    elif command == "msgin":
        DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_RECEIVED_FROM_UNITY = not DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_RECEIVED_FROM_UNITY
        print ("DISPLAY TCP READ EVENTS: " + str(DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_RECEIVED_FROM_UNITY))
        return
    elif command == "msgout":
        DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_SENT_TO_UNITY = not DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_SENT_TO_UNITY
        print ("DISPLAY TCP SEND EVENTS: " + str(DragonMasterDeviceManager.DEBUG_PRINT_EVENTS_SENT_TO_UNITY))
        return
    elif command == "msgtrans":
        DragonMasterDeviceManager.DEBUG_TRANSLATE_PACKETS = not DragonMasterDeviceManager.DEBUG_TRANSLATE_PACKETS
        print ("TRANSLATE TCP MESSAGES: " + str(DragonMasterDeviceManager.DEBUG_TRANSLATE_PACKETS))
        return
    #Joystick DEBUG
    elif command == "logjoystick":
        DragonMasterDeviceManager.DEBUG_DISPLAY_JOY_AXIS = not DragonMasterDeviceManager.DEBUG_DISPLAY_JOY_AXIS
        return
    #DRAX DEBUG
    elif command == "displaydraxbutton":
        DragonMasterDeviceManager.DEBUG_SHOW_DRAX_BUTTONS = not DragonMasterDeviceManager.DEBUG_SHOW_DRAX_BUTTONS
        if (DragonMasterDeviceManager.DEBUG_SHOW_DRAX_BUTTONS):
            print ("Printing Drax Buttons: ON")
        else:
            print ("Printing Drax Buttons: OFF")
        return
    elif command == "logdrax":
        print ("This is a command, but it is not implemented right now...")
        return
    elif command == "flashdrax":
        if len(commandSplit) >= 2:
            debug_flash_draxboards(deviceManager, int(commandSplit[1]))
        else:
            debug_flash_draxboards(deviceManager)
        return
    elif command == "bitenable":
        if len(commandSplit) >= 3:
            debug_bitenable_drax(deviceManager, int(commandSplit[1]), int(commandSplit[2]))
            return
        elif len(commandSplit) >= 2:
            debug_bitenable_drax(deviceManager, int(commandSplit[1]))
            return
        else:
            debug_bitenable_drax(deviceManager)
            return
    elif command == "bitdisable":
        if len(commandSplit) >= 3:
            debug_bitdisable_drax(deviceManager, int(commandSplit[1]), int(commandSplit[2]))
            return
        elif len(commandSplit) >= 2:
            debug_bitdisable_drax(deviceManager, int(commandSplit[1]))
            return
        else:
            debug_bitdisable_drax(deviceManager)
            debug_bitdisable_drax(deviceManager, 1)
            debug_bitdisable_drax(deviceManager, 2)
            return
    elif command == "draxout":
        if len(commandSplit) >= 3:
            debug_draxout(deviceManager, int(commandSplit[1]), int(commandSplit[2]))
            return
        elif len(commandSplit) >= 2:
            debug_draxout(deviceManager, int(commandSplit[1]))
            return
        else:
            debug_draxout(deviceManager)
            return
    elif command == "meter":
        if len(commandSplit) >= 4:
            debug_meter_increment(deviceManager, int(commandSplit[1]), int(commandSplit[2]), int(commandSplit[3]))
        elif len(commandSplit) >= 3:
            debug_meter_increment(deviceManager, int(commandSplit[1]), int(commandSplit[2]))
            return
        elif len(commandSplit) >= 2:
            debug_meter_increment(deviceManager, int(commandSplit[1]))
            return
        else:
            debug_meter_increment(deviceManager)
            return
    elif command == "requestinput":
        if len(commandSplit) >= 2:
            debug_request_drax_input(deviceManager, int(commandSplit[1]))
        else:
            debug_request_drax_input(deviceManager)

    #PRINT DEBUG
    elif command == "vprint":
        if len(commandSplit) >= 2:
            debug_print_voucher_ticket(deviceManager, int(commandSplit[1]))
        else:
            debug_print_voucher_ticket(deviceManager)
        return
    elif command == "rprint":
        if len(commandSplit) >= 2:
            debug_print_reprint_ticket(deviceManager, int(commandSplit[1]))
        else:
            debug_print_reprint_ticket(deviceManager)
        return
    elif command == 'tprint':
        if len(commandSplit) >= 2:
            debug_print_test_ticket(deviceManager, int(commandSplit[1]))
        else:
            debug_print_test_ticket(deviceManager)
        return
    elif command == 'cprint':
        if len(commandSplit) >= 2:
            debug_print_codex_ticket(deviceManager, int(commandSplit[1]))
        else:
            debug_print_codex_ticket(deviceManager)
        return
    elif command == 'aprint':
        if len(commandSplit) >= 2:
            debug_print_audit_ticket(deviceManager, int(commandSplit[1]))
        else:
            debug_print_audit_ticket(deviceManager)
        return
    #BILL ACCEPTOR DEBUG
    elif command == "reset":
        if len(commandSplit) >= 2:
            debug_reset_dbv(deviceManager, commandSplit[1])
        else:
            debug_reset_dbv(deviceManager)
        return
    elif command == "idle":
        if len(commandSplit) >= 2:
            debug_idle_dbv(deviceManager, commandSplit[1])
        else:
            debug_idle_dbv(deviceManager)
        return
    elif command == "inhibit":
        if len(commandSplit) >= 2:
            debug_inhibit_dbv(deviceManager, commandSplit[1])
        else:
            debug_inhibit_dbv(deviceManager)
        return
    elif command == "stack":
        if len(commandSplit) >= 2:
            debug_accept_bill_dbv(deviceManager, commandSplit[1])
        else:
            debug_accept_bill_dbv(deviceManager)
        return
    elif command == "reject":
        if len(commandSplit) >= 2:
            debug_reject_bill_dbv(deviceManager, commandSplit[1])
        else:
            debug_reject_bill_dbv(deviceManager)
        return
    elif command == "toggleidle":
        if len(commandSplit) >=4:
            debug_toggle_dbv_idle(deviceManager, int(commandSplit[1]), float(commandSplit[2]), int(commandSplit[3]))
        elif len(commandSplit) >=3:
            debug_toggle_dbv_idle(deviceManager, int(commandSplit[1]), float(commandSplit[2]))
        elif len(commandSplit) >=2:
            debug_toggle_dbv_idle(deviceManager, int(commandSplit[1]))
        elif len(commandSplit) >=1:
            debug_toggle_dbv_idle(deviceManager)
        return
    elif command == "state":
        if len(commandSplit) >= 2:
            debug_status_dbv(deviceManager, commandSplit[1])
        else:
            debug_status_dbv(deviceManager)
        return
    elif command == "dbvdownload":
        if len(commandSplit) >= 2:
            debug_firmware_updated_dbv(deviceManager, commandSplit[1])
        else:
            debug_firmware_updated_dbv(deviceManager)
        return
    elif command == "dbvversion":
        if len(commandSplit) >= 2:
            debug_print_dbv_version(deviceManager, commandSplit[1])
        else:
            debug_print_dbv_version(deviceManager)
        return
    elif command == "fuck":
        print ("I'm sorry you're having a rough time. Please don't be so hard on yourself. I'm sure you'll get through it!")
    else:
        print ("'" + command + "' is not a valid command... type 'help' to see all available commands")
    return
    

"""
Prints out the current state of every device that is currently connected to our machine
"""
def debug_status_message(deviceManager):
    print ('=' * 60)
    print ()
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
        print (deviceManager.playerStationDictionary[key].to_string(True))
    print ("TOTAL DEV: " + str(len(deviceManager.allConnectedDevices)))
    
    return

"""
Function to test our threaded device events. Sends 3 queued events all the connected devices that we have
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
    print ("FORMAT FOR ALL DEVICE COMMANDS: 'command data... playerStationHash'")
    print ("NOTE: If you only enter the command it will perform a default function to ALL devices that correspond to that function")
    print ("NOTE: By default, we will send commands to all playerstations unless you specifically put the hash at the end of the command")
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
    print ("'displaydraxbutton' - shows the button presses/releases on the draxboard")
    print ("'bitenable - enter 0-15 to enable a specific output on our Draxboard (data=[bitToToggle])")
    print ("'bitdisable - enter 0-15 to disable a specific output on our Draxboard (data=[bitToToggle])")
    print ("'draxout' - enter a ushort value and the draxboard output will be set to that state (data=[ushortOutputState])")
    print ("'meter' - increments the hard meters attached to our draxboards (data=[meterID, #ofTicks])")
    print ("'flashdrax' - This will trigger the ticket light to turn on and off and display which station it is applied to (data=[])")
    print ('-' * 60)
    print ("**JOYSTICK COMMANDS**")
    print ("'logjoystick' - This will print out all joystick values that are gathered. To turn off reenter the command (data=[])")
    print ("    NOTE: 'logjoystick' can get very spammy. simply type display joy even if its not all on one line and it will register")
    print ('-' * 60)
    print ("**Printer Commands**")
    print ("'vprint' - Prints a sample voucher ticket (data=[])")
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
    print ("'toggleidle' - sends a command to toggle back and forth between idle and inhibit (data=[#ofToggles, secondsBetwenToggles]")
    print ("'dbvdownload' - runs a command to update the firmware of the connected bill acceptor")
    print ("'dbvversion' - runs a command to print the dbv version that is read in from the device")
    print ('-' * 60)
    return

#region debug drax functions

"""
Sends a pulse to the Draxboards ticket light to indicate which station goes with which hash code
"""
def debug_flash_draxboards(deviceManager, playerStationHash = -1):
    if (playerStationHash < 0):
        for pStation in deviceManager.playerStationDictionary.values():
            actually_flash_drax(pStation)
    else:
        if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
            print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
            return
        pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
        pStation = deviceManager.playerStationDictionary[pStationKey]
        if pStation.connectedDraxboard == None:
            print ("There is no Draxboard connected to this Station Hash")
            return
        actually_flash_drax(pStation)
    return

"""
Helper method to flash the ticket light of the draxboard on and off 8 times
"""
def actually_flash_drax(pStation):
    if pStation.connectedDraxboard != None:
        print ('-' * 60)
        print ("Flashing Ticket Light For Hash: " + str(pStation.persistedPlayerStationHash))
        for i in range(8):
            pStation.connectedDraxboard.toggle_output_state_of_drax(1 << 2, 2)
            sleep(.15)
            pStation.connectedDraxboard.toggle_output_state_of_drax(1 << 2, 1)
            sleep(.15)
    return

"""
Debug method used to enable a bit on the draxboard output
"""
def debug_bitenable_drax(deviceManager, bitToEnable = 0, playerStationHash = -1):
    if bitToEnable < 0 or bitToEnable >= 16:
        print ("Make sure that the bit you are enabling is a value from 0 to 15")
        return
    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedDraxboard != None:
                pStation.connectedDraxboard.toggle_output_state_of_drax(1 << bitToEnable, 1)
    else:
        if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
            print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
            return
        pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
        pStation = deviceManager.playerStationDictionary[pStationKey]
        if pStation.connectedDraxboard == None:
            print ("There is no Draxboard connected to this Station Hash")
            return
        pStation.connectedDraxboard.toggle_output_state_of_drax(1 << bitToEnable, 1)
    return

"""
Debug method used to disable a bit on the draxboard output
"""
def debug_bitdisable_drax(deviceManager, bitToDisable = 0, playerstationHash = -1):
    if bitToDisable < 0 or bitToDisable >= 16:
        print ("Make sure that the bit you are disabling is a value from 0 to 15")
        return
    if playerstationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedDraxboard != None:
                pStation.connectedDraxboard.toggle_output_state_of_drax(1 << bitToDisable, 2)
    else:
        if playerstationHash not in deviceManager.playerStationHashToParentDevicePath:
            print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
            return
        pStationKey = deviceManager.playerStationHashToParentDevicePath[playerstationHash]
        pStation = deviceManager.playerStationDictionary[pStationKey]
        if pStation.connectedDraxboard == None:
            print ("There is no Draxboard connected to this Station Hash")
            return
        pStation.connectedDraxboard.toggle_output_state_of_drax(1 << bitToDisable, 2)
    return

"""
Debug method used to set that Draxboard output state
"""
def debug_draxout(deviceManager, outputState = 0, playerStationHash = -1):
    if outputState < 0 or outputState >= 65536:
        print ("Make sure that the output state is a value from 0 to 65535")
        return
    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedDraxboard != None:
                pStation.connectedDraxboard.toggle_output_state_of_drax(outputState, 0)
    else:
        if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
            print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
            return
        pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
        pStation = deviceManager.playerStationDictionary[pStationKey]
        if pStation.connectedDraxboard == None:
            print ("There is no Draxboard connected to this Station Hash")
            return
        pStation.connectedDraxboard.toggle_output_state_of_drax(outputState, 0)
    return

"""
Debug method used to increment the hard meters that are attached to the draxboards

@type deviceManager: DragonMasterDeviceManager

@type meterID: int
@param meterID: the hard meter that we will be incrementing. There are typically 4 hard meters attached with values from 0-3

@type incrementValue: ushort
@param incrementValue: the number of ticks we want to send to the hard meter

@type playerStationHash: int
@param playerStationHash: the playerstation hash for the draxboard that we would like to send a hard meter event to. If this value is negative we will send an event to all draxboards
"""
def debug_meter_increment(deviceManager, meterID=0, incrementValue=1, playerStationHash = -1):
    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedDraxboard != None:
                pStation.connectedDraxboard.increment_meter_ticks(meterID, incrementValue)
    else:
        if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
            print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
            return
        pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
        pStation = deviceManager.playerStationDictionary[pStationKey]
        if pStation.connectedDraxboard == None:
            print ("There is no Draxboard connected to this Station Hash")
            return
        pStation.connectedDraxboard.increment_meter_ticks(meterID, incrementValue)
    return

"""
Sends an event to request the input state of our connected Draxboard device
"""
def debug_request_drax_input(deviceManager, playerStationHash = -1):
    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedDraxboard != None:
                pStation.connectedDraxboard.send_request_current_input_state()
    else:
        if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
            print ("The player station hash was not found. Perhaps there is no draxboard connected for that station.")
            return
        pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
        pStation = deviceManager.playerStationDictionary[pStationKey]
        if pStation.connectedDraxboard == None:
            print ("There is no Draxboard connected to this station hash")
            return
        pStation.connectedDraxboard.send_request_current_input_state()
    return
        
#endregion debug drax functions
            
#region debug DBV commands
"""
Debug test function whether the idle function works as expected in our Bill Acceptors
"""
def debug_idle_dbv(deviceManager, playerStationHash = -1):
    if playerStationHash < 0: 
        for dev in deviceManager.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                dev.idle_dbv()
        return

    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
        deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.idle_dbv()
    return

"""
Debug method that will set our dbv to the inhibit state based on the dbv comport that is passed in
"""
def debug_inhibit_dbv(deviceManager, playerStationHash = -1):
    if playerStationHash < 0: 
        for dev in deviceManager.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                dev.inhibit_dbv()
        return

    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
        deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.inhibit_dbv()
    return
    

"""
Debug method that will reset our DBV based on the comport
"""
def debug_reset_dbv(deviceManager, playerStationHash = -1):
    if playerStationHash < 0: 
        for dev in deviceManager.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                dev.reset_dbv()
        return

    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
        deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.reset_dbv()
    return

"""
Debug method to accept a bill that is in escrow
"""
def debug_accept_bill_dbv(deviceManager, playerStationHash = -1):
    if playerStationHash < 0: 
        for dev in deviceManager.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                dev.stack_bill()
        return

    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
        deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.stack_bill()
    return

"""
Debug method to reject a bill that is in escrow
"""
def debug_reject_bill_dbv(deviceManager, playerStationHash = -1):
    if playerStationHash < 0: 
        for dev in deviceManager.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                dev.reject_bill()
        return

    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
        deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.reject_bill()
    return

"""
Toggles the dbv between idle an inhibit. The time between idle to the next idle will be determined by the value seconds, between toggles.

One full toggle is idle->inhibit
two full toggles is idle->inhibit->idle->inhibit
"""
def debug_toggle_dbv_idle(deviceManager, numberOfToggles = 5, secondsBetweenToggles = 1, playerStationHash = -1):
    if numberOfToggles <= 0 or numberOfToggles > 100:
        print ("Number of toggles was was out of range. Please pass a number between 1 and 100")
        return

    toggleToIdle = True
    for i in range((numberOfToggles * 2)):
        #print ("Toggle: " + str(toggleToIdle))
        if playerStationHash < 0: 
            for dev in deviceManager.allConnectedDevices:
                if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                    if toggleToIdle:
                        dev.idle_dbv()
                    else:
                        dev.inhibit_dbv()
        else:
            if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
                print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
                return
            pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
            if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
                if toggleToIdle:
                    deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.idle_dbv()
                else:
                    deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.inhibit_dbv()
        sleep(secondsBetweenToggles / 2)
        toggleToIdle = not toggleToIdle
    print ("Completed Toggle Process")
    return

def debug_firmware_updated_dbv(deviceManager, playerStationHash=-1):
    if playerStationHash < 0: 
        for dev in deviceManager.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                dev.begin_firmware_download_process()
        return
    
    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
        deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.begin_firmware_download_process()
    return


"""
Updates the state of all bill acceptors. This will return a
"""
def debug_status_dbv(deviceManager, playerStationHash = -1):
    if playerStationHash < 0: 
        for dev in deviceManager.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                print (dev.State)
                dev.get_dbv_state()
        return
    
    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
        print (deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.State)
        deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor.get_dbv_state()
    return

"""
Prints the version of the DBV device that is passed through
"""
def debug_print_dbv_version(deviceManager, playerStationHash = -1):
    if playerStationHash < 0: 
        for dev in deviceManager.allConnectedDevices:
            if isinstance(dev, DragonMasterSerialDevice.BillAcceptor):
                print (str(dev.get_player_station_hash()) + " DBV Version: " + dev.dbvVersion)
        return
    
    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash was not found. Perhaps there is no draxboard connected for that station")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedBillAcceptor != None:
        print (str(dev.get_player_station_hash()) + " DBV Version: " + dev.dbvVersion)
    return


#endregion debug DBV commands

#region debug printer commands
"""
Prints a voucher ticket as it would appear with 0 credits
"""
def debug_print_voucher_ticket(deviceManager, playerStationHash = -1):

    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedPrinter != None:
                pStation.connectedPrinter.print_voucher_ticket("0", DragonMasterDeviceManager.PRINTER_CASHOUT_TICKET)

        return
    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash that was passed in was not valid")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedPrinter != None:
        deviceManager.playerStationDictionary[pStationKey].connectedPrinter.print_voucher_ticket("0", DragonMasterDeviceManager.PRINTER_CASHOUT_TICKET)
    else:
        print ("Player Station Found but there was no associted printer connected")

    return

"""
Prints a reprint voucher ticket as it would appear with 0 credits
"""
def debug_print_reprint_ticket(deviceManager, playerStationHash = -1):

    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedPrinter != None:
                pStation.connectedPrinter.print_voucher_ticket("0", DragonMasterDeviceManager.PRINTER_REPRINT_TICKET)

        return
    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash that was passed in was not valid")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedPrinter != None:
        deviceManager.playerStationDictionary[pStationKey].connectedPrinter.print_voucher_ticket("0", DragonMasterDeviceManager.PRINTER_REPRINT_TICKET)
    else:
        print ("Player Station Found but there was no associted printer connected")

    return

"""
Prints a test ticket as it would appear called from our Unity Application
"""
def debug_print_test_ticket(deviceManager, playerStationHash = -1):

    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedPrinter != None:
                pStation.connectedPrinter.print_voucher_ticket(DragonMasterDeviceManager.PRINTER_TEST_TICKET, "")

        return
    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash that was passed in was not valid")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedPrinter != None:
        deviceManager.playerStationDictionary[pStationKey].connectedPrinter.print_voucher_ticket(DragonMasterDeviceManager.PRINTER_TEST_TICKET, "")
    else:
        print ("Player Station Found but there was no associted printer connected")

    return


"""
Prints a codes ticket with all values set to 0
"""
def debug_print_codex_ticket(deviceManager, playerStationHash = -1):
    printDataBytesString = "123456|"
    printDataBytesString += "111111|"
    printDataBytesString += "CFS|"
    printDataBytesString += "102|"
    printDataBytesString += "02|"
    printDataBytesString += "DM1|"
    printDataBytesString += "90|"
    printDataBytesString += "1.5|"
    printDataBytesString += "987|"
    printDataBytesString += "654|"
    printDataBytesString += "321|"
    printDataBytesString += "111|"
    printDataBytesString += "222|"
    printDataBytesString += "333|"
    printDataBytesString += "444|"
    printDataBytesString += "555|"
    printDataBytesString += "666|"
    printDataBytesString += "This is a JSON EXAMPLE"

    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedPrinter != None:
                pStation.connectedPrinter.print_codex_ticket(bytes(printDataBytesString, 'utf-8'))
        return

    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash that was passed in was not valid")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedPrinter != None:
        deviceManager.playerStationDictionary[pStationKey].connectedPrinter.print_codex_ticket(bytes(printDataBytesString, 'utf-8'))
    else:
        print ("Player Station Found but there was no associted printer connected")

    return

"""
Prints an audit ticket with all values set to 0
"""
def debug_print_audit_ticket(deviceManager, playerStationHash = -1):
    debugLastArchiveClear = datetime.datetime(1999, 1, 1, 11, 11, 11)

    printDataByteString = "0|"#0
    printDataByteString += "0|"#1
    printDataByteString += debugLastArchiveClear.strftime("%m/%d/%Y") + "|"#2
    printDataByteString += debugLastArchiveClear.strftime("%H:%M:%S") + "|"#3
    printDataByteString += "100|"#4
    printDataByteString += "200|"#5
    printDataByteString += "-100|"#6
    printDataByteString += "-100|"#7
    printDataByteString += "400|"#8
    printDataByteString += "500|"#9
    printDataByteString += "-100|"#10
    printDataByteString += "-25|"#11
    printDataByteString += "1001|"#12
    printDataByteString += "100|"#13
    printDataByteString += "100|"#14
    printDataByteString += "0|"#15
    printDataByteString += "0|"#16
    printDataByteString += "10|"#17
    printDataByteString += "99|"#18
    printDataByteString += "2|"#19
    printDataByteString += "This is a JSON string|"#20
    printDataByteString += "1000000|"#21
    printDataByteString += "10000|"#22
    printDataByteString += "123456|"#23


    if playerStationHash < 0:
        for pStation in deviceManager.playerStationDictionary.values():
            if pStation.connectedPrinter != None:
                pStation.connectedPrinter.print_audit_ticket(bytes(printDataByteString, 'utf-8'))

        return
    if playerStationHash not in deviceManager.playerStationHashToParentDevicePath:
        print ("The player station hash that was passed in was not valid")
        return
    pStationKey = deviceManager.playerStationHashToParentDevicePath[playerStationHash]
    if deviceManager.playerStationDictionary[pStationKey].connectedPrinter != None:
        deviceManager.playerStationDictionary[pStationKey].connectedPrinter.print_audit_ticket(bytes(printDataByteString, 'utf-8'))
    else:
        print ("Player Station Found but there was no associted printer connected")

    return

#endregion debug printer commands

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
