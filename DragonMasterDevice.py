#std lib imports
import threading
import os
import time
from time import sleep
import datetime

#external lib imports
import evdev
import usb.core
import usb.util
import queue

#escpos imports
from escpos.printer import Usb
from escpos.constants import RT_STATUS_ONLINE, RT_MASK_ONLINE
from escpos.constants import RT_STATUS_PAPER, RT_MASK_PAPER, RT_MASK_LOWPAPER, RT_MASK_NOPAPER

#Internal project imports
import DragonMasterDeviceManager
import DragonMasterSerialDevice

"""
@author Ryan Andersen, EQ Games, Phone #: (404-643-1783)

The Base class for all our Dragon Master Devices
"""
class DragonMasterDevice:

    def __init__(self, dragonMasterDeviceManager):

        #The Device Manager object that is managing this device
        self.dragonMasterDeviceManager = dragonMasterDeviceManager
        #Parent device path. This is used to group all devices to a specific player station
        self.deviceParentPath = None
        #Queue of events from our Unity application. We do not want to miss any events, but we also do not want to hold up other devices from receiving their events
        self.deviceEventQueue = queue.Queue()
        #Bool value that indicates whether or not we are performing a queued event
        self.isPerformingQueuedEvents = False

    """
    This method should be called every time we connect to a new device for the fist time. If our device does not connect correctly
    this mtehod should return false.

    deviceElement - The element that is retrieved from our pyudev search. This will 
    """
    def start_device(self, deviceElement):
        self.deviceParentPath = self.fetch_parent_path(deviceElement)
        return False

    """
    This method will be called upon removing a device from the device manager. Any clean up for a device class should happen here,
    such as disabling any hanging threads that no longer need to be active
    """
    def disconnect_device(self):
        self.deviceEventQueue = queue.Queue()#Clear all remainging events from our queue if there are any
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
    Returns a player station hash uint value for the device that we can use to send event packets to unity.
    """
    def get_player_station_hash(self):
        if self.dragonMasterDeviceManager == None:
            return None

        return self.dragonMasterDeviceManager.get_player_station_hash_for_device(self)

    """
    Queue up events to for our device to carry out
    """
    def add_event_to_queue(self, functionToPerform, *args):
        functionItems = [functionToPerform]
        functionItems += args
        
        self.deviceEventQueue.put(functionItems)

        if (not self.isPerformingQueuedEvents):
            self.isPerformingQueuedEvents = True

            eventThread = threading.Thread(target=DragonMasterDevice.threaded_perform_events, args=(self,))
            eventThread.daemon = True
            eventThread.start()
        return

    """
    functions that performs threaded events for this particular device
    """
    def threaded_perform_events(self):
        while (not self.deviceEventQueue.empty()):
            functionItems = self.deviceEventQueue.get()
            uinputPath = functionItems[0]
            try:
                args = functionItems[1:]
                uinputPath(*args)
            except Exception as e:
                print (e)
                print ("There was an error executing a function in our event queue: " + self.to_string())
        self.isPerformingQueuedEvents = False
        return

    
#region joystick classes

"""
Joystick class. Sends events to our Unity application of the current state of the joystick
"""
class Joystick(DragonMasterDevice):

    def __init__(self, dragonMasterDeviceManager):
        super().__init__(dragonMasterDeviceManager)
        self.joystickUInput = None#joystick device is our evdev element that will be used to collect the axes of our joystick

        #NOTE: We initialize the joystick axes to 128 as that is the neutral position. The values for our joystick are between 0-255
        self.currentAxes = (128,128)#The current axis values that our joystick is set to
        self.lastSentAxes = (128,128)#The last sent axes values. This is the last value that we have sent off to Unity

    #region override methods
    """
    Starts up a thread that will check for updates to the axis

    NOTE: In this case deviceElement is a type of UInput in the library evdev
    """
    def start_device(self, deviceElement):
        super().start_device(deviceElement)
        self.joystickUInput = deviceElement

        self.collectJoystickAxisThread = threading.Thread(target=self.joystick_axes_update_thread,)
        self.collectJoystickAxisThread.daemon = True
        self.collectJoystickAxisThread.start()
        return True

    """
    Simply just sets the joystick device to be None. Primarily to ensure that we exit
    our threaded loop that is polling for new axes values
    """
    def disconnect_device(self):
        super().disconnect_device()
        self.joystickUInput = None
        return 

    """
    Returns a string with the name of the device and the physical location of the joystick
    """
    def to_string(self):
        if self.joystickUInput != None:
            return "Joystick (" + self.joystickUInput.phys + ")"
        else:
            return "Joystick (Missing)"

    #endregion override methods

    """
    Thread to update the current axis values of our joystick
    """
    def joystick_axes_update_thread(self):
        try:
            for event in self.joystickUInput.read_loop():
                if self.joystickUInput == None:
                    return
                if (event.type != evdev.ecodes.EV_SYN):
                    absevent = evdev.categorize(event)
                    if 'ABS_X' in str(absevent):
                        updatedAxes = (event.value, self.currentAxes[1])
                        self.currentAxes = updatedAxes

                    if 'ABS_Y' in str(absevent):
                        updatedAxes = (self.currentAxes[0], event.value)
                        self.currentAxes = updatedAxes
                    if DragonMasterDeviceManager.DragonMasterDeviceManager.DEBUG_DISPLAY_JOY_AXIS:
                        print (str(self.get_player_station_hash()) + "-" + self.to_string() + ": " + str(self.currentAxes))
        except Exception as e:
            print ("There was an error with our joystick connection")
            print (e)
            self.dragonMasterDeviceManager.remove_device(self)
        return

    """
    Sends an event to update the Joystick axes to our 
    """
    def send_joystick_axes_if_updated(self):
        if self.currentAxes != self.lastSentAxes:
            eventData = [self.currentAxes[0], self.currentAxes[1]]
            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.JOYSTICK_INPUT_EVENT, eventData, self.dragonMasterDeviceManager.get_player_station_hash_for_device(self))
            self.lastSentAxes = self.currentAxes
    pass

    """
    Returns a value of 0 for our joystick, which should indicate an invalid joystick type. The Joystick class should probably be set to abstract in the future so that this does not happen
    """
    @staticmethod
    def get_joystick_id():
        print ("No Joystick ID has been properly set. Be sure to add a get_joystick_id() method to your Joystick class.")
        return 0
    pass


"""
Extension of Joystick class, with values specific to our Ulrimarc Ultra-Stik Joystick device
"""
class UltimarcJoystick(Joystick):
    JOYSTICK_DEVICE_NAME = "Ultimarc UltraStik Ultimarc Ultra-Stik Player 1"

    """
    Returns the device parent path of our joystick device
    """
    def fetch_parent_path(self, deviceElement):
        usbKey  = ''
        physSplit = deviceElement.phys.split('-')
        if len(physSplit) > 1:
            usbKey = physSplit[len(physSplit) - 1]
            usbKey = usbKey.split('/')[0]

        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if "js" in dev.sys_name and usbKey in dev.device_path:
                return dev.parent.parent.parent.parent.parent.device_path
        return

    def to_string(self):
        return "Ultimarc Joystick"

    @staticmethod
    def get_joystick_id():
        return DragonMasterDeviceManager.DragonMasterDeviceManager.ULTIMARC_JOYSTICK
    pass

"""
This class is an extension of our Joystick class. All functions remain the same, but the parent device path has changed as well
as the product name of the joystick
"""
class BaoLianJoystick(Joystick):
    
    JOYSTICK_DEVICE_NAME = "Baolian industry Co., Ltd. BL digital joystick #1"


    """
    Returns the device parent path of our joystick device
    """
    def fetch_parent_path(self, deviceElement):
        usbKey  = ''
        physSplit = deviceElement.phys.split('-')
        if len(physSplit) > 1:
            usbKey = physSplit[len(physSplit) - 1]
            usbKey = usbKey.split('/')[0]

        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if "js" in dev.sys_name and usbKey in dev.device_path:
                return dev.parent.parent.parent.parent.parent.parent.device_path
        return 

    def to_string(self):
        return "Bao Lian Joystick"

    @staticmethod
    def get_joystick_id():
        return DragonMasterDeviceManager.DragonMasterDeviceManager.BAOLIAN_JOYSTICK

    pass

#endregion joystick classes

"""
Printer device handles printer events. Sends the status of the printer to Unity


