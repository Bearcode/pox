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
import settings
from tornado.wsgi import WSGIContainer
from tornado.httpserver import HTTPServer
from tornado.ioloop import IOLoop
import threading
import os

from client import OpenDaylightClient

client = OpenDaylightClient()

log = core.getLogger()
packet_id = 0
installed_flows = []
saved_flows = []
app = Flask(__name__)


def start_tornado(*args, **kwargs):
    if settings.ssl:
        ssl_options = {"certfile": os.path.join(".ssl", "server.crt"), "keyfile": os.path.join(".ssl", "server.key")}
    else:
        ssl_options = None
    http_server = HTTPServer(WSGIContainer(app), ssl_options=ssl_options)
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
    return {'name': flow['name'], 'object': flow_mod, 'json': flow}


def mod_flow(flow_mod, remove=False):
    try:
        for connection in core.openflow.connections:
            if dpid_to_str(connection.dpid) == flow_mod['json']['node']['id']:
                if not remove:
                    log.debug('Installing %s flow' % flow_mod['name'])
                    connection.send(of.ofp_flow_mod(match=flow_mod['object']['match'], priority=flow_mod['object']['priority'],
                                                    action=flow_mod['object']['actions']))
                else:
                    log.debug("Removing %s flow" % flow_mod['name'])
                    connection.send(of.ofp_flow_mod(match=flow_mod['object']['match'], priority=flow_mod['object']['priority'],
                                                    action=flow_mod['object']['actions'], command=of.OFPFC_DELETE))
            else:
                log.debug('connection: %s node: %s' % (dpid_to_str(connection.dpid), flow_mod['json']['node']['id']))

    except Exception as e:
        print e
        print "match: %s" % flow_mod['object']['match']
        print "priority: %s" % flow_mod['object']['priority']
        print "actions: %s" % flow_mod['object']['actions']


@app.route('/dmz/api/v1.0/saved/flows/<name>', methods=['GET'])
def get_saved_flows(name):
    name = str(name)
    flows = []
    if name == 'all':

        for flow in saved_flows:
            flows.append(flow['json'])
    else:
        named_flow = (item for item in saved_flows if item["name"] == name).next()
        flows.append(named_flow['json'])
    return jsonify({'flows': flows})



@app.route('/dmz/api/v1.0/installed/flows', methods=['GET'])
def get_installed_flows():
    flows = []
    for flow in installed_flows:
        flows.append(flow['json'])
    return jsonify({'flows': flows})


@app.route('/dmz/api/v1.0/installed/flows/remove/<name>', methods=['get'])
def remove_flow_named(name):
    name = str(name)
    if name == 'all':
        msg = of.ofp_flow_mod(command=of.OFPFC_DELETE)
        for connection in core.openflow.connections: # _connections.values() before betta
            connection.send(msg)
            log.debug("Clearing all flows from %s." % (dpid_to_str(connection.dpid),))
        del installed_flows[:]
    else:
        named_flow = (item for item in saved_flows if item["name"] == name).next()
        mod_flow(named_flow, remove=True)
        installed_flows[:] = [d for d in installed_flows if d.get('name') != name]
        if name == 'MizzouIPout':
            client.delete_flow(settings.mu_flow_6['node']['id'], settings.mu_flow_6['name'])
    return get_installed_flows()


@app.route('/dmz/api/v1.0/installed/flows/add/<name>', methods=['get'])
def add_flow_named(name):
    name = str(name)
    if name == 'all':
        for flow in saved_flows:
            mod_flow(flow)
            installed_flows.append(flow)
    else:
        named_flow = (item for item in saved_flows if item["name"] == name).next()
        mod_flow(named_flow)
        installed_flows.append(named_flow)
        if name == 'MizzouIPout':
            client.add_flow(settings.mu_flow_6)
    return get_installed_flows()


class DMZFlows(object):
    def __init__(self, connection):
        # Switch we'll be adding DMZFlows to
        self.connection = connection

        # We want to hear PacketIn messages, so we listen
        # to the connection
        connection.addListeners(self)

        #Static flows
        for flow in saved_flows:
            mod_flow(flow)
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
    for var in dir(settings):
        if var.startswith("osu"):
            flow = flow_adapter(settings.__dict__[var])
            saved_flows.append(flow)
    t.start()
    core.registerNew(DMZSwitch)
