#external lib imports
import socket
import pyudev

#std lib imports
import queue
import threading
from time import sleep

#internal project imports
import DragonMasterDevice
import DragonMasterSerialDevice

"""
Our device manager class that will find and hold all of our connected devices and manage their current state
It will manages messages between our Unity Application and assign commands to the correct devices.
"""
class DragonMasterDeviceManager:
    ##General Device Commands
    #This command will be sent as a single byte event simply to inform python that we are still connected to the our Unity application
    STATUS_FROM_UNITY = 0x00
    DEVICE_CONNECTED = 0x01
    DEVICE_DISCONNECTED = 0x02
    OMNI_EVENT = 0x03 #For messages that we send/receive to our omnidongle

    ##DRAX COMMANDS
    DRAX_ID = 0x10

    #Send Events
    DRAX_INPUT_EVENT = 0x11

    #Receive Events
    DRAX_OUTPUT_EVENT = 0x12
    DRAX_OUTPUT_BIT_ENABLE_EVENT = 0x13
    DRAX_OUTPUT_BIT_DISABLE_EVENT = 0x14
    DRAX_HARD_METER_EVENT = 0X15

    ##JOYSTICK COMMANDS
    JOYSTICK_ID = 0X20
    JOYSTICK_INPUT_EVENT = 0X21


    ##PRINTER COMMANDS
    PRINTER_ID = 0X40
    #Receive Events
    PRINTER_CASHOUT_TICKET = 0X41
    PRINTER_AUDIT_TICKET = 0X042
    PRINTER_CODEX_TICKET = 0X43
    PRINTER_TEST_TICKET = 0X44
    #Send Events
    PRINT_COMPLETE_EVENT = 0X45
    PRINT_ERROR_EVENT = 0x46

    #Printer Types
    CUSTOM_TG02 = 0X01
    RELIANCE_PRINTER = 0X02
    PYRAMID_PRINTER = 0X03

    ##BILL ACCEPTOR COMMANDS
    BILL_ACCEPTOR_ID = 0X80

    #Send Events
    BA_BILL_INSERTED_EVENT = 0X81
    BA_BILL_ACCEPTED_EVENT = 0X82
    BA_BILL_REJECTED_EVENT = 0X83

    #Receive Events
    BA_ACCEPT_BILL_EVENT = 0X84
    BA_REJECT_BILL_EVENT = 0X85
    BA_IDLE_EVENT = 0X86
    BA_INHIBIT_EVENT = 0X87
    BA_RESET_EVENT = 0X88


    #region debug variables
    DEBUG_PRINT_EVENTS_SENT_TO_UNITY = False
    DEBUG_PRINT_EVENTS_RECEIVED_FROM_UNITY = False

    
    #endregion debum variables


    def __init__(self,):
        self.tcpManager = TCPManager(self)
        self.CONNECTED_OMNIDONGLE = None #Since there should only be one omnidongle in our machine, we will only search until we find the first connection
        self.allConnectedDevices = [] #(DragonMasterDevice)
        self.playerStationDictionary = {}#Key: Parent USB Device Path (string) | Value: Player Station (PlayerStation)

        #Start a thread to search for newly connected devices
        deviceAddedThread = threading.Thread(target=self.device_connected_thread,)
        deviceAddedThread.isDaemon = True
        deviceAddedThread.start()
        sleep(.3)
        try: 
            print ('start search')
            self.search_for_devices()
        except Exception as e:
            print ("There was an error with our inital search")
            print (e)
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
                try:
                    self.search_for_devices()
                except Exception as e:
                    print ("There was an error searching for new devices")
                    print (e)
        return


    """
    This thread will be used to periodically poll for newly connected devices. This is more used as a back up incase our
    newly connected event thread fails to detect a new connection
    """
    def periodically_poll_for_devices_thread(self):
        
        return

    #endregion threaded events


    #region Device Management
    def initialize_printers(self, vendorID, productID):

        return

    """
    This method will search for all valid devices that are connected to our machine
    """
    def search_for_devices(self):
        allConnectedJoysticks = DragonMasterDevice.get_all_connected_joystick_devices()
        allConnectedDraxboards = DragonMasterSerialDevice.get_all_connected_draxboard_elements()
        DragonMasterSerialDevice.get_all_reliance_printer_serial_elements()
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
        print ("Device Added ID: " + str(deviceTypeID))

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
        print ("Device Removed ID: " + str(deviceTypeID))


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

            print (deviceToAdd.deviceParentPath)
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

    #endregion Device Management

    #region TCP Communication
    """
    Queue up an event to send to our Unity Application. This should always be of the type
    byteArray
    """
    def add_event_to_send(self, eventToSend):
        self.tcpManager.add_event_to_send(eventToSend)
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
            print (event)
            pass
        return
        
    #endregion TCP Communication


    pass

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
        # self.start_new_socket_receive_thread()
        # self.start_new_socket_send_thread()
        self.deviceManager = deviceManager
        


    """
    Be sure that the event that is passed through is of the type bytearray
    """
    def add_event_to_send(self, eventPacketToSend):
        if (eventPacketToSend == None):
            print ("The event added was null.")
            return
        self.tcpEventQueue.put(eventPacketToSend)
        
        return

    """
    Start a new instance of a socket thread that will send data to our Unity Application
    """
    def start_new_socket_send_thread(self):
        sendThread = threading.Thread(target=self.socket_send)
        sendThread.daemon = False
        sendThread.start()
        return

    """
    Start a new instance of a socket thread that will receive data from our unity application
    """
    def start_new_socket_receive_thread(self):
        receiveThread = threading.Thread(target=self.socket_receive)
        receiveThread.daemon = False
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
                        bytesToSend = bytesToSend + eventToAdd
                        #print (bytesToSend)
                    convertedByteArrayToSend = bytearray(bytesToSend)
                    if (len(bytesToSend) > 0):
                        print (convertedByteArrayToSend)
                    conn.send(convertedByteArrayToSend)
                    conn.close()
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
                print ("Receive Error")
                if socketRead != None:
                    socketRead.close()
                
                print (e)
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
    def separate_events_received_into_list(self, eventReceived):
        if (len(eventReceived) == 0):
            return
        eventMessages = []
        while (len(eventReceived) > 0):
            endOfMessage = 1 + eventReceived[0]
            if (len(eventReceived) > endOfMessage):
                endOfMessage = len(eventReceived)
            eventMessages.append(eventReceived[1:endOfMessage])
            eventReceived = eventReceived[endOfMessage - 1:]
        return
        

    pass



#region debug methods
def debug_print_all_player_stations(deviceManager):

    return

#endregion debug methods
