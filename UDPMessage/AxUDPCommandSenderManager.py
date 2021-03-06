#!/usr/bin/python3

from UDPMessage.AxUDPCommandSender import AxUDPCommandSender;
from UDPMessage.UDPHelper import UDPHelper;

class AxUDPCommandSenderManager(object):
    """Manages all \ref AxUDPCommandSender"""

    #Always just one
    AxUDPCommandSenders = {};

    def __init__(self, magic):
        self.magic = magic;
        pass;    

    def get_sender_for_device(self, mac_address):
        return AxUDPCommandSenderManager.AxUDPCommandSenders[bytes(mac_address)];

    def device_lookup(self, mac_address):
        if(self.device_exists(mac_address)):
            return True;
        else:
            messages = UDPHelper.fill_devices(self.magic);

            for info in messages:
                self.add_or_update_device_address(info.RemoteIpAddress, info.MacAddress, info.iface);

            if(self.device_exists(mac_address)):
                return True;
            else:
                return False;

    def device_exists(self, mac_address):
        return bytes(mac_address) in AxUDPCommandSenderManager.AxUDPCommandSenders;

    def add_or_update_device_address(self, remote_ip_address, mac_address, iface):
        if(self.device_exists(mac_address)):
            AxUDPCommandSenderManager.AxUDPCommandSenders[bytes(mac_address)].udp_helper.target_ip = remote_ip_address;
        else:
            AxUDPCommandSenderManager.AxUDPCommandSenders[bytes(mac_address)] = AxUDPCommandSender(remote_ip_address, iface, self.magic);
