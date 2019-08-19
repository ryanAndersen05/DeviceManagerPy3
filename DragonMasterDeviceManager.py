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



    def __init__(self,):
        self.tcpEventQueue = queue.Queue()#Queue that is used for sending device events to our Unity Application
        return

    #TCP Communication ###############################################################


    #END TCP Communication ###########################################################


    pass