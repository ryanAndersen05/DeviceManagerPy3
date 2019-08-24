import DragonMasterDevice
import socket
import queue
import threading
from time import sleep

"""
Our device manager class that will find and hold all of our connected devices and manage their current state
It will manages messages between our Unity Application and assign commands to the correct devices.
"""
class DragonMasterDeviceManager:
    ##General Device Commands
    #This command will be sent as a single byte event simply to inform python that we are still connected to the our Unity application
    STATUS_FROM_UNITY = 0X00
    DEVICE_CONNECTED = 0X01
    DEVICE_DISCONNECTED = 0X02

    ##DRAX COMMANDS
    DRAX_ID = 0X10
    #Send Events
    DRAX_INPUT_EVENT = 0X11
    #Receive Events
    DRAX_OUTPUT_EVENT = 0X12
    DRAX_OUTPUT_BIT_EVENT = 0X13
    DRAX_HARD_METER_EVENT = 0X14

    ##JOYSTICK COMMANDS
    JOYSTICK_ID = 0X20
    JOYSTICK_INPUT_EVENT = 0X21


    ##PRINTER COMMANDS
    PRINTER_ID = 0X40

    CUSTOM_TG02 = 0X01
    RELIANCE_PRINTER = 0X02
    PYRAMID_PRINTER = 0X03
    


    ##BILL ACCEPTOR COMMANDS
    BILL_ACCEPTOR_ID = 0X80


    #TCP Variables



    def __init__(self,):
        self.tcpManager = TCPManager(self)
        
        return


    #Device Management

    def remove_device(deviceToRemove):
        print deviceToRemove
        return
    #End Device Management

    #TCP Communication ###############################################################
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
    def process_received_event(self, eventList):
        if (len(eventList) <= 0):
            return

        for event in eventList:

            pass
        return
        
    #END TCP Communication ###########################################################


    pass



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
    Be sure that the event that is passed through is of the type bytearray

    function - byte value that references the type of function that this event will be
    playerStationID - an id that is the 
    """
    def add_event_to_send(self, function, playerStationID, data):
        if (eventToSend == None):
            print ("The event added was null.")
            return
        self.tcpEventQueue.put(eventToSend)

        if (not self.sendingEventsToOurUnityApplication):
            self.socket_send()
        return

    """
    Start a new instance of a socket thread that will send data to our Unity Application
    """
    def start_new_socket_send_thread(self):
        sendThread = threading.Thread(socket_send)
        sendThread.daemon = False
        sendThread.start()
        return

    """
    Start a new instance of a socket thread that will receive data from our unity application
    """
    def start_new_socket_receive_thread(self):
        receiveThread = threading.Thread(socket_receive)
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
                byteMessage = []
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
                    self.deviceManager.process_received_event(self.separate_events_received_into_list(fullResponse))
                socketRead.shutdown(socket.SHUT_RDWR)
            except Exception as e:
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
