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
        #Drop PVST+ traffic
        self.connection.send(of.ofp_flow_mod(action=[],
                                             priority=9999,
                                             match=of.ofp_match(in_port=64, dl_dst=EthAddr("01:00:0c:cc:cc:cd"))))

        #OSU DTN ARP traffic outbound to Clemson to controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=801,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.ARP_TYPE,
                                                                dl_dst=EthAddr("00:24:38:9c:13:00"))))
        #Clemson Inbound to Controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=800,
                                             match=of.ofp_match(in_port=64, dl_vlan=3070)))

        #OSU DTN traffic outbound to Clemson rewrite src
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=800,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_dst="130.127.3.192/32")))

        #MU Inbound send to OSU DTN
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=20),
                                             priority=700,
                                             match=of.ofp_match(in_port=64, dl_vlan=1751)))

        #OSU DTN traffic outbound to MU IP 128.146.162.36
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=64),
                                             priority=700,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_dst="128.146.162.36/32")))

        #OSU DTN Traffic outbound to public IPs
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_strip_vlan(), of.ofp_action_output(port=61)],
                                             priority=500,
                                             match=of.ofp_match(in_port=20,
                                                                dl_vlan=1751,
                                                                dl_type=pkt.ethernet.IP_TYPE,
                                                                nw_src="128.146.162.35/32")))
        #OSU DTN Traffic outbound ARP flood
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_strip_vlan(), of.ofp_action_output(port=of.OFPP_FLOOD)],
                                             priority=500,
                                             match=of.ofp_match(in_port=20,
                                                                dl_type=pkt.ethernet.ARP_TYPE,
                                                                dl_src=(EthAddr("00:02:c9:1f:d1:60")))))

        #OSU DTN Outbound Default to Controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=2,
                                             match=of.ofp_match(in_port=20)))

        #OSU Public inbound traffic default to OSU DTN
        self.connection.send(of.ofp_flow_mod(action=[of.ofp_action_vlan_vid(vlan_vid=1751),
                                                     of.ofp_action_output(port=20)],
                                             priority=1,
                                             match=of.ofp_match(in_port=61)))
        #AL2S inbound default to controller
        self.connection.send(of.ofp_flow_mod(action=of.ofp_action_output(port=of.OFPP_CONTROLLER),
                                             priority=1,
                                             match=of.ofp_match(in_port=64)))

    def _handle_PacketIn(self, event):
        """
        Handle packet in messages from the switch to implement above algorithm.
        """
        packet = event.parsed
        global packet_id

        def output(packet):
            out_port = 64
            out_vlan = 3070
            msg = of.ofp_packet_out(in_port=of.OFPP_NONE)
            msg.data = packet
            if event.port == 64:
                out_port = 20
                out_vlan = 1751
            msg.actions.append(of.ofp_action_vlan_vid(vlan_vid=out_vlan))
            msg.actions.append(of.ofp_action_output(port=out_port))
            log.debug("%i Forwarding %s from %i out: %i as VLAN %i" % (packet_id, packet, event.port, out_port, out_vlan))
            self.connection.send(msg)

        def ip_rewrite(packet):
            orignal_dst = packet.find('ipv4').dstip
            orignal_src = packet.find('ipv4').srcip
            if packet.find('ipv4').dstip in ["130.127.3.192"]:
                #Packet is outbound to Clemson
                packet.find('ipv4').srcip = IPAddr("130.127.3.193")
            if packet.find('ipv4').dstip in ["130.127.3.193"]:
                packet.find('ipv4').dstip = IPAddr("128.146.162.35")
            log.debug("%i Rewrote Source: %s -> %s Destination: %s -> %s" % (packet_id,
                                                                             orignal_src, packet.find('ipv4').srcip,
                                                                             orignal_dst, packet.find('ipv4').dstip))
            parse_tree(packet, forward=False)
            output(packet)

        def arp_forward(packet):
            defined = False
            if packet.find('arp').opcode == pkt.arp.REQUEST:
                if packet.find('arp').protodst in ["130.127.3.193", "128.146.162.35"]:
                    #ARP inbound to OSU DTN
                    defined = True
                    packet.find('arp').protodst = IPAddr("128.146.162.35")
                    log.debug("%i ARP_forward: Who has %s tell %s" % (packet_id, packet.find('arp').protodst, packet.find('arp').protosrc))
            if packet.find('arp').opcode == pkt.arp.REPLY:
                if packet.find('arp').protodst in ["130.127.3.192"]:
                    #Replies destined to Clemson
                    defined = True
                    packet.find('arp').protosrc = IPAddr("130.127.3.193")
                    log.debug("%i ARP_forward: %s is at %s" % (packet_id, packet.find('arp').protosrc, packet.find('arp').hwsrc))
            if defined:
                output(packet)
            else:
                arp = packet.find('arp')
                arp_code_map = {1: "Request", 2:"Reply"}
                log.debug("%i arp_forward failed on ARP %s from %s to %s" % (packet_id, arp_code_map[arp.opcode], arp.protosrc, arp.protodst))

        def handle_IP_packet(packet, forward=True):
            ip = packet.find('ipv4')
            if ip is None:
            # This packet isn't IP!
                return False
            log.debug("%i Source IP: %s Destination IP: %s" % (packet_id, ip.srcip, ip.dstip))
            if forward:
                ip_rewrite(packet)

            return True

        def handle_ARP_packet(packet, forward=True):
            arp = packet.find('arp')
            if arp is None:
            # This packet isn't ARP!
                return False
            if arp.opcode == pkt.arp.REQUEST:
                log.debug("%i Who has %s tell %s" % (packet_id, arp.protodst, arp.protosrc))
            if arp.opcode == pkt.arp.REPLY:
                log.debug("%i %s Is at %s" % (packet_id, arp.protosrc, arp.hwsrc))

            if forward:
                arp_forward(packet)
            return True

        def handle_VLAN_packet(packet):
            vlan = packet.find('vlan')
            log.debug("%i VLAN: %s" % (packet_id, vlan))
            return True

        def parse_tree(packet, forward=True):
            success = False
            if packet.find('vlan'):
                success = handle_VLAN_packet(packet)
            if packet.find('ipv4'):
                success |= handle_IP_packet(packet, forward)
            if packet.find('arp'):
                success |= handle_ARP_packet(packet, forward)
            return success

        success = parse_tree(packet)

        if not success:
            log.debug("%i parse failed: %s" % (packet_id, packet))
        packet_id += 1
        return


class DMZSwitch(object):
    def __init__(self):
        core.openflow.addListeners(self)

    def _handle_ConnectionUp(self, event):
        log.debug("Switch %s has come up.", dpid_to_str(event.dpid))
        DMZFlows(event.connection)


def launch():
    core.registerNew(DMZSwitch)