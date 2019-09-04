#std lib imports
import threading
#external lib imports
import evdev
import usb.core
import usb.util



from escpos.printer import Usb
#Internal project imports
import DragonMasterDeviceManager

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

    """
    Simply just sets the joystick device to be None. Primarily to ensure that we exit
    our threaded loop that is polling for new axes values
    """
    def disconnect_device(self):
        self.joystickDevice = None
        return 

    """
    Returns a string with the name of the device and the physical location of the joystick
    """
    def to_string(self):
        if self.joystickDevice != None:
            return "Joystick (" + self.joystickDevice.phys + ")"
        else:
            return "Joystick (Missing)"


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
            self.lastSentAxes = self.currentAxes
    pass



"""
Printer device handles printer events. Sends the status of the printer to Unity
"""
class Printer(DragonMasterDevice):
    CROSS_FIRE_PNG_PATH = ""
    DRAGON_MASTER_LOGO_PNG_PATH = ""
    LOCATION_NAME = "PlaceHolder"

    def __init__(self, dragonMasterDeviceManager):
        super().__init__(dragonMasterDeviceManager)
        self.printerObject = None
        self.currentState = (0,0)#Tuple represents the state of the printer. (Printer Status, Paper Availability)

    """
    This method formats and prints out a cash-out ticket
    """
    def print_cashout_ticket(self, totalCreditsWon, timeTicketRedeemed, playerStation="0", whiteSpaceUnderTicket = 10, isTestTicket=False, isReprintTicket=False):
        characterCount = 24
        try:
            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.textln('=' * characterCount)
            self.printerObject.set(align='center')
            try:
                self.printerObject.image(Printer.CROSS_FIRE_PNG_PATH, high_density_horizontal=True, high_density_vertical=True)
            except Exception as e:
                print("There was an error printing out the cross fire png")
                print(e)
                self.printerObject.textln("Cross-Fire")
            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.textln(Printer.LOCATION_NAME)
            self.printerObject.set(align='center', font='b', height=12)

            if isReprintTicket:
                self.printerObject.textln("REPRINT")
            elif isTestTicket:
                self.printerObject.textln("TEST TICKET")
            else:
                self.printerObject.textln("VOUCHER TICKET")
            
            self.printerObject.textln("STATION " + playerStation)
            

        except Exception as e:
            print ("There was an error printing our Cash-Out Ticket")

        return

    """

    """
    def print_audit_ticket(self, auditTicketData, whiteSpaceUnderTicket=7):

        return

    """

    """
    def print_codex_ticket(self, codexTicketData, whiteSpaceUnderTicket=6):

        return

    """

    """
    def get_updated_printer_state_and_paper_state(self):

        return 
    pass

"""
Extension of our printer object. This handles special properties for our Custom TG02 printer
"""
class CustomTG02(Printer):
    VENDOR_ID = 0x0dd4
    PRODUCT_ID = 0x0186
    IN_EP = 0x81
    OUT_EP = 0x02

    ##Override Methods
    def start_device(self, deviceElement):
        if deviceElement == None:
            return False
        self.printerObject = Usb(idVendor=CustomTG02.VENDOR_ID, idProduct=CustomTG02.PRODUCT_ID, in_ep=CustomTG02.IN_EP, out_ep=CustomTG02.OUT_EP)
        if self.printerObject == None:
            return False
        self.printerObject.device = deviceElement

        return True

    def disconnect_device(self):
        return super().disconnect_device()

    def fetch_parent_path(self, deviceElement):
        return super().fetch_parent_path(deviceElement)

    def to_string(self):
        return "CustomTG02(" + ")"
    #End Override Methods
    pass

class PhoenixPyramid(Printer):

    pass

"""
Extension of our printer class. This handles special properties for our Reliance Printer
"""
class ReliancePrinter(Printer):
    VENDOR_ID = 0x0425
    PRODUCT_ID = 0x8147
    IN_EP = 0x87
    OUT_EP = 0x08

    ##Override methods
    def start_device(self, deviceElement):
        try:
            if not deviceElement.is_kernel_driver_active(0):
                deviceElement.attach_kernel_driver(0)
        except Exception as e:
            print (e)
        print ("Step 1")
        self.printerObject = Usb(idVendor=ReliancePrinter.VENDOR_ID, idProduct=ReliancePrinter.PRODUCT_ID, in_ep=ReliancePrinter.IN_EP, out_ep=ReliancePrinter.OUT_EP)
        if self.printerObject == None:
            return False
        print("Step 2")
        self.printerObject.device = deviceElement
        return True

    def disconnect_device(self):
        return super().disconnect_device()

    def fetch_parent_path(self, deviceElement):
        return super().fetch_parent_path(deviceElement)

    def to_string(self):
        return "Reliance(" + ")"
    #End Override Methods
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

"""

"""
def get_all_connected_custom_tg02_printer_elements():
    return usb.core.find(idVendor=CustomTG02.VENDOR_ID, idProduct=CustomTG02.PRODUCT_ID, find_all=True)

"""

"""
def get_all_connected_reliance_printer_elements():
    return usb.core.find(idVendor=ReliancePrinter.VENDOR_ID, idProduct=ReliancePrinter.PRODUCT_ID, find_all=True)


##End Retrieve device method