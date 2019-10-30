#import external lib
import setuptools

#import std lib
from time import sleep
import os
from sys import exit

#import internal project lib
import DragonMasterDeviceManager


DEVICE_MANAGER_VERSION = "2.0.0"

os.system("sudo ufw allow " + str(DragonMasterDeviceManager.TCPManager.SEND_PORT))#allows access to the port if it is currently firewalled
os.system("sudo ufw allow " + str(DragonMasterDeviceManager.TCPManager.RECEIVE_PORT))#allows access to the port if it is currently firewalled

print ("Launching Device Manager v" + DEVICE_MANAGER_VERSION)
print 

deviceManager = DragonMasterDeviceManager.DragonMasterDeviceManager()



while (True):

    sleep(.5)