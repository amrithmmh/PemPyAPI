#!/usr/bin/python3

# Copyright (c) 2017 Matija Mazalin
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in
# all copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN
# THE SOFTWARE.

"""Thread safe robot interface."""

__author__ = "Matija Mazalin"
__email__ = "matija.mazalin@abrantix.com"
__license__ = "MIT"

from Robot.PinRobot import PinRobot;
from Rest.RestfulThreaded import RESTfulThreadedServer;
from os.path import join;
from Parsers.ParseXmlRobotConfiguration import ParseXmlRobotConfiguration, RobotConfiguration;
from Exception.Exception import Error, ConnectionError, InputError, ParseError, DestinationNotFoundError, DeviceStateError;
import json;
import argparse;
from SQL.Statistics import Statistics;
import logging;
import traceback;
from AxHw.CardMultiplexer import CardMultiplexer;
from AxHw.CardMagstriper import CardMagstriper;

#----------------------------------------------------------------------------------------------------------------#

__major__ = 1
__minor__ = 5
__service__ = 0
__build__ = 51
__path = "ConfigRest"

__intro__= (
    "AX Robot Integration Layer\n"
    "Version {}.{}.{}.{}\n" 
    "Copyright (C) {} - {} Abrantix AG\n"
    "{}".format(__major__, __minor__, __service__, __build__, 2015, 2018, "#" * 50)
    )

#----------------------------------------------------------------------------------------------------------------#

def main():

    args = EnableAndParseArguments()
  
    config = args.config
    port = int(args.port)
        
    enable_statistics=args.enable_statistics
    empower = args.empower_card

    SetLoggingLevel(args)

    print(__intro__)

    print("Initialising...")

    try:
        (robot_conf_list, mux_conf_list, mag_conf_list) = ParseXmlRobotConfiguration.parseXml(config)

        device_list = {}
        error = 0

        for key, robotConfiguration in robot_conf_list.items():
             try:
                robot = PinRobot(enable_statistics, empower)

                if(False is RobotInitialisation(robot, robotConfiguration)):
                    error += 1
                    continue

                device_list.update({key: robot})
             except DeviceStateError:
                pass;


        for key, mux_configuration in mux_conf_list.items():
            mux = CardMultiplexer(mux_configuration.mac_address, enable_statistics)

            if(False is MuxInitialization(mux, mux_configuration)):
                error += 1
                continue

            device_list.update({key: mux})

        for key, mag_configuration in mag_conf_list.items():
            mag = CardMagstriper(mag_configuration.mac_address, enable_statistics)

            if(False is MagInitialization(mag, mag_configuration)):
                error += 1
                continue

            device_list.update({key: mag})

        if(not device_list):
            logging.critical("Fatal error, device list is empty!");
            raise Error("", "Fatal error, device list is empty!");

        logging.info("Initialization success! Warnings: {}".format(error))

        StartRestServer(doPostWork, doGetWork, device_list, port)

    except Error as e:
        traceback.print_exc()

#---------------------------------------------------------------------------------------------------------------#

def SetLoggingLevel(args):
    FORMAT = "%(asctime)-15s %(levelname)s: %(message)s"

    if(args.debug):
        logging.basicConfig(format=FORMAT, level=logging.DEBUG)
    elif(args.verbose):
        logging.basicConfig(format=FORMAT, level=logging.INFO)
    else:
        logging.basicConfig(format=FORMAT, level=logging.WARNING)

#------------------------------------------------------------------------------------------------------------------------#

def EnableAndParseArguments():
    parser = argparse.ArgumentParser(description="AX Robot Integration Layer v{}.{}.{}".format(__major__, __minor__, __service__))
    parser.add_argument("-c", "--config", default=join("Assets", "EntryConfiguration.xml"), help="path to entry configuration xml", required=False)
    parser.add_argument("-p", "--port", default='8000', help="port for the http listener, default is 8000", required=False)
    parser.add_argument("--enable-statistics", nargs='?', const=True, default=False, help="enable tracking of the button press to the local DB", required=False)
    parser.add_argument("-v", "--verbose", nargs='?', const=True, default=False, help="increase trace verbosity to the INFO level", required=False)
    parser.add_argument("-d", "--debug", nargs='?', const=True, default=False, help="increase trace verbosity to the DEBUG level", required=False)
    parser.add_argument("--empower-card", nargs='?', const=True, default=False, help="increase the current on the card for the terminals with tighter card reader", required=False)

    return parser.parse_args()

#------------------------------------------------------------------------------------------------------------------------#

def MuxInitialization(mux : CardMultiplexer, configuration):
    if(False is mux.device_lookup()):
        return False

    if(False is mux.initialize_device(join(__path, configuration.Layout))):
        return False

    return True

#------------------------------------------------------------------------------------------------------------------------#

def MagInitialization(mag : CardMagstriper, configuration):
    if(False is mag.device_lookup()):
        return False

    if(False is mag.initialize_device(join(__path, configuration.Layout))):
        return False

    return True

#---------------------------------------------------------------------------------------------------------------#

def RobotInitialisation(robot : PinRobot, configuration):
    """Initializes the robot, and perfoms home"""
    try:
        if(False is robot.InitializeTerminal(join(__path, configuration.Layout))):
            logging.warning(configuration.Layout + ": Initialization of robot failed, skip...")
            return False

        if(False is robot.InitializeConnection(configuration.IP, int(configuration.Port))):
            logging.warning(configuration.Layout + ": robot not reachable, skip...")
            return False

        if (False is robot.send_command("HOME")):
            logging.warning(configuration.Layout + ": robot calibration could not be executed")
            return False;

    finally:
        robot.close_connection()

    return True

#---------------------------------------------------------------------------------------------------------------#

def StartRestServer(postWork, getWork, robotList, port):
    server = RESTfulThreadedServer(postWork, getWork, robotList, port)
    server.start()
    server.waitForThread()

#---------------------------------------------------------------------------------------------------------------#

def executeCommands(device, commands, key):
    """Execute a request, protected by a lock. Every request on a single robot 
    must be processed till the end before the next may be processed
    """
    try:
        device.mutex.acquire()

        if(False is device.connect()):
            logging.error("robot '{}' is unreachable".format(key))
            raise ConnectionError("", "could not connect to the robot: " + key)

        for command in commands:
            if(True is device.send_command(command)):
                logging.info("{}: execution of {} was succesful".format(key, command))
                device.UpdateTable(key, command)
            else:
                logging.warning("could not execute '{}' on {}. Abort further execution".format(command, key))
                raise InputError("", key + ": could not execute: " + command)

    finally:
        device.close_connection()
        device.mutex.release()

#-----------------------------------------------------------------------------------------------------------------#

def getRequest(jsonString):
    try:
        request = json.loads(jsonString)
    except json.JSONDecodeError:
        logging.error("json could not be loaded:\n" + jsonString)
        raise ParseError("", "json could not be parsed")

    return request

#----------------------------------------------------------------------------------------------------------------#   

def doPostWork(jsonString, robotList):
    
    request = getRequest(jsonString)
    try:
        key = request['id']

        if(key not in robotList):
            logging.error("robot {} not in list".format(key))
            raise DestinationNotFoundError("" , key + ": robot not found")

        executeCommands(robotList[key], request['commands'], key)
    except KeyError as e:
        raise ParseError("", str(e));
    return True

#----------------------------------------------------------------------------------------------------------------#
        
def doGetWork(robotList):
    l = list(robotList.keys())
    robot_object = {'id' : l}
    return json.dumps(robot_object)

#----------------------------------------------------------------------------------------------------------------#

main()
