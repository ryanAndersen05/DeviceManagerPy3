#import external lib
import setuptools

#import std lib
from time import sleep
import os
from sys import exit

#import internal project lib
import DragonMasterDeviceManager



deviceManager = DragonMasterDeviceManager.DragonMasterDeviceManager()


while (True):

    sleep(5)