In General When using print commands in our printer we will want to send it as an array of chars. We want to make sure that the values that we send are accurate and sending it as a string seems like the most
accurate way to do this
"""
class Printer(DragonMasterDevice):
    #The path of our Cross fire png image
    CROSS_FIRE_PNG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Cross-fire.png")
    #The file path to our dragon master logo png
    DRAGON_MASTER_PNG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "DragonMaster.png")
    #Static variable for the name of the machine. This will be printed on every ticket. Can be changed from our Unity application
    LOCATION_NAME = "PlaceHolder"
    #The Machine number. Way for operators to differentiate which machine this came from. This can be changed from our Unity application
    MACHINE_NUMBER = "00001"



    def __init__(self, dragonMasterDeviceManager):
        super().__init__(dragonMasterDeviceManager)
        self.printerObject = None
        self.currentState = (0,0)#Tuple represents the state of the printer. (Printer Status, Paper Availability)
        self.lastSentPrinterState = (0, 0)


    def start_device(self, deviceElement):
        printerStateThread = threading.Thread(target=self.check_for_printer_state_thread)
        printerStateThread.daemon = True
        printerStateThread.start()

        return super().start_device(deviceElement)

    def disconnect_device(self):
        self.printerObject = None
        super().disconnect_device()
        return

    """
    Returns the printer type id. This is primarily for our Unity application to idntify which type of printer
    it is connected to. This will help wiht deciphering states we receive from our application

    NOTE: All classes that extend the printer class should contain this method
    """
    @staticmethod
    def get_printer_id():
        return 0x00

    def get_printer_object(self):
        return None

    """
    Method that will check the current state of the connected printer. This will send a message to our Unity
    Application if the state has changed
    """
    def check_for_printer_state_thread(self):
        while self.printerObject != None:
            try:
                self.currentState = self.get_updated_printer_state_and_paper_state()
                
                if self.currentState != self.lastSentPrinterState:
                    self.add_printer_state_to_send_queue()
                    self.lastSentPrinterState = self.currentState
            except Exception as e:
                print ("There was a problem getting the state of the printer")
                print (e)
                self.dragonMasterDeviceManager.remove_device(self)
            
            sleep (.2)

    """

    """
    def add_printer_state_to_send_queue(self):
        self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_STATE_EVENT, self.currentState[0].to_bytes(4, byteorder='big') + self.currentState[1].to_bytes(1, byteorder='big'), self.get_player_station_hash())
        return

    
    """
    sends a command to the connected printer to print a QR Code
    """
    def print_qr_code(self, stringToPrint, sizeOfQR):
        self.printerObject.qr(content=stringToPrint, size=sizeOfQR) # Print the QR code to be scanned. We need to figure out the content of these codes.



    """
    This method will print out a voucher ticket. The general format should apply to all of our printer types
    """
    def print_voucher_ticket(self, ticketType, printVoucherData, whiteSpaceUnderTicket=1):


        totalCreditsWon = "0.00"
        playerStation = "0"
        validationNumber = "0"
        TerminalID = "000000"
        dateTimeOfPrint = None

        try:

            if ticketType != DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_TEST_TICKET:
                propertiesSplitList = str(printVoucherData).split('|')
                totalCreditsWon = propertiesSplitList[0]
                playerStation = propertiesSplitList[1]
                validationNumber = propertiesSplitList[2]
                TerminalID = propertiesSplitList[3]
                dateTimeOfPrint = datetime.datetime(propertiesSplitList[4], propertiesSplitList[5], propertiesSplitList[6], propertiesSplitList[7], propertiesSplitList[8], propertiesSplitList[9])

            if dateTimeOfPrint == None:#An older version of the game may not provide the datetime of the print. This probably won't be an issue, but just in case....
                dateTimeOfPrint = datetime.datetime.now()
                print ("Date Time was None, defaulting to the current time on our system clock")
            # self.config_text()
            self.printerObject.set(align='center', font='b', height=12, bold=False)
            if ticketType == DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_REPRINT_TICKET:
                self.printerObject.textln("***REPRINT***")

            self.printerObject.set()
            self.printerObject.set(align='center', font='b', height=12, bold=False)
            self.printerObject.textln('========================')
            self.printerObject.textln("THANKS FOR PLAYING")
            self.printerObject.textln("VALID ON DATE OF \nISSUE ONLY!")
            self.printerObject.textln('========================')
            self.printerObject.set(align='center', font='b', height=12, bold=True)  # Align text
            self.printerObject.textln(Printer.LOCATION_NAME)
            self.printerObject.set(align='center', font='b', height=12, bold=False)
            self.printerObject.textln('========================')

            # Print text and image
            # try:
            #     self.printerObject.image(Printer.CROSS_FIRE_PNG_PATH, high_density_horizontal=True, high_density_vertical=True)  # Cross Fire Image
            # except Exception as e:
            #     print ("There was an error reading the image 'Cross-fire.png'")
            #     self.printerObject.textln("Cross Fire")#Instead of loading the image we use the actual text

            self.printerObject.set(align='center', font='b', height=12, bold=False)
            self.printerObject.textln(self.dragonMasterDeviceManager.DRAGON_MASTER_VERSION_NUMBER)
            self.printerObject.textln("TID: " + TerminalID)
            if ticketType == DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_REPRINT_TICKET:
                self.printerObject.textln("REPRINT TICKET")
            elif ticketType == DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_TEST_TICKET:
                self.printerObject.textln('Test Ticket')
            else:
                self.printerObject.textln('VOUCHER TICKET')
            self.printerObject.textln(dateTimeOfPrint.strftime("%m/%d/%y, %I:%M:%S %p"))

            if ticketType == DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_REPRINT_TICKET:
                self.printerObject.textln("***REPRINT***")

            self.printerObject.set(align='center', font='b', height=24, bold=True)
            self.printerObject.textln('=' * 24)
            
            self.printerObject.set(align='center', font='b', height=12, bold=False)

            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple("Machine", Printer.MACHINE_NUMBER, 24, ' ')) # Print Machine Number.
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple("Station", playerStation, 24, ' '))

            if ticketType == DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_REPRINT_TICKET:
                self.printerObject.textln("***REPRINT***")

            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.textln(' ')


            self.printerObject.set(align='center', font='b', height=12, bold=True)
            if ticketType == DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_TEST_TICKET:
                self.printerObject.textln('REDEEM             TEST')
            else:
                self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('REDEEM', '$' + str(totalCreditsWon), 24)) # Print the amount to be redeemed.

            if ticketType == DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_REPRINT_TICKET:
                self.printerObject.set(align='center', font='b', height=12, bold=False)
                self.printerObject.textln("***REPRINT***")

            qrData = "$"+ totalCreditsWon + " " + dateTimeOfPrint.strftime('%I:%M:%S %p  %x')
            self.printerObject.set(align='center', font='b', height=12)
            self.print_qr_code(qrData, 8)

            self.printerObject.set(align='center', font='b', height=12, bold=False)

            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple("VALIDATION: ", validationNumber, 24))#Validation number.

            self.printerObject.ln(1)
            try:
                self.printerObject.image(Printer.DRAGON_MASTER_PNG_PATH, high_density_horizontal=True, high_density_vertical=True)  # Dragon Master Image.
            except Exception as e:
                print ("There was an error when trying to read the image 'DragonMaster.png'")
                print (e)
                # self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINT_ERROR_EVENT, self.get_player_station_hash())
                self.printerObject.textln("Dragon's Ascent")
                self.printerObject.textln('=' * 24)
            self.printerObject.textln(self.get_footer_string())

            if ticketType == DragonMasterDeviceManager.DragonMasterDeviceManager.PRINTER_REPRINT_TICKET:
                self.printerObject.set(align='center', font='b', height=12, bold=False)
                self.printerObject.textln("***REPRINT***")

            self.printerObject.ln(whiteSpaceUnderTicket)

            self.printerObject.cut(feed=True)# Cut the page for removal.

            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINT_COMPLETE_EVENT, [], self.get_player_station_hash())
        except Exception as e:
            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINT_ERROR_EVENT, [], self.get_player_station_hash())
            print ("Printer Exception: " + str(e))
            return



    """
    Prints and formats our audit ticket from the byte array data that we receive

    TODO: Update this to match the current voucher ticket from our Python2.7 application
    """
    def print_audit_ticket(self, auditTicketData, line_length = 32, whiteSpaceUnderTicket=7):
        '''
        auditInfoString parameter list / order (ex. auditInfoString[1] = parentDeviceKey)
        0: Player station ( 0 = Machine wide Audit, 1-8 = Player station specific)
        1: Security Level (1-5) (If security level < 5, we will not print the archive values)
        2: List Clear Date (Archive, Weekly, Daily)
        3: List Clear Time (Archive, Weekly, Daily)
        4: Credit In (Archive, Weekly, Daily)
        5: Wins Out (Archive, Weekly, Daily)
        6: I-O Hold (Archive, Weekly, Daily)
        7: Hold % (Archive, Weekly, Daily)
        8: Points Played (Archive, Weekly, Daily)
        9: Points Won (Archive, Weekly, Daily)
        10: P-W Earned (Archive, Weekly, Daily)
        11: Return % (Archive, Weekly, Daily)
        12: Games Played (Archive, Weekly, Daily)
        13: Games Won (Archive, Weekly, Daily)
        14: Hit % (Archive, Weekly, Daily)
        15: Coupon Sale (Archive, Weekly, Daily)
        16: Free Entry (Archive, Weekly, Daily)
        17: Current Terminal Balance
        18: Fill Time Remaining
        19: Period that will be printed
        20: Audit JSON string (Convert this to QR code)
        21: large progressive reward value
        22: small progressive reward value
        23: TerminalID
        '''

        try:
            auditTicketDataString = str(auditTicketData, 'utf-8')
            auditInfoString = auditTicketDataString.split('|')

            self.config_text()
            #Period refers to archive/weekly/daily history and will be represented as 0,1,2 respectively
            periodType = int(auditInfoString[19])
            periodName = ""
            if periodType == 0:
                periodName = 'ARCHIVE'
            elif periodType == 1:
                periodName = 'WEEKLY'
            elif periodType == 2:
                periodName = 'DAILY'


            self.printerObject.set(align='center', font='b', height=1, bold=False)
            self.printerObject.textln('=' * line_length)
            self.printerObject.set(align='center', font='b', height=14, bold=True)
            self.printerObject.textln("Dragon's Ascent")
            self.printerObject.set(align='center', bold=False, height=14)
            self.printerObject.textln('A Game Of Skill')
            self.printerObject.textln('and Strategy')
            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.set(align='center', font='b', height=1, bold=False)
            self.printerObject.textln(DragonMasterDeviceManager.DragonMasterDeviceManager.DRAGON_MASTER_VERSION_NUMBER)
            self.printerObject.textln("TID: " + auditInfoString[23])
            # self.printerObject.textln('Ver: ' + DragonMasterDeviceManager.DRAGON_MASTER_VERSION_NUMBER)

            if str(auditInfoString[2]) == '0':
                self.printerObject.textln("MACHINE AUDIT (" + periodName + ")")
            else:
                print (auditTicketDataString + "             " + auditInfoString[0])
                self.printerObject.textln("PLAYER AUDIT " + auditInfoString[0] + " (" + periodName+ ")")

            currentDateTime = time.strftime('%x %I:%M:%S %p')
            self.printerObject.textln('=' * line_length)

            self.printerObject.textln(currentDateTime)

            if str(auditInfoString[1]) != '5':  # If the security level is not 5, we want to print "N/A" for the archive values.
                for x in range(4, 46, 3):  # Archive values start at 4, and are present every 3rd value. (ex. 4,7,10)
                    pass



            self.printerObject.set(align='center', height=1, width=1, custom_size=False, font='b')

            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('DESCRIPT', periodName, lengthOfString=line_length, spacingChar=' '))
            self.printerObject.set(align='center', height=1, width=1, custom_size=False, font='b')
            self.printerObject.textln('=' * line_length)
            self.printerObject.line_spacing(spacing=0, divisor=360)


            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('LSTCLRDATE', auditInfoString[2], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('LSTCLRTIME', auditInfoString[3], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('CRDT IN', '$' + auditInfoString[4], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('CRDT OUT', '$' + auditInfoString[5], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('I-O HOLD', '$' + auditInfoString[6], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('HOLD%', auditInfoString[7] + '%', lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('PTS PLAYED', '$' + auditInfoString[8], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('POINTS WON', '$' + auditInfoString[9], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('P-W EARNED', '$' + auditInfoString[10], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('RETURN%', auditInfoString[11] + '%', lengthOfString=line_length, spacingChar=' '))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('GAMES PLYD', auditInfoString[12], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('GAMES WON', auditInfoString[13], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('HIT%', auditInfoString[14] + '%', lengthOfString=line_length, spacingChar=' '))
            
            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('LG PRG', '$' + auditInfoString[21], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('SM PRG', '$' + auditInfoString[22], lengthOfString=line_length, spacingChar=' '))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.textln('CRNT TRMNL BAL: $' + str(auditInfoString[17]))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.set(align='center', font='b', height=12)
            self.print_qr_code(auditInfoString[20], 4)

            self.printerObject.set(align='center')
            self.printerObject.textln('FILL/TIME REMAINING')
            self.printerObject.textln(str(auditInfoString[18]))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.set(align='center', font='b', height=12, bold=False)
            self.printerObject.textln(self.get_footer_string())

            self.printerObject.textln('\n' * whiteSpaceUnderTicket)#Give a little bit of white space between tickets

            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINT_COMPLETE_EVENT, [], self.get_player_station_hash())


        except Exception as e:
            print ("There was an error printing an audit ticket:" + str(e))
            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINT_ERROR_EVENT, [], self.get_player_station_hash())

        return

    """
    Prints and formats a code exchange ticket
    """
    def print_codex_ticket(self, codexTicketData, lineLength=32, whiteSpaceUnderTicket=6):
        """
        0: TID
        1: LICENSE
        2: PRODUCT
        3: VERSION
        4: BUILD
        5: REGION
        6: FILL PERCENT
        7: FILL-COUNT
        8: SEED-A
        9: SEED-B
        10: SEED-C
        11: GROUP-1
        12: GROUP-2
        13: GROUP-3
        14: GROUP-4
        15: GROUP-5
        16: GROUP-6
        17: QR JSON
        """
        try:
            codexTicketDataString = str(codexTicketData, 'utf-8')
            codexTicketArray = codexTicketDataString.split('|')

            self.config_text()
            self.printerObject.set(align='center', font='b', height=14, bold=True)
            self.printerObject.textln("Dragon's Ascent")
            self.printerObject.set(align='center', bold=False, width=1, height=1, custom_size=True)
            self.printerObject.textln('A Game of Skill\n and Strategy')
            self.printerObject.set(align='center', height=1, width=1, custom_size=False, font='b')
            self.printerObject.textln('=' * lineLength)

            self.printerObject.set(align='center', bold=True)
            #self.printerObject.textln('SKL503.07CPN     BANK1')
            self.printerObject.textln(DragonMasterDeviceManager.DragonMasterDeviceManager.DRAGON_MASTER_VERSION_NUMBER)

            self.printerObject.set(align = 'center', bold=True)
            self.printerObject.textln("TID: " + codexTicketArray[0])
            self.printerObject.textln("CODE EXCHANGE")

            self.printerObject.textln(time.strftime("%m/%d/%y, %I:%M:%S %p"))

            self.printerObject.set(align='center', height=1, width=1, bold=False, custom_size=True, font='b')
            self.printerObject.textln('=' * lineLength)

            spaceCount = int((lineLength - 12) / 3)
            spaceChar = ' ' * spaceCount
            lblLine = "PRD" + spaceChar + "VER" + spaceChar + "BLD" + spaceChar + "REG"
            self.printerObject.textln(lblLine)
            self.printerObject.set(align='center', height=1, width=1, bold=True, custom_size=True, font='b')
            self.printerObject.textln(codexTicketArray[2] + spaceChar + codexTicketArray[3] + spaceChar + codexTicketArray[4] + spaceChar + codexTicketArray[5])

            self.printerObject.set(align='center', height=1, width=1, bold=False, custom_size=True, font='b')
            self.printerObject.textln('=' * lineLength)

            spaceCount = int((lineLength - 9) / 2)
            self.printerObject.textln("FILL-CNT" + (' ' * (spaceCount - 5)) + "TID" + (' ' * spaceCount) + "LIC")
            spaceCount = int((lineLength - 18) / 2)
            self.printerObject.set(align='center', height=1, width=1, bold=True, custom_size=True, font='b')
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple(codexTicketArray[7], codexTicketArray[0], lineLength - 6 - spaceCount) + (' ' * spaceCount) + codexTicketArray[1])

            self.printerObject.set(align='center', height=1, width=1, bold=False, custom_size=True, font='b')
            self.printerObject.textln('=' * lineLength)

            spaceCount = int((lineLength - 18) / 2)
            spaceChar = ' ' * spaceCount

            self.printerObject.textln("SEED-A" + spaceChar + "SEED-B" + spaceChar + "SEED-C")
            spaceCount = int((lineLength - 15) / 2)
            spaceChar = ' ' * spaceCount
            self.printerObject.set(align='center', height=1, width=1, bold=True, custom_size=True, font='b')
            self.printerObject.textln(" " + codexTicketArray[8] + " " + spaceChar + " " + codexTicketArray[9] + " " + spaceChar + " " + codexTicketArray[10] + " ")
            self.printerObject.set(align='center', height=1, width=1, bold=False, custom_size=True, font='b')
            self.printerObject.textln('=' * lineLength)
            
            self.printerObject.textln("GRP-1" + spaceChar + "GRP-2" + spaceChar + "GRP-3")
            self.printerObject.set(align='center', height=1, width=1, bold=True, custom_size=True, font='b')
            self.printerObject.textln(" " + codexTicketArray[11] + " " + spaceChar + " " + codexTicketArray[12] + " " + spaceChar + " " + codexTicketArray[13] + " ")

            self.printerObject.set(align='center', height=1, width=1, bold=False, custom_size=True, font='b')
            self.printerObject.textln('=' * lineLength)

            self.printerObject.textln("GRP-4" + spaceChar + "GRP-5" + spaceChar + "GRP-6")
            self.printerObject.set(align='center', height=1, width=1, bold=True, custom_size=True, font='b')
            self.printerObject.textln(" " + codexTicketArray[14] + " " + spaceChar + " " + codexTicketArray[15] + " " + spaceChar + " " + codexTicketArray[16] + " ")

            self.printerObject.set(align='center', font='b', height=12)
            self.print_qr_code(codexTicketArray[17], 4)

            self.printerObject.textln('=' * lineLength)
            self.printerObject.set(align='center', font='b', height=12, bold=False)
            self.printerObject.textln(self.get_footer_string())
            self.printerObject.textln('\n' * whiteSpaceUnderTicket)

            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINT_COMPLETE_EVENT, [], self.get_player_station_hash())
        except Exception as e:
            print ("There was an error printing our codex ticket")
            print (e)
            self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINT_ERROR_EVENT, [], self.get_player_station_hash())

            return

    

    """
    Returns the updated printer state and paper state as a tuple. These values should both be returned as byte values
    """
    def get_updated_printer_state_and_paper_state(self):
        try:
            self.printerObject.query_status(mode=RT_STATUS_ONLINE)[0]
            printerStatus = 0
            paperStatus = 0
            self.printerObject._raw(RT_STATUS_ONLINE)
            printerStatus = self.printerObject._read()[0]
            self.printerObject._raw(RT_STATUS_PAPER)
            status = self.printerObject._read()
            if len(status) == 0:
                paperStatus = 2
            if (status[0] & RT_MASK_NOPAPER == RT_MASK_NOPAPER):
                paperStatus = 0
            if (status[0] & RT_MASK_LOWPAPER == RT_MASK_LOWPAPER):
                paperStatus = 1
            if (status[0] & RT_MASK_PAPER == RT_MASK_PAPER):
                paperStatus = 2#Has paper
            return (printerStatus, paperStatus)


        except Exception as e:
            if (str(e).__contains__("Errno 110")):
                print("Time Out Error. Should be resolved once paper is put back into our custom TG02")
                return (0, 0)
            print ("Error experienced while trying to gather paper status")
            print (e)
            return None 
    pass

    def config_text(self):
        self.printerObject.set()
        return

    def get_footer_string(self):
        return "VOID IF MUTILATED\nVAL# 1522789371186\n_" + DragonMasterDeviceManager.DragonMasterDeviceManager.DRAGON_MASTER_VERSION_NUMBER + "_\n2017-2019 ALL RIGHTS RESERVED"

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
        self.printerObject = self.get_printer_object()

        if self.printerObject == None:
            return False
        self.printerObject.device = deviceElement
        if self.printerObject.device.is_kernel_driver_active(0):
            self.printerObject.device.detach_kernel_driver(0)

        self.printerObject.device.reset()
        self.printerObject.device.set_configuration()
        self.config_text()
        
        
        super().start_device(deviceElement)

        return True

    def disconnect_device(self):
        super().disconnect_device()
        return

    def fetch_parent_path(self, deviceElement):
        pathString = ""
        pathString += str(deviceElement.bus) + "-"
        
        for p in deviceElement.port_numbers:
            pathString += str(p) + "."

        pathString = pathString[:len(pathString) - 1]
        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if dev.sys_name == pathString:
                return dev.parent.device_path
                
        return None

    """
    Sends a serial message to configure the text format of the custom printer
    """
    def config_text(self):
        msg = '\x1b\xc1\x30'
        self.printerObject._raw(msg)
        Printer.config_text(self)
        return


    def to_string(self):
        return "CustomTG02(" + ")"

    def get_printer_object(self):
        return Usb(idVendor=CustomTG02.VENDOR_ID, idProduct=CustomTG02.PRODUCT_ID, in_ep=CustomTG02.IN_EP, out_ep=CustomTG02.OUT_EP)
    #End Override Methods

    @staticmethod
    def get_printer_id():
        return DragonMasterDeviceManager.DragonMasterDeviceManager.CUSTOM_TG02
    pass

"""
Extension of our printer class. Handles special properties for our NextGen Coupon printer
"""
class NextGen(Printer):
    
    pass

class PyramidPrinter(CustomTG02):
    VENDOR_ID = 0x0425
    PRODUCT_ID = 0x0412
    IN_EP = 0x81
    OUT_EP = 0x02

    def start_device(self, deviceElement):
        if deviceElement == None:
            return False
        self.printerObject = self.get_printer_object()
        if self.printerObject == None:
            return False
        self.printerObject.device = deviceElement
        if self.printerObject.device.is_kernel_driver_active(0):
            self.printerObject.device.detach_kernel_driver(0)
        self.printerObject.device.reset()
        self.printerObject.device.set_configuration()
        self.config_text()
        
        super().start_device(deviceElement)
        return True

    def get_printer_object(self):
        return Usb(*(PyramidPrinter.VENDOR_ID, PyramidPrinter.PRODUCT_ID, None, 0, PyramidPrinter.IN_EP, PyramidPrinter.OUT_EP))

    def print_qr_code(self, stringToPrint, sizeOfQR):
        stringLenBytes = len(stringToPrint).to_bytes(2, 'little')
        print (stringLenBytes)
        payload = [0x0d, 0x1d, 0x28, 0x6b, len(stringToPrint) + 3, 0x00, 0x31, 0x50, 0x31]
        payload += [ord(c) for c in stringToPrint]

        payload += [0x1d, 0x28, 0x6b, 0x03, 0x00, 0x51, 0x31]
        print (str(payload))
        self.printerObject._raw(payload)

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
    def __init__(self, dragonMasterDeviceManager):
        super().__init__(dragonMasterDeviceManager)
        self.associatedRelianceSerial = None

    """
    The reliance start device function is in charge of both starting our reliance usb printer as well as finding the serial component of the printer
    """
    def start_device(self, deviceElement):


        self.printerObject = self.get_printer_object()
        if self.printerObject == None:
            return False

        self.printerObject.device = deviceElement
        if self.printerObject.device.is_kernel_driver_active(0):
            self.printerObject.device.detach_kernel_driver(0)

        self.associatedRelianceSerial = self.get_matching_reliance_serial(deviceElement)
        if self.associatedRelianceSerial == None:
            return False

        self.printerObject.set()
        super().start_device(deviceElement)
        if self.deviceParentPath == None:
            return False

        return True

    """
    Disconnects both the associated Reliance Serial class and disconnects this printer device
    """
    def disconnect_device(self):
        if self.associatedRelianceSerial  != None:
            self.associatedRelianceSerial.disconnect_device()
        
        super().disconnect_device()
        return

    """

    """
    def fetch_parent_path(self, deviceElement):
        pathString = self.port_numbers_to_usb_address(deviceElement)

        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if dev.sys_name == pathString:
                return dev.parent.device_path
        return None

    """
    Returns a tuple of the state and the paper availability of our printer
    """
    def get_updated_printer_state_and_paper_state(self):
        fullPrinterStatus = self.associatedRelianceSerial.get_printer_status()
        if fullPrinterStatus == None:
            print ("The return status of our reliance printer was invalid")
            return (0, 0)
        paperStatus = int(fullPrinterStatus[2])
        printerStatus = 0
        

        printerStatus += int(fullPrinterStatus[3])
        printerStatus += int(fullPrinterStatus[4]) * 256
        printerStatus += int(fullPrinterStatus[5]) * 65536

        return (printerStatus, paperStatus)


        

    def to_string(self):
        return "Reliance(" + ")"
    #End Override Methods


    #region helper methods

    """
    Since we can not detach the kernal driver normally with the Reliance printer we will send a blank command to
    do that for us. In this case we simply align the text to the left. Keep in mind you can use any command in the escpos printer
    to accomplish this.
    """
    def detach_printer(self):
        self.printerObject.set() 

    """
    converts the port numbers and bus number of our printer element into a string usb location path
    """
    def port_numbers_to_usb_address(self, deviceElement):
        pathString = ""
        pathString += str(deviceElement.bus) + "-"
        
        for p in deviceElement.port_numbers:
            pathString += str(p) + "."

        pathString = pathString[:len(pathString) - 1]
        return pathString

    """
    There are two components to our reliance printer. The first being the normal USB printer in which we relay normal escpos commands to print out ticket.
    The second is the reliance Serial port in which we gather the status of our printer and the amount of paper remaining as well as send off an special commands
    such as cut, retract, etc.
    """
    def get_matching_reliance_serial(self, deviceElement):
        pathString = self.port_numbers_to_usb_address(deviceElement)
        
        allRelianceSerialList = DragonMasterSerialDevice.get_all_reliance_printer_serial_elements()
        for rSerial in allRelianceSerialList:
            try:
                if rSerial.location.split(':')[0] == pathString:
                    associatedSerial = DragonMasterSerialDevice.ReliancePrinterSerial(self.dragonMasterDeviceManager, self)
                    if associatedSerial.start_device(rSerial):
                        return associatedSerial
                    else:
                        return None

            except Exception as e:
                print ("Trying to match reliance printer reliance serial usb path")
                print (e)
        return None
    #endregion helper methods


    #region override printer methods

    """
    Override method to print our audit ticket for Reliance Printers
    """
    def print_audit_ticket(self, auditInfoString):
        self.associatedRelianceSerial.retract()
        Printer.print_audit_ticket(self, auditInfoString, 29, 0)
        self.associatedRelianceSerial.cut()
        return

    """
    Override method to print our voucher ticket for Reliance Printers
    """
    def print_voucher_ticket(self, ticketType, eventData):
        self.associatedRelianceSerial.retract()
        Printer.print_voucher_ticket(self, ticketType, eventData)
        self.associatedRelianceSerial.cut()

    """
    Override method to print our codex ticket for Reliance Printers
    """
    def print_codex_ticket(self, codexTicketInfo, lineLength=29, whiteSpaceUnderTicket=0):
        self.associatedRelianceSerial.retract()
        Printer.print_codex_ticket(self, codexTicketInfo, lineLength, whiteSpaceUnderTicket)
        self.associatedRelianceSerial.cut()

    """

    """
    def get_printer_object(self):
        return Usb(idVendor=ReliancePrinter.VENDOR_ID, idProduct=ReliancePrinter.PRODUCT_ID, in_ep=ReliancePrinter.IN_EP, out_ep=ReliancePrinter.OUT_EP)
    #endregion override printer methods

    @staticmethod
    def get_printer_id():
        return DragonMasterDeviceManager.DragonMasterDeviceManager.RELIANCE_PRINTER
    pass


##Retrieve device methods
"""
This method will retrieve all valid joysticks that are connected to our machine

