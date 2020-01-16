#import external lib
import setuptools

#import std lib
from time import sleep
import os
from sys import exit

#import internal project lib
import DragonMasterDeviceManager


"""
@author Ryan Andersen, EQ Games, Phone #: (404-643-1783)
email: ryan@eq-games.com
"""
################################################################################################################################################

os.system("sudo ufw allow " + str(DragonMasterDeviceManager.TCPManager.SEND_PORT))#allows access to the port if it is currently firewalled
os.system("sudo ufw allow " + str(DragonMasterDeviceManager.TCPManager.RECEIVE_PORT))#allows access to the port if it is currently firewalled

print ("Launching Device Manager v" + DragonMasterDeviceManager.DragonMasterDeviceManager.VERSION)

deviceManager = DragonMasterDeviceManager.DragonMasterDeviceManager()


#Main thread of our game is here. When we want to fully kill our application, we should exit the loop by setting the Kill_device_manager_application to True
while (not DragonMasterDeviceManager.DragonMasterDeviceManager.KILL_DEVICE_MANAGER_APPLICATION): #We can force exit the application by setting this value to true

    sleep(.5)

#Main Loop has been terminated. If the application continues to run long after this point, then more than likely there is a process that is not set as a background process and is still running
print ("Terminated Device Manager Application")