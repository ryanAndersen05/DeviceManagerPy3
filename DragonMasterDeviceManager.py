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

    """
    Upon receiving an event from our Unity Application, we will process the command through this method
    """
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


    """
    Be sure that the event that is passed through is of the type bytearray
    """
    def add_event_to_send(self, eventToSend):
        if (eventToSend == None):
            print ("The event added was null.")
            return
        self.tcpEventQueue.put(eventToSend)

        if (not self.sendingEventsToOurUnityApplication):
            self.socket_send()
        return

    """
    This method sends all of the events that are currently in our event queue to our
    Unity Application
    """
    def socket_send(self):
        self.sendingEventsToOurUnityApplication = True



        self.sendingEventsToOurUnityApplication = False
        return

    """
    This method will 
    """
    def socket_receive(self):

        return
    pass
