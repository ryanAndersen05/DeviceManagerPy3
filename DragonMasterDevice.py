import DragonMasterDeviceManager
import evdev
import threading

"""
The Base class for all our Dragon Master Devices
"""
class DragonMasterDevice:

    def __init__(self, dragonMasterDeviceManager):
        self.playerStationID = 0
        self.dragonMasterDeviceManager = dragonMasterDeviceManager
        self.deviceParentPath = None
        self.devicePath = None

    """
    This method should be called every time we connect to a new device for the fist time. If our device does not connect correctly
    this mtehod should return false.

    deviceElement - The element that is retrieved from our pyudev search. This will 
    """
    def start_device(self, deviceElement):
        self.deviceParentPath = self.fetch_parent_path(deviceElement)
        return False

    def disconnect_device(self):
        return

    """
    This method will be called periodically to ensure that our device is still connected and fucntioning correctly
    """
    def poll_device_for_errors(self):
        return False

    """
    This method will retrieve the parent path of our device
    """
    def fetch_parent_path(self, deviceElement):
        return None

    """
    To string method primarily used for debugging purposes. This will return a string name of the device and any other relevant information
    """
    def to_string(self):
        return "Device ToString Not Defined"



"""
Joystick class. Sends events to our Unity application of the current state of the joystick
"""
class Joystick(DragonMasterDevice):
    JOYSTICK_DEVICE_NAME = "Ultimarc UltraStik Ultimarc Ultra-Stik Player 1"

    def __init__(self, dragonMasterDeviceManager):
        super().__init__(dragonMasterDeviceManager)
        self.joystickDevice = None#joystick device is our evdev element that will be used to collect the axes of our joystick

        #NOTE: We initialize the joystick axes to 128 as that is the neutral position. The values for our joystick are between 0-255
        self.currentAxes = (128,128)#The current axis values that our joystick is set to
        self.lastSentAxes = (128,128)#The last sent axes values. This is the last value that we have sent off to Unity

    """
    Starts up a thread that will check for updates to the axis
    """
    def start_device(self, deviceElement):
        super().start_device(deviceElement)
        self.joystickDevice = deviceElement

        self.joystickThread = threading.Thread(target=self.joystick_axes_update_thread,)
        self.joystickThread.daemon = True
        self.joystickThread.start()
        return True

    def disconnect_device(self):
        self.joystickDevice = None
        return 

    def to_string(self):
        return "Joystick"


    """
    Thread to update the current axis values of our joystick
    """
    def joystick_axes_update_thread(self):
        try:
            for event in self.joystickDevice.read_loop():
                if self.joystickDevice == None:
                    return
                if (event.type != evdev.ecodes.EV_SYN):
                    absevent = evdev.categorize(event)
                    if 'ABS_X' in str(absevent):
                        adjustedValue = event.value
                        updatedAxes = (adjustedValue, self.currentAxes[1])
                        self.currentAxes = updatedAxes
                    if 'ABS_Y' in str(absevent):
                        adjustedValue = event.value
                        updatedAxes = (self.currentAxes[0], adjustedValue)
                        self.currentAxes = updatedAxes
                if self.currentAxes != self.lastSentAxes:
                    self.lastSentAxes = self.currentAxes
                    # print (self.currentAxes)
        except Exception as e:
            print ("There was an error with our joystick connection")
            print (e)
            self.dragonMasterDeviceManager.remove_device(self)
        return

    """
    Sends an event to update the Joystick axes to our 
    """
    def send_updated_joystick_to_unity_application(self):
        if self.currentAxes != self.lastSentAxes:
            byteArrayPacketToSend = bytearray([DragonMasterDeviceManager.DragonMasterDeviceManager.JOYSTICK_INPUT_EVENT, self.playerStationID, self.currentAxes[0], self.currentAxes[1]])
            self.dragonMasterDeviceManager.add_event_to_send(byteArrayPacketToSend)
    pass



"""
Printer device handles printer events. Sends the status of the printer to Unity
"""
class Printer(DragonMasterDevice):

    pass

"""
Child class of our printer object. This handles special properties for our Custom TG02 printer
"""
class CustomTG02(Printer):

    pass

"""
Extension of our printer class. This handles special properties for our Reliance Printer
"""
class ReliancePrinter(Printer):

    pass


##Retrieve device methods
"""
This method will retrieve all valid joysticks that are connected to our machine
"""
def get_all_connected_joystick_devices():
    allJoystickDevices = [evdev.InputDevice(fn) for fn in evdev.list_devices()] #Creates a list of all connected input devices
    listOfValidJoysticks = []
    for dev in allJoystickDevices:
        if (dev.name == Joystick.JOYSTICK_DEVICE_NAME and "input0" in dev.phys):
            listOfValidJoysticks.append(dev)

    return listOfValidJoysticks
##End Retrieve device method