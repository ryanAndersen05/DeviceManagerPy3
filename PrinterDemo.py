"""
Run this script to print a test voucher ticket. This will be a demonstration of all the features we would like to be present
in our Dragon's Ascent game.

After callling this scirpt, it should find all connected phoneix printers a print a voucher ticket to each
if you have any questions, please contact Ryan Andersen at 404-643-1783
"""
import usb.core
import usb.util
import datetime
import os

from escpos.printer import Usb
from escpos.constants import RT_STATUS_ONLINE, RT_MASK_ONLINE
from escpos.constants import RT_STATUS_PAPER, RT_MASK_PAPER, RT_MASK_LOWPAPER, RT_MASK_NOPAPER




#Returns a list of all phoenix printers
def find_all_connected_printers(vid, pid):
    return usb.core.find(idVendor=vid, idProduct=pid, find_all=True)


def set_string_length_multiple(string1, string2, lengthOfString = 60, spacingChar = ' '):
    remainingLength = lengthOfString - len(string1) - len(string2)

    if remainingLength > 0:
        return string1 + (spacingChar * remainingLength) + string2
    else:
        return string1 + string2

#Minimum class representation of our Phoenix printer class
class PhoenixPrinter:
    VENDOR_ID = 0x0425
    PRODUCT_ID = 0x0412
    IN_EP = 0x81
    OUT_EP = 0x02


    LOCATION_NAME = "PlaceHolder"
    MACHINE_NUMBER = "00001"
    DRAGON_MASTER_PNG_PATH = os.path.join(os.path.dirname(os.path.realpath(__file__)), "DragonMaster.png")

    def __init__(self, usbElememt):
        self.printerObject = Usb(idVendor=PhoenixPrinter.VENDOR_ID, idProduct=PhoenixPrinter.PRODUCT_ID, in_ep=PhoenixPrinter.IN_EP, out_ep=PhoenixPrinter.OUT_EP)
        self.printerObject.device = usbElememt
        return


    def print_test_ticket(self):
        totalCreditsWon = "0.00"
        playerStation = "0"
        validationNumber = "0"
        TerminalID = "000000"
        dateTimeOfPrint = None
        versionNumber = "v9999 101.3"
        try:

            
            if dateTimeOfPrint == None:#An older version of the game may not provide the datetime of the print. This probably won't be an issue, but just in case....
                dateTimeOfPrint = datetime.datetime.now()
                # print ("Date Time was None, defaulting to the current time on our system clock")
            self.printerObject.set(align='center', font='b', height=12, bold=False)
            
            self.printerObject.set(align='center', font='b', height=12, bold=False)
            self.printerObject.textln("THANKS FOR PLAYING")
            self.printerObject.textln("VALID ON DATE OF \nISSUE ONLY!")
            self.printerObject.textln('========================')
            self.printerObject.set(align='center', font='b', height=12, bold=True)  # Align text
            self.printerObject.textln(PhoenixPrinter.LOCATION_NAME)
            self.printerObject.set(align='center', font='b', height=12, bold=False)
            self.printerObject.textln('========================')

            self.printerObject.set(align='center', font='b', height=12, bold=False)
            self.printerObject.textln(versionNumber)
            self.printerObject.textln("TID: " + TerminalID)
            self.printerObject.textln('VOUCHER TICKET')
            self.printerObject.textln(dateTimeOfPrint.strftime("%m/%d/%y, %I:%M:%S %p"))

            self.printerObject.set(align='center', font='b', height=24, bold=True)
            self.printerObject.textln('=' * 24)
            
            self.printerObject.set(align='center', font='b', height=12, bold=False)

            self.printerObject.textln(set_string_length_multiple("Machine", PhoenixPrinter.MACHINE_NUMBER, 24, ' ')) # Print Machine Number.
            self.printerObject.textln(set_string_length_multiple("Station", playerStation, 24, ' '))

            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.textln(' ')


            self.printerObject.set(align='center', font='b', height=12, bold=True)
            
            self.printerObject.textln(set_string_length_multiple('REDEEM', '$' + str(totalCreditsWon), 24)) # Print the amount to be redeemed.

            qrData = "$"+ totalCreditsWon + " " + dateTimeOfPrint.strftime('%I:%M:%S %p  %x')
            self.printerObject.set(align='center', font='b', height=12)
            self.printerObject.qr(content=qrData, size=8) # Print the QR code to be scanned. We need to figure out the content of these codes.

            self.printerObject.set(align='center', font='b', height=12, bold=False)

            self.printerObject.textln(set_string_length_multiple("VALIDATION: ", validationNumber, 24))#Validation number.

            self.printerObject.ln(1)
            try:
                self.printerObject.image(PhoenixPrinter.DRAGON_MASTER_PNG_PATH, high_density_horizontal=True, high_density_vertical=True)  # Dragon Master Image.
            except Exception as e:
                print ("There was an error when trying to read the image 'DragonMaster.png'")
                print (e)
                # self.dragonMasterDeviceManager.add_event_to_send(DragonMasterDeviceManager.DragonMasterDeviceManager.PRINT_ERROR_EVENT, self.get_player_station_hash())
                self.printerObject.textln("Dragon's Ascent")
                self.printerObject.textln('=' * 24)
            self.printerObject.textln("VOID IF MUTILATED\nVAL# 1522789371186\n_" + versionNumber + "_\n2017-2019 ALL RIGHTS RESERVED")

            self.printerObject.ln(0)

            self.printerObject.cut(feed=True)# Cut the page for removal.

        except Exception as e:
            print ("Printer Exception: " + str(e))
            return


        return





##############################################################################################

listOfAllConnectedPrinters = find_all_connected_printers(PhoenixPrinter.VENDOR_ID, PhoenixPrinter.PRODUCT_ID)
for printer in listOfAllConnectedPrinters:
    phoenixPrinter = PhoenixPrinter(printer)
    phoenixPrinter.print_test_ticket()
