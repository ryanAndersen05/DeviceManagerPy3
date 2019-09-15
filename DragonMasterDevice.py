#std lib imports
import threading
import os
#external lib imports
import evdev
import usb.core
import usb.util
import time

from escpos.printer import Usb
#Internal project imports
import DragonMasterDeviceManager
import DragonMasterSerialDevice

"""
The Base class for all our Dragon Master Devices
"""
class DragonMasterDevice:

    def __init__(self, dragonMasterDeviceManager):
        self.playerStationID = 0
        self.dragonMasterDeviceManager = dragonMasterDeviceManager
        self.deviceParentPath = None

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

    #region override methods
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
        
        

    #endregion override methods

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


In General When using print commands in our printer we will want to send it as an array of chars. We want to make sure that the values that we send are accurate and sending it as a string seems like the most
accurate way to do this
"""
class Printer(DragonMasterDevice):
    AUDIT_TICKET = 0x05
    CODEX_TICKET = 0x04

    REPRINT_TICKET = 0x02
    TEST_TICKET = 0x01
    VOUCHER_TICKET = 0x00

    #The path of our Cross fire png image
    CROSS_FIRE_PNG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "Cross-fire.png")
    #The file path to our dragon master logo png
    DRAGON_MASTER_PNG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "DragonMaster.png")
    LOCATION_NAME = "PlaceHolder"
    MACHINE_NUMBER = "00001"

    def __init__(self, dragonMasterDeviceManager):
        super().__init__(dragonMasterDeviceManager)
        self.printerObject = None
        self.currentState = (0,0)#Tuple represents the state of the printer. (Printer Status, Paper Availability)


    # """
    # NOTE: This may not be entirely necessary. Will look into it more later
    # """
    def initialize_printers(vendorID, productID):
        # for dev in usb.core.find(find_all=True, idVendor=vendorID, idProduct=productID):
        #     #We apparently had to do this to find the printers.  Ryan doesn't know what this is.
        #     try:
        #         if not dev.is_kernel_driver_active(0):
                    
        #             dev.attach_kernel_driver(0)
        #     except:
        #         pass
        return

    """
    This method formats and prints out a cash-out ticket
    """
    def print_voucher_ticket(self, totalCreditsWon, timeTicketRedeemed, playerStation="0", validationNumber = "0", whiteSpaceUnderTicket = 10, ticketType = 0):
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

            if ticketType == Printer.REPRINT_TICKET:
                self.printerObject.textln("REPRINT")
            elif ticketType == Printer.TEST_TICKET:
                self.printerObject.textln("TEST TICKET")
            else:
                self.printerObject.textln("VOUCHER TICKET")
            
            self.printerObject.textln("STATION " + playerStation)

            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.textln('------------------------')
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple("MACH", Printer.MACHINE_NUMBER, 24, ' ')) # Machine Number.

            currentDateTime = time.strftime('%I:%M:%S %p     %x')   # Get the current date and time, this ticket was printed.
            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.textln(currentDateTime)

            self.printerObject.set(align='center', font='b', height=12, bold=True)
            if ticketType == Printer.TEST_TICKET:
                self.printerObject.textln('REDEEM             TEST')
            else:
                self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('REDEEM', '$' + str(totalCreditsWon), 24)) # Print the amount to be redeemed.

            # status = self.get_printer_state()  # The printer can hang in the qr code method. Check for any errors before attempting to print.
            #if (status != "JAMMED" and status != "PAPER OBSTRUCTED" and status != "OUT OF PAPER"):
            qrData = "$"+str(totalCreditsWon) + " " + time.strftime('%I:%M:%S %p  %x')
            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.qr(content=qrData, size=8)              # Print the QR code to be scanned. We need to figure out the content of these codes.
            #else:
            #    self.deviceManager.write_printer_state(self.parentPath)
            #    print "Printer " + str(self.printerID) + " has errored while printing"
            #    self.deviceManager.add_event_to_queue(self.deviceManager.PRINT_ERROR + "|" + self.parentPath)
            #    return

            self.printerObject.set(align='center', font='a', height=1, width=1, bold=True, custom_size=True)
            self.printerObject.textln('VALID ON DATE OF\nISSUE ONLY\n')# Validation warning.

            self.printerObject.set(align='center', font='b', height=12)
            
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple("VALIDATION: ", validationNumber, 24))#Validation number.

            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.textln('------------------------')
            #self.printerObject.textln('CFS 101.01 DM1  ' + u"\u00a9" + str(time.strftime('%Y')))   # I need to ask Chris what this means.
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple("VERSION NUMBER GOES HERE" ,u"\u00a9" + str(time.strftime('%Y')), 23))
            self.printerObject.textln('------------------------')
            self.printerObject.ln(1)

            #if (status != "JAMMED" and status != "PAPER OBSTRUCTED" and status != "OUT OF PAPER"):  # The printer can hang when printing an image. Check for any errors before attempting to print.
            try:
                self.printerObject.image(Printer.DRAGON_MASTER_PNG_PATH, high_density_horizontal=True, high_density_vertical=True)  # Dragon Master Image.
            except Exception as e:
                print ("There was an error when trying to read the image 'DragonMaster.png'")
                print (e)
                # self.deviceManager.add_event_to_queue(DragonMasterDeviceManager.PRINT_MEDIA_MISSING + "|" + self.parentPath)
                self.printerObject.textln("Dragon Master")
            self.printerObject.ln(whiteSpaceUnderTicket)
            #else:
            #    self.deviceManager.write_printer_state(self.parentPath)
            #    print "Printer " + str(self.printerID) + " has errored while printing"
            #    self.deviceManager.add_event_to_queue(self.deviceManager.PRINT_ERROR + "|" + self.parentPath)
            #    return

            self.printerObject.cut(feed=True)                                      # Cut the page for removal.

            #self.deviceManager.write_printer_state(self.parentPath)                # Send the updated state to application.
            # self.deviceManager.add_event_to_queue(self.deviceManager.PRINT_SUCCESS + "|" + self.parentPath)

        except Exception as e:
            print ("There was an error printing our Cash-Out Ticket")
            print (e)

        return



    """
    Prints and formats our audit ticket from the byte array data that we receive
    """
    def print_audit_ticket(self, auditTicketData, line_length = 32, whiteSpaceUnderTicket=7):

        '''
        auditInfoString parameter list / order (ex. auditInfoString[1] = parentDeviceKey)
        0: Event Name ("PRINTAUDIT")
        1: parentDeviceKey
        2: Player station ( 0 = Machine wide Audit, 1-8 = Player station specific)
        3: Security Level (1-5) (If security level < 5, we will not print the archive values)
        4-6: List Clear Date (Archive, Weekly, Daily)
        7-9: List Clear Time (Archive, Weekly, Daily)
        10-12: Credit In (Archive, Weekly, Daily)
        13-15: Wins Out (Archive, Weekly, Daily)
        16-18: I-O Hold (Archive, Weekly, Daily)
        19-21: Hold % (Archive, Weekly, Daily)
        22-24: Points Played (Archive, Weekly, Daily)
        25-27: Points Won (Archive, Weekly, Daily)
        28-30: P-W Earned (Archive, Weekly, Daily)
        31-33: Return % (Archive, Weekly, Daily)
        34-36: Games Played (Archive, Weekly, Daily)
        37-39: Games Won (Archive, Weekly, Daily)
        40-42: Hit % (Archive, Weekly, Daily)
        43-45: Coupon Sale (Archive, Weekly, Daily)
        46-48: Free Entry (Archive, Weekly, Daily)
        49: Current Terminal Balance
        50: Fill Time Remaining
        51: Period that will be printed
        52: Audit JSON string (Convert this to QR code)
        53: large progressive reward value
        54: small progressive reward value
        '''

        

        try:
            auditTicketString = auditTicketData.decode("utf-8")
            auditInfoString = auditTicketString.split('|')

            self.config_text()
            #Period refers to archive/weekly/daily history and will be represented as 0,1,2 respectively
            periodType = int(auditInfoString[51])
            periodName = ""
            if periodType == 0:
                periodName = 'ARCHIVE'
            elif periodType == 1:
                periodName = 'WEEKLY'
            elif periodType == 2:
                periodName = 'DAILY'


            self.printerObject.set(align='center', width=1, height=1, font='b')
            self.printerObject.textln('=' * line_length)
            self.printerObject.set(align='center', font='b', height=14, bold=True)
            self.printerObject.textln("Dragon's Ascent")
            self.printerObject.set(align='center', bold=False, height=14)
            self.printerObject.textln('A Game Of Skill')
            self.printerObject.textln('and Strategy')
            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.set(align='center', bold=True)
            #self.printerObject.textln('SKL503.07CPN     BANK1')
            self.printerObject.textln(self.dragonMasterDeviceManager.DRAGON_MASTER_VERSION_NUMBER)
            self.printerObject.textln("TID: " + auditInfoString[55])
            self.printerObject.set(align = 'center', bold=True)
            # self.printerObject.textln('Ver: ' + DragonMasterDeviceManager.DRAGON_MASTER_VERSION_NUMBER)

            if str(auditInfoString[2]) == '0':
                self.printerObject.textln("MACHINE AUDIT")
            else:
                self.printerObject.textln("PLAYER STATION #" +str(auditInfoString[2]))
            
            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)


            self.printerObject.set(align='center', font='a', height=1, bold=True)
            currentDateTime = time.strftime('%x %I:%M:%S %p')
            self.printerObject.textln(currentDateTime)
            self.printerObject.textln("ARCHIVE (LEVEL " + str(auditInfoString[3]) + ")")

            if str(auditInfoString[3]) != '5':  # If the security level is not 5, we want to print "N/A" for the archive values.
                for x in range(4, 46, 3):  # Archive values start at 4, and are present every 3rd value. (ex. 4,7,10)
                    pass
            

            
            self.printerObject.set(align='center', height=1, width=1, custom_size=False, font='b')

            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('DESCRIPT', periodName, lengthOfString=line_length, spacingChar=' '))
            self.printerObject.set(align='center', height=1, width=1, custom_size=False, font='b')
            self.printerObject.textln('=' * line_length)
            self.printerObject.line_spacing(spacing=0, divisor=360)
            
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('LSTCLRDATE', auditInfoString[4 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('LSTCLRTIME', auditInfoString[7 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('CRDT IN', '$' + auditInfoString[10 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('CRDT OUT', '$' + auditInfoString[13 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('I-O HOLD', '$' + auditInfoString[16 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('HOLD%', auditInfoString[19 + periodType] + '%', lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('PTS PLAYED', '$' + auditInfoString[22 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('POINTS WON', '$' + auditInfoString[25 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('P-W EARNED', '$' + auditInfoString[28 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('RETURN%', auditInfoString[31 + periodType] + '%', lengthOfString=line_length, spacingChar=' '))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('GAMES PLYD', auditInfoString[34 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('GAMES WON', auditInfoString[37 + periodType], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('HIT%', auditInfoString[40 + periodType] + '%', lengthOfString=line_length, spacingChar=' '))
            #self.printerObject.textln('GAMES PLYD ' + str(auditInfoString[34]) + ' ' + str(auditInfoString[35]) + '   ' + str(auditInfoString[36]))
            #self.printerObject.textln('GAMES PLYD ' + str(auditInfoString[37]) + ' ' + str(auditInfoString[38]) + '        ' + str(auditInfoString[39]))
            #self.printerObject.textln('HIT%       ' + str(auditInfoString[40]) + ' ' + str(auditInfoString[41]) + '%    ' + str( auditInfoString[42]) + '%')
            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('LG PRG', '$' + auditInfoString[53], lengthOfString=line_length, spacingChar=' '))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length_multiple('SM PRG', '$' + auditInfoString[54], lengthOfString=line_length, spacingChar=' '))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            # self.printerObject.textln(set_string_length_multiple('COUPONSALE', '$' + auditInfoString[43], lengthOfString=line_length, spacingChar=' '))
            # self.printerObject.textln(set_string_length_multiple('FREE ENTRY', '$' + auditInfoString[46], lengthOfString=line_length, spacingChar=' '))
            #self.printerObject.textln('COUPONSALE ' + str(auditInfoString[43]) + ' $' + str(auditInfoString[44]) + '    $' + str(auditInfoString[45]))
            #self.printerObject.textln('FREE ENTRY ' + str(auditInfoString[46]) + ' $' + str(auditInfoString[47]) + '   $' + str(auditInfoString[48]))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.textln('CRNT TRMNL BAL: $' + str(auditInfoString[49]))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.qr(content=auditInfoString[52], size=4)    

            self.printerObject.set(align='center')
            self.printerObject.textln('FILL/TIME REMAINING')
            self.printerObject.textln(str(auditInfoString[50]))

            self.printerObject.set(align='center', font='b')
            self.printerObject.textln('=' * line_length)

            self.printerObject.set(align='center')
            self.printerObject.textln('VOID IF MUTILATED')
            self.printerObject.textln('VAL# ' + str(1522789371186))
            self.printerObject.textln(DragonMasterDeviceManager.set_string_length(self.dragonMasterDeviceManager.DRAGON_MASTER_VERSION_NUMBER, 21, '-'))
            self.printerObject.textln(u"\u00a9" + '2017-2019 ALL RIGHTS\nRESERVED')

            self.printerObject.textln('\n' * whiteSpaceUnderTicket)#Give a little bit of white space between tickets

            # self.deviceManager.add_event_to_queue(self.deviceManager.PRINT_SUCCESS + "|" + self.parentPath)


        except Exception as e:
            print ("There was an error printing an audit ticket:" + str(e))
            # self.deviceManager.add_event_to_queue(self.deviceManager.PRINT_ERROR + "|" + self.parentPath)

        return

    """
    Prints and formats a code exchange ticket
    """
    def print_codex_ticket(self, codexTicketData, whiteSpaceUnderTicket=6):

        return

    """
    Returns the updated printer state and paper state as a tuple. These values should both be returned as byte values
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
        super().start_device(deviceElement)

        return True

    def disconnect_device(self):
        return super().disconnect_device()

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
            

        # self.parentPath = self.deviceNode.parent.parent.parent.device_path
        # self.devicePath = self.deviceNode.device_path

    def config_text(self):
        msg = '\x1b\xc1\x30'
        self.printerObject.device.write(CustomTG02.OUT_EP, msg, 1)


    def to_string(self):
        return "CustomTG02(" + ")"
    #End Override Methods
    pass

"""
Extension of our printer class. Handles special properties for our phoenix printer
"""
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
    def __init__(self, dragonMasterDeviceManager):
        super().__init__(dragonMasterDeviceManager)
        self.associatedRelianceSerial = None

    """
    The reliance start device function is in charge of both starting our reliance usb printer as well as finding the serial component of the printer
    """
    def start_device(self, deviceElement):


        self.printerObject = Usb(idVendor=ReliancePrinter.VENDOR_ID, idProduct=ReliancePrinter.PRODUCT_ID, in_ep=ReliancePrinter.IN_EP, out_ep=ReliancePrinter.OUT_EP)
        if self.printerObject == None:
            return False

        self.printerObject.device = deviceElement
        super().start_device(deviceElement)
        if self.deviceParentPath == None:
            return False

        self.associatedRelianceSerial = self.get_matching_reliance_serial(deviceElement)
        if self.associatedRelianceSerial == None:
            return False

        return True

    """
    Disconnects both the associated Reliance Serial class and disconnects this printer device
    """
    def disconnect_device(self):
        if self.associatedRelianceSerial  != None:
            self.associatedRelianceSerial.disconnect_device()
        
        return super().disconnect_device()

    """

    """
    def fetch_parent_path(self, deviceElement):
        pathString = self.port_numbers_to_usb_address(deviceElement)

        for dev in self.dragonMasterDeviceManager.deviceContext.list_devices():
            if dev.sys_name == pathString:
                return dev.parent.device_path
        return None
        

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
    def audit_ticket(self, auditInfoString):
        self.associatedRelianceSerial.retract()
        Printer.audit_ticket(self, auditInfoString, 29, 0)
        self.associatedRelianceSerial.cut()

    def print_voucher_ticket(self, totalCreditsWon, timeTicketRedeemed, playerStation='0', validationNumber='0', whiteSpaceUnderTicket=1, ticketType=0):
        self.associatedRelianceSerial.retract()
        super().print_voucher_ticket(totalCreditsWon, timeTicketRedeemed, playerStation, validationNumber, whiteSpaceUnderTicket, ticketType)
        self.associatedRelianceSerial.cut()

    def print_codex_ticket(self, codexTicketInfo, line_length =29):
        self.associatedRelianceSerial.retract()
        Printer.print_codex_ticket(self, codexTicketInfo, line_length, 0)
        self.associatedRelianceSerial.cut()
    #endregion override printer methods
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
Returns a list of all the connected custom TG02 printers. We do this by searching for a matching vid and pid
"""
def get_all_connected_custom_tg02_printer_elements():
    return usb.core.find(idVendor=CustomTG02.VENDOR_ID, idProduct=CustomTG02.PRODUCT_ID, find_all=True)

"""
Searches for a list of all connected reliance printers. This is done be searching for matching vid and pid
"""
def get_all_connected_reliance_printer_elements():
    return usb.core.find(idVendor=ReliancePrinter.VENDOR_ID, idProduct=ReliancePrinter.PRODUCT_ID, find_all=True)


##End Retrieve device method