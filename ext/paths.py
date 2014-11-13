"""
This module contains some flows for The Ohio State University DMZ
"""

import json
from collections import defaultdict, OrderedDict

from flask import Flask, jsonify

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.addresses import EthAddr
from pox.openflow.of_json import dict_to_flow_mod
import settings
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
import threading


log = core.getLogger()
packet_id = 0
installed_flows = []
app = Flask(__name__)


def start_tornado(*args, **kwargs):
    http_server = HTTPServer(WSGIContainer(app))
    http_server.listen(5000, address="0.0.0.0")
    log.debug("Starting Tornado")
    IOLoop.instance().start()
    log.debug("Tornado finished")

t = threading.Thread(target=start_tornado)


def stop_tornado():
    ioloop = IOLoop.instance()
    ioloop.add_callback(lambda x: x.stop(), ioloop)
    log.debug("Asked Tornado to exit")


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
                    setattr(match, key, str(flow[match_map[key][1]]))
        except Exception as e:
            print key, e
    action_map = OrderedDict([('POP_VLAN', [None, of.ofp_action_strip_vlan()]), ('SET_VLAN_ID', ['int', of.ofp_action_vlan_vid]),
                              ('SET_DL_DST', ['EthAddr', of.ofp_action_dl_addr]), ('CONTROLLER', [None, of.ofp_action_output]),
                              ('OUTPUT', ['int', of.ofp_action_output])])
    actions = []
    if flow['actions']:
        for key in action_map.keys():
            matching = [s for s in flow['actions'] if key in s]
            if matching:
                if key is 'POP_VLAN':
                    actions.append(action_map[key][1])
                elif key is 'SET_DL_DST':
                    data = matching[0].split('=')[1]
                    action = action_map[key][1].set_dst(EthAddr(data))
                    actions.append(action)
                elif key is 'SET_VLAN_ID':
                    data = int(matching[0].split('=')[1])
                    action = action_map[key][1](vlan_vid=data)
                    actions.append(action)
                elif key is 'CONTROLLER':
                    action = action_map[key][1](port=of.OFPP_CONTROLLER)
                    actions.append(action)
                elif key is 'OUTPUT':
                    data = int(matching[0].split('=')[1])
                    action = action_map[key][1](port=data)
                    actions.append(action)
    priority = int(flow['priority'])
    flow_mod = {'match': match, 'priority': priority, 'actions': actions, 'name': flow['name']}
    return flow_mod


def mod_flow(connection, flow_mod):
    log.debug('Installing %s flow' % flow_mod['name'])
    try:
        connection.send(of.ofp_flow_mod(match=flow_mod['match'], priority=flow_mod['priority'], action=flow_mod['actions']))
    except Exception as e:
        print e
        print "match: %s" % flow_mod['match']
        print "priority: %s" % flow_mod['priority']
        print "actions: %s" % flow_mod['actions']

@app.route('/dmz/api/v1.0/saved/flows', methods=['GET'])
def get_flows():
    flows = []
    for var in dir(settings):
        if var.startswith("osu"):
            flows.append(settings.__dict__[var])
            flows.append(str(flow_adapter(settings.__dict__[var])))
    return jsonify({'flows': flows})

@app.route('/dmz/api/v1.0/installed/flows', methods=['GET'])
def get_flows():
    return jsonify({'flows': installed_flows})

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
                flow = flow_adapter(settings.__dict__[var])
                mod_flow(self.connection, flow)
                installed_flows.append(flow)


class DMZSwitch(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Switch %s has come up.", dpid_to_str(event.dpid))
        DMZFlows(event.connection)

    def _handle_ConnectionDown(self, event):
        log.debug("DMZSwitch stopping tornado")
        stop_tornado()
        t.join()


def launch():
    core.registerNew(DMZSwitch)
    t.start()
