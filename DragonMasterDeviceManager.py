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
    #General Device Commands
    DEVICE_CONNECTED = 0X01
    DEVICE_DISCONNECTED = 0X02

    #DRAX COMMANDS
    DRAX_ID = 0X10
    DRAX_INPUT_EVENT = 0X11

    #JOYSTICK COMMANDS
    JOYSTICK_ID = 0X20
    JOYSTICK_INPUT_EVENT = 0X21


    #PRINTER COMMANDS
    PRINTER_ID = 0X40


    #BILL ACCEPTOR COMMANDS
    BILL_ACCEPTOR_ID = 0X80


    #TCP Variables



    def __init__(self,):
        self.tcpManager = TCPManager()
        return

    #TCP Communication ###############################################################
    """
    Queue up an event to send to our Unity Application. This should always be of the type
    byteArray
    """
    def add_event_to_send(self, eventToSend):
        self.tcpManager.add_event_to_send(eventToSend)

        return


    def process_received_event(self, eventReceived):

        return
        
    #END TCP Communication ###########################################################


    pass


"""
Class that handles all of our TCP communication
"""
class TCPManager:

    def __init__(self):
        self.sendingEventsToOurUnityApplication = False
        self.tcpEventQueue = queue.Queue()#Queue of events that we want to send to Unity


    def add_event_to_send(self, eventToSend):
        if (eventToSend == None):
            print ("The event added was null.")
            return
        self.tcpEventQueue.put(eventToSend)
        
        if (not self.sendingEventsToOurUnityApplication):
            self.socket_send()
        return

    def socket_send(self):
        self.sendingEventsToOurUnityApplication = True



        self.sendingEventsToOurUnityApplication = False
        return

    def socket_receive(self):

        return
    pass
