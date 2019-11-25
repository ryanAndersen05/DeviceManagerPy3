import queue
import threading
import socket

from time import sleep


"""
Class that handles all of our TCP communication. This will send and receive packets between our Unity application

Note: Packets should be sent in the form of [Function, playerStationID, Data.....]
"""
class TCPManager:
    MAX_THREADING_COUNT = 500
    HOST_ADDRESS = "127.0.0.1"
    SEND_PORT = 35001
    RECEIVE_PORT = 25001

    MAX_RECV_BUFFER = 1024

    def __init__(self):
        self.sendingEventsToOurUnityApplication = False
        self.tcpEventQueue = queue.Queue()#Queue of events that we want to send to Unity

        #REMEBER TO UNCOMMENT
        self.start_new_socket_receive_thread()
        self.start_new_socket_send_thread()
        # self.deviceManager = deviceManager
        


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
                    print (fullResponse)
                    # self.deviceManager.execute_received_event(self.separate_events_received_into_list(fullResponse))
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

tcpManager = TCPManager()
while True:
    sleep (1)