"""
This module contains some flows for The Ohio State University DMZ
"""

import json
from collections import defaultdict

from flask import Flask, jsonify

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.addresses import EthAddr
import settings


log = core.getLogger()
packet_id = 0

app = Flask(__name__)


def flow_adapter(flow_dict):
    if type(flow_dict) is str:
        flow_dict = json.loads(flow_dict)
    flow = defaultdict(lambda: None)
    flow.update(flow_dict)
    match_map = {'in_port': ['int', 'ingressPort'], 'dl_type': ['hex', 'etherType'], 'dl_src': ['EthAddr', 'dlSrc'],
                 'dl_dst': ['EthAddr', 'dlDst'], 'dl_vlan': ['int', 'vlanId'], 'nw_src': ['str', 'nwSrc'],
                 'nw_dst': ['str', 'nwDst']}
    match = of.ofp_match()
    for key in match_map:
        try:
            if match_map[key][1] in flow.keys():
                if match_map[key][0] is 'int':
                    setattr(match, key, int(flow[match_map[key][1]]))
                elif match_map[key][0] is 'hex':
                    setattr(match, key, int(flow[match_map[key][1]], 16))
                elif match_map[key][0] is 'EthAddr':
                    setattr(match, key, EthAddr(flow[match_map[key][1]]))
                else:
                    setattr(match, key, flow[match_map[key][1]])
        except Exception as e:
            print key, e

    return match


@app.route('/dmz/api/v1.0/flows', methods=['GET'])
def get_flows():
    flows = []
    for var in dir(settings):
        if var.startswith("osu"):
            flows.append(settings.__dict__[var])
            flows.append(str(flow_adapter(settings.__dict__[var])))
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
