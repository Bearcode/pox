"""
This module contains some flows for The Ohio State University DMZ
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr
import pox.lib.packet as pkt

log = core.getLogger()


class DMZFlows(object):
    def __init__(self, connection):
        # Switch we'll be adding DMZFlows to
        self.connection = connection

        # We want to hear PacketIn messages, so we listen
        # to the connection
        connection.addListeners(self)

        #Static flows
        #Drop PVST+ traffic
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_NONE),
                                             priority=9999,
                                             match=of.ofp_match(in_port=64, dl_dst=EthAddr("01:00:0c:cc:cc:cd"))))

        #Clemson Inbound to Controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=800,
                                             match=of.ofp_match(in_port=64, dl_vlan=3070)))
        #OSU DTN traffic outbound to Clemson to controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=20),
                                             priority=800,
                                             match=of.ofp_match(in_port=64,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_dst="130.127.3.192/32")))

        #MU Inbound send to OSU DTN
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=20),
                                             priority=700,
                                             match=of.ofp_match(in_port=64, dl_vlan=1751)))

        #OSU DTN traffic outbound to MU IP 128.146.162.36
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=64),
                                             priority=700,
                                             match=of.ofp_match(in_port=20, dl_type=pkt.ethernet.IP_TYPE)))

        #OSU DTN Traffic outbound to public IPs
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_strip_vlan(), of.ofp_action_output(port=61)],
                                             priority=500,
                                             match=of.ofp_match(in_port=20,
                                                                dl_vlan=1751,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_src="128.146.162.35/32")))
        #OSU DTN Traffic outbound ARP flood
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_strip_vlan(), of.ofp_action_output(of.OFPP_FLOOD)],
                                             priority=500,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.ARP_TYPE,
                                                                dl_src=(EthAddr("00:02:c9:1f:d1:60")))))

        #OSU DTN Outbound Default to Controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=2,
                                             match=of.ofp_match(in_port=20)))

        #OSU Public inbound traffic default to OSU DTN
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_vlan_vid(vlan_vid=1750),
                                                     of.ofp_action_output(port=20)],
                                             priority=1,
                                             match=of.ofp_match(in_port=61)))
        #AL2S inbound default to controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=1,
                                             match=of.ofp_match(in_port=64)))





class DMZSwitch(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Switch %s has come up.", dpid_to_str(event.dpid))
        DMZFlows(event.connection)


def launch():
    core.registerNew(DMZSwitch)