#import external lib
import setuptools

#import std lib
from time import sleep
import os
from sys import exit

#import internal project lib
import DragonMasterDeviceManager



os.system("sudo ufw allow " + str(DragonMasterDeviceManager.TCPManager.SEND_PORT))#allows access to the port if it is currently firewalled
os.system("sudo ufw allow " + str(DragonMasterDeviceManager.TCPManager.RECEIVE_PORT))#allows access to the port if it is currently firewalled

print ("Launching Device Manager v" + DragonMasterDeviceManager.DragonMasterDeviceManager.VERSION)

deviceManager = DragonMasterDeviceManager.DragonMasterDeviceManager()



while (not DragonMasterDeviceManager.DragonMasterDeviceManager.KILL_DEVICE_MANAGER_APPLICATION): #We can force exit the application by setting this value to true

    sleep(.5)

print ("Terminated Device Manager Application")