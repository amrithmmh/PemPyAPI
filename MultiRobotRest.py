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

from PinRobot import PinRobot
from RestfulThreaded import RESTfulThreadedServer
from os.path import join
from ParseXmlRobotConfiguration import ParseXmlRobotConfiguration, RobotConfiguration
from Exception import Error, ConnectionError, InputError, ParseError, DestinationNotFoundError
import json
import argparse
from Statistics import Statistics
import logging


def main():

    FORMAT = "%(asctime)-15s %(levelname)s: %(message)s"
    _path = "ConfigRest"

    parser = argparse.ArgumentParser(description='PIN Robot Rest API')
    parser.add_argument("-c", "--config", default=join("Assets", "EntryConfiguration.xml"),help="path to entry configuration xml", required=False)
    parser.add_argument("-p", "--port", default='8000', help="port for the http listener", required=False)
    parser.add_argument("--enable-statistics", nargs='?', const=True, default=False, help="enable tracking of the button press", required=False)
    parser.add_argument("-v", "--verbose", nargs='?', const=True, default=False, help="increase verbosity to the INFO level", required=False)
    parser.add_argument("-d", "--debug", nargs='?', const=True, default=False, help="increase verbosity to the DEBUG level", required=False)
    args = (parser.parse_args())

  
    config = args.config
    port = int(args.port);
        
    enable_statistics=args.enable_statistics

    if(args.debug):
        logging.basicConfig(format=FORMAT, level=logging.DEBUG);
    elif(args.verbose):
        logging.basicConfig(format=FORMAT, level=logging.INFO);
    else:
        logging.basicConfig(format=FORMAT, level=logging.WARNING);

    try:
        ConfigurationList = ParseXmlRobotConfiguration.parseXml(config)
        RobotList = {}

        for key, value in ConfigurationList.items():
             robot = PinRobot(enable_statistics)
             if(False is robot.InitializeTerminal(join(_path, value.Layout))):
                logging.warning(value.Layout + ": Initialization failed, skip...")
                continue

             if(False is robot.InitializeConnection(value.IP, int(value.Port))):
                logging.warning(value.Layout + ": robot not reachable, skip...")
                continue

             if (False is robot.SendCommand("HOME")):
                 logging.warning(value.Layout + ": robot calibration could not be executed");

             robot.CloseConnection();


             RobotList.update({key:robot})

        if(not RobotList):
            logging.critical(" Fatal error, robot list is empty...")
            raise

        server = RESTfulThreadedServer(doPostWork, doGetWork, RobotList, port)
        server.start()
        server.waitForThread()
    except Error as e:
        print(e);

def str2bool(v):
    if v.lower() in ('yes', 'true', 't', 'y', '1'):
        return True
    elif v.lower() in ('no', 'false', 'f', 'n', '0'):
        return False
    else:
        raise argparse.ArgumentTypeError('Boolean value expected.')

#------------------------------------------------------------------------------------------------------------------------#

def executeCommands(robot, commands, key):

    try:
        robot.mutex.acquire();
        if(False is robot.Connect()):
            logging.error("robot '{}' is unreachable".format(key));
            raise ConnectionError("", "could not connect to the robot" + key);

        for command in commands:
            if(True is robot.SendCommand(command)):
                logging.info("{} execution of {} was succesful".format(key, command));
                robot.UpdateTable(key, command)
            else:
                logging.warning("could not execute '{}' on {}. Abort further execution".format(command, key));
                raise InputError("", key + ": could not execute " + command); 
    finally:
        robot.CloseConnection();
        robot.mutex.release()


#------------------------------------------------------------------------------------------------------------------------#

def getRequest(jsonString):
    try:
        request = json.loads(jsonString)
    except json.JSONDecodeError:
        logging.error("json could not be loaded:\n" + jsonString)
        raise ParseError("", "json could not be parsed");

    return request

#------------------------------------------------------------------------------------------------------------------------#   

def doPostWork(jsonString, robotList):
    
    request = getRequest(jsonString);

    key = request['id'];
    if(key not in robotList):
        logging.error("robot {} not in list".format(key))
        raise DestinationNotFoundError("" , key + ": robot not found");

    executeCommands(robotList[key], request['commands'], key);
        
    return True


#------------------------------------------------------------------------------------------------------------------------#
        
def doGetWork(robotList):
    l = list(robotList.keys())
    robot_object = {'id' : l}
    return json.dumps(robot_object)

main()
