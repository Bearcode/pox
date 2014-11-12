"""
This module contains some flows for The Ohio State University DMZ
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.addresses import EthAddr
import pox.lib.packet as pkt
from flask import Flask, jsonify
import settings

log = core.getLogger()
packet_id = 0

app = Flask(__name__)

@app.route('/todo/api/v1.0/flows', methods=['GET'])
def get_flows():
    flows = []
    for var in dir(settings):
            if var.startswith("osu"):
                flows.append(settings.__dict__[var])
    return jsonify({'flows': flows})

class DMZFlows(object):
    def __init__(self, connection):
        # Switch we'll be adding DMZFlows to
        self.connection = connection

        # We want to hear PacketIn messages, so we listen
        # to the connection
        connection.addListeners(self)

        #Static flows
        for var in dir(settings):
            if var.startswith("osu"):
                print settings.__dict__[var]


class DMZSwitch(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Switch %s has come up.", dpid_to_str(event.dpid))
        DMZFlows(event.connection)


def launch(verbose=False, max_length=110, full_packets=True,
           hide=False, show=False):
    core.registerNew(DMZSwitch)
    app.run(debug=True)
