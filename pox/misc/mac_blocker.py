# Copyright 2012 James McCauley
#
# This file is part of POX.
#
# POX is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# POX is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with POX.  If not, see <http://www.gnu.org/licenses/>.

"""
Gives a GUI for blocking individual MAC addresses.

Meant to work with reactive components like l2_learning or l2_pairs.

Start with --no-clear-tables if you don't want to clear tables on changes.
"""

from pox.core import core
from pox.lib.revent import EventHalt 
from pox.lib.addresses import EthAddr, IPAddr
import pox.openflow.libopenflow_01 as of

from Tkinter import *

# Sets of blocked and unblocked MACs
blocked = set()
unblocked = set()
ip_blocked = set()
ip_unblocked = set()

# Listbox widgets
unblocked_list = None
blocked_list = None
ip_unblocked_list = None
ip_blocked_list = None

# If True, clear tables on every block/unblock
clear_tables_on_change = True

def add_mac (mac):
  if mac.is_multicast: return
  if mac.is_bridge_filtered: return
  if mac in blocked: return
  if mac in unblocked: return
  unblocked.add(mac)
  core.tk.do(unblocked_list.insert, None, END, str(mac))

def add_ip(ip):
  if ip in ip_blocked: return
  if ip in ip_unblocked: return
  ip_unblocked.add(ip)
  core.tk.do(ip_unblocked_list.insert, None, END, str(ip))

  
def packet_handler (event):
  # Note the two MACs
  add_mac(event.parsed.src)
  add_mac(event.parsed.dst)
  ip = event.parsed.find('ipv4')
  if ip is None:
    # This packet isn't IP!
    return
  add_ip(ip.srcip)
  add_ip(ip.dstip)

  # Check for blocked MACs
  if event.parsed.src in blocked:
    return EventHalt
  if event.parsed.dst in blocked:
    return EventHalt
  if ip.srcip in ip_blocked:
    return EventHalt
  if ip.dstip in ip_blocked:
    return EventHalt

def get (l):
  """ Get an element from a listbox """
  try:
    i = l.curselection()[0]
    mac = l.get(i)
    return i,mac
  except:
    pass
  return None,None

def clear_flows ():
  """ Clear flows on all switches """
  for c in core.openflow.connections:
    d = of.ofp_flow_mod(command = of.OFPFC_DELETE)
    c.send(d)

def move_entry (from_list, from_set, to_list, to_set):
  """ Move entry from one list to another """
  i,item = get(from_list)
  if item is None: return
  from_list.delete(i)
  to_list.insert(END, item)
  item_obj = None
  try:
    mac = EthAddr(item)
    item_obj = mac
  except Exception as e:
    pass
  try:
    ip = IPAddr(item)
    item_obj = ip
  except Exception as e:
    pass
  if item_obj:
    to_set.add(item_obj)
    from_set.remove(item_obj)

  if clear_tables_on_change:
    # This is coming from another thread, so don't just send -- use
    # callLater so that it happens from the coop thread.
    core.callLater(clear_flows)

def do_block ():
  """ Handle clicks on block button """
  move_entry(unblocked_list, unblocked, blocked_list, blocked)

def do_unblock ():
  """ Handle clicks on unblock button """
  move_entry(blocked_list, blocked, unblocked_list, unblocked)

# Ugly duplicate IP functions
def ip_do_block ():
  """ Handle clicks on block button """
  move_entry(ip_unblocked_list, ip_unblocked, ip_blocked_list, ip_blocked)

def ip_do_unblock ():
  """ Handle clicks on unblock button """
  move_entry(ip_blocked_list, ip_blocked, ip_unblocked_list, ip_unblocked)

def setup ():
  """ Set up GUI """
  global unblocked_list, blocked_list, ip_unblocked_list, ip_blocked_list
  top = Toplevel()
  top.title("MAC Blocker")

  # Shut down POX when window is closed
  top.protocol("WM_DELETE_WINDOW", core.quit)

  box1 = Frame(top)
  box2 = Frame(top)
  l1 = Label(box1, text="Allowed")
  l2 = Label(box2, text="Blocked")
  unblocked_list = Listbox(box1)
  blocked_list = Listbox(box2)
  l1.pack()
  l2.pack()
  unblocked_list.pack(expand=True,fill=BOTH)
  blocked_list.pack(expand=True,fill=BOTH)

  buttons = Frame(top)
  block_button = Button(buttons, text="Block >>", command=do_block)
  unblock_button = Button(buttons, text="<< Unblock", command=do_unblock)
  block_button.pack()
  unblock_button.pack()

  opts = {"side":LEFT,"fill":BOTH,"expand":True}
  box1.pack(**opts)
  buttons.pack(**{"side":LEFT})
  box2.pack(**opts)

  #IP Box
  bottom = Toplevel()
  bottom.title("IP Blocker")
  box3 = Frame(bottom)
  box4 = Frame(bottom)
  l3 = Label(box3, text="Allowed")
  l4 = Label(box4, text="Blocked")
  ip_unblocked_list = Listbox(box3)
  ip_blocked_list = Listbox(box4)
  l3.pack()
  l4.pack()
  ip_unblocked_list.pack(expand=TRUE,fill=BOTH)
  ip_blocked_list.pack(expand=TRUE,fill=BOTH)

  ip_buttons = Frame(bottom)
  ip_block_button = Button(ip_buttons, text="Block >>", command=ip_do_block)
  ip_unblock_button = Button(ip_buttons, text="<< Unblock", command=ip_do_unblock)
  ip_block_button.pack()
  ip_unblock_button.pack()

  box3.pack(**opts)
  ip_buttons.pack(**{"side":LEFT})
  box4.pack(**opts)

  core.getLogger().debug("Ready")

def launch (no_clear_tables = False):
  global clear_tables_on_change
  clear_tables_on_change = not no_clear_tables

  def start ():
    core.openflow.addListenerByName("PacketIn",packet_handler,priority=1)
    core.tk.do(setup)

  core.call_when_ready(start, ['openflow','tk'])
