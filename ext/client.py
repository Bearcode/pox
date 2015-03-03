from opendaylight import OpenDaylight
from opendaylight.OpenDaylight import OpenDaylightFlow
from opendaylight.OpenDaylight import OpenDaylightNode
from opendaylight.OpenDaylight import OpenDaylightError

import settings

class OpenDaylightClient(object):
    def __init__(self):
        self.CONTROLLER = settings.CONTROLLER
        self.USERNAME = settings.USERNAME
        self.PASSWORD = settings.PASSWORD
        self.odl = OpenDaylight.OpenDaylight()
        self.flow = OpenDaylightFlow(self.odl)
        self.node = OpenDaylightNode(self.odl)
        self.switch_id_1 = settings.SWITCH_1

        self.odl.setup['hostname'] = self.CONTROLLER
        self.odl.setup['username'] = self.USERNAME
        self.odl.setup['password'] = self.PASSWORD

    def get_all_flows(self):
        """Retrieve all flows back from the controller
        """
        self.flow.get(node_id=self.switch_id_1)
        flow_list = []
        for flow in self.flow.flows:
            flow_list.append(str(flow['name']))
        print "MU has %i flows installed: %s" % (len(self.flow.flows), flow_list)

    def delete_flow(self, node, name):
        try:
            self.flow.delete(node, name)
        except:
            print "Flow %s is already deleted" % name

    def add_flow(self, flow):
        print "Installing flow %s:" % flow['name']
        for key in flow.keys():
            if key not in ['node', 'name', 'installInHw', 'actions']:
                print "%s: %s" % (key, flow[key])
        print "Actions: %s" % flow['actions']
        self.flow.add(flow)

if __name__ == '__main__':
    client = OpenDaylightClient()
    client.get_all_flows()