Returns two lists. The first list is all connected Ultimarc joysticks
The seconds list are connected Bao Lian Joysticks
"""
def get_all_connected_joystick_devices():
    allConnectedUInputDevices = [evdev.InputDevice(uinputPath) for uinputPath in evdev.list_devices()] #Creates a list of all connected input devices
    listOfUltramarkJoysticks = []
    listOfBoaLianJoysticks = []

    for uInputDevice in allConnectedUInputDevices:
        if (uInputDevice.name == UltimarcJoystick.JOYSTICK_DEVICE_NAME and "input0" in uInputDevice.phys):
            listOfUltramarkJoysticks.append(uInputDevice)
        if (uInputDevice.name == BaoLianJoystick.JOYSTICK_DEVICE_NAME and "input0" in uInputDevice.phys):
            listOfBoaLianJoysticks.append(uInputDevice)

    return listOfUltramarkJoysticks, listOfBoaLianJoysticks

def get_all_connected_printers():
    return get_all_connected_custom_tg02_printer_elements(), get_all_connected_reliance_printer_elements(), get_all_connected_pyramid_printer_elements()

"""
Returns a list of all the connected custom TG02 printers. We do this by searching for a matching vid and pid
"""
def get_all_connected_custom_tg02_printer_elements():
    return usb.core.find(idVendor=CustomTG02.VENDOR_ID, idProduct=CustomTG02.PRODUCT_ID, find_all=True)

"""
Searches for a list of all connected reliance printers. This is done by searching for matching vid and pid
"""
def get_all_connected_reliance_printer_elements():
    return usb.core.find(idVendor=ReliancePrinter.VENDOR_ID, idProduct=ReliancePrinter.PRODUCT_ID, find_all=True)

"""
Searches for a list of a connected phoenix printers. This is done by searching for matching vid and pid
"""
def get_all_connected_pyramid_printer_elements():
    return usb.core.find(idVendor=PyramidPrinter.VENDOR_ID, idProduct=PyramidPrinter.PRODUCT_ID, find_all=True)


##End Retrieve device method
