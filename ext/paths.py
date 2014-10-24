"""
This module contains some flows for The Ohio State University DMZ
"""

from pox.core import core
import pox.openflow.libopenflow_01 as of
from pox.lib.util import dpid_to_str
from pox.lib.addresses import EthAddr
import pox.lib.packet as pkt

from pox.lib.util import dpidToStr

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
        #Drop PVST+ traffic
        self.connection.send(of.ofp_flow_mod(action=[],
                                             priority=9999,
                                             match=of.ofp_match(in_port=64, dl_dst=EthAddr("01:00:0c:cc:cc:cd"))))

        #Forward outbound Clemson ARP replies
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_vlan_vid(vlan_vid=3070),
                                                     of.ofp_action_output(port=64)],
                                             priority=801,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.ARP_TYPE,
                                                                dl_dst=EthAddr("00:24:38:9c:13:00"))))
        #Forward Clemson Inbound IP
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_strip_vlan(),
                                                     of.ofp_action_output(port=20)],
                                             priority=800,
                                             match=of.ofp_match(in_port=64, dl_vlan=3070)))

        #Forward Clemson Outbound IP
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_vlan_vid(vlan_vid=3070),
                                                     of.ofp_action_output(port=64)],
                                             priority=800,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_dst="130.127.3.192/32")))

        #MU L2 Inbound send to OSU DTN
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_strip_vlan(), of.ofp_action_output(port=20)],
                                             priority=700,
                                             match=of.ofp_match(in_port=64, dl_vlan=1751)))

        #OSU DTN traffic outbound to MU IP 128.206.117.1 to AL2S
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_dl_addr.set_dst(EthAddr("00:02:C9:1F:D4:60")),
                                                     of.ofp_action_vlan_vid(vlan_vid=1751),
                                                     of.ofp_action_output(port=64)],
                                             priority=700,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_dst="128.206.117.1/32")))

        #OSU DTN Traffic outbound to public IPs
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=61),
                                             priority=500,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_src="128.146.162.35/32")))
        #OSU DTN Traffic outbound ARP
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=61),
                                             priority=500,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.ARP_TYPE,
                                                                dl_src=(EthAddr("00:02:c9:1f:d1:60")))))

        #OSU DTN Outbound Default to Controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=2,
                                             match=of.ofp_match(in_port=20)))

        #OSU Public inbound traffic default to OSU DTN
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=20),
                                             priority=1,
                                             match=of.ofp_match(in_port=61)))
        #AL2S inbound default to controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=1,
                                             match=of.ofp_match(in_port=64)))

    log = core.getLogger()

    _verbose = None
    _max_length = None
    _types = None
    _show_by_default = None

    def _handle_PacketIn(event):
        packet = event.parsed

        show = _show_by_default
        p = packet
        while p:
            if p.__class__.__name__.lower() in _types:
                if _show_by_default:
                    # This packet is hidden
                    return
                else:
                    # This packet should be shown
                    show = True
                    break
                return
            if not hasattr(p, 'next'): break
            p = p.next

        if not show: return

        msg = dpidToStr(event.dpid) + ": "
        msg = ""
        if _verbose:
            msg += packet.dump()
        else:
            p = packet
            while p:
                if isinstance(p, basestring):
                    msg += "[%s bytes]" % (len(p),)
                    break
                msg += "[%s]" % (p.__class__.__name__,)
                p = p.next

        if _max_length:
            if len(msg) > _max_length:
                msg = msg[:_max_length - 3]
                msg += "..."
        core.getLogger("dump:" + dpidToStr(event.dpid)).debug(msg)


class DMZSwitch(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Switch %s has come up.", dpid_to_str(event.dpid))
        DMZFlows(event.connection)


def launch(verbose=False, max_length=110, full_packets=True,
           hide=False, show=False):
    core.registerNew(DMZSwitch)
    global _verbose, _max_length, _types, _show_by_default
    _verbose = verbose
    _max_length = max_length
    force_show = (show is True) or (hide is False and show is False)
    if isinstance(hide, basestring):
        hide = hide.replace(',', ' ').replace('|', ' ')
        hide = set([p.lower() for p in hide.split()])
    else:
        hide = set()
    if isinstance(show, basestring):
        show = show.replace(',', ' ').replace('|', ' ')
        show = set([p.lower() for p in show.split()])
    else:
        show = set()

    if hide and show:
        raise RuntimeError("Can't both show and hide packet types")

    if show:
        _types = show
    else:
        _types = hide
        _show_by_default = not not hide
    if force_show:
        _show_by_default = force_show

    if full_packets:
    # Send full packets to controller
        core.openflow.miss_send_len = 0xffff