"""
This module contains some flows for The Ohio State University DMZ
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.addresses import IPAddr, EthAddr
import pox.lib.packet as pkt

log = core.getLogger()
packet_id = 0


class DMZFlows(object):
    def __init__(self, connection):
        # Switch we'll be adding DMZFlows to
        self.connection = connection

        # We want to hear PacketIn messages, so we listen
        # to the connection
        connection.addListeners(self)

        #Static flows

        #Missouri Management MAC to Gateway
        self.connection.send(of.ofp_flow_mod(match=of.ofp_match(dl_src=EthAddr("74:8e:f8:fc:6a:00")),
                                             priority=900,
                                             action=[of.ofp_action_vlan_vid(vlan_vid=350),
                                                     of.ofp_action_output(port=1)]))

        #Missouri Management IP to Gateway
        self.connection.send(of.ofp_flow_mod(match=of.ofp_match(dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_src="128.206.117.124/32"),
                                             priority=900,
                                             action=[of.ofp_action_vlan_vid(vlan_vid=350),
                                                     of.ofp_action_output(port=1)]))

        #DTN2 MAC Inbound
        self.connection.send(of.ofp_flow_mod(match=of.ofp_match(in_port=1,
                                                                dl_dst=EthAddr("00:02:c9:1f:d4:60")),
                                             priority=900,
                                             action=[of.ofp_action_strip_vlan(),
                                                     of.ofp_action_output(port=3)]))

        #DTN2 outbound to DTN1
        self.connection.send(of.ofp_flow_mod(match=of.ofp_match(in_port=3,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_dst="128.146.162.35/32"),
                                             priority=800,
                                             action=[of.ofp_action_dl_addr.set_dst(EthAddr("00:02:c9:1f:d1:60")),
                                                     of.ofp_action_vlan_vid(vlan_vid=1751),
                                                     of.ofp_action_output(port=1)]))

        #DTN2 MAC to Gateway
        self.connection.send(of.ofp_flow_mod(match=of.ofp_match(in_port=3,
                                                                dl_src=EthAddr("00:02:c9:1f:d4:60")),
                                             priority=700,
                                             action=[of.ofp_action_vlan_vid(vlan_vid=350),
                                                     of.ofp_action_output(port=1)]))




class DMZSwitch(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Switch %s has come up.", dpid_to_str(event.dpid))
        DMZFlows(event.connection)


def launch():
    core.registerNew(DMZSwitch)