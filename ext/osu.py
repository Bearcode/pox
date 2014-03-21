"""
This module contains some flows for The Ohio State University DMZ
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str

log = core.getLogger()


class DMZFlows(object):
    def __init__(self, connection):
        # Switch we'll be adding DMZFlows to
        self.connection = connection

        # We want to hear PacketIn messages, so we listen
        # to the connection
        connection.addListeners(self)

        #Static flows
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=20),
                                             priority=42,
                                             match=of.ofp_match(dl_type=0x800,
                                                                nw_dst="128.146.162.35")))


class DMZSwitch(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Switch %s has come up.", dpid_to_str(event.dpid))
        DMZFlows(event.connection)


def launch():
    core.registerNew(DMZSwitch)