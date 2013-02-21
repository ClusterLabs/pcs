import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils

pcs_location = "../pcs.py"
empty_cib = "empty.xml"
temp_cib = "temp.xml"

class ResourceAdditionTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    # Setups up a cluster with Resources, groups, master/slave resource & clones
    def setupClusterA(self,temp_cib):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP2 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP3 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP4  ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP5 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP6  ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""

        line = "resource group add TestGroup1 ClusterIP"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""

        line = "resource group add TestGroup2 ClusterIP2 ClusterIP3"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""

        line = "resource clone ClusterIP4"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""

        line = "resource master Master ClusterIP5"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""

    def testEmpty(self):
        output, returnVal = pcs(temp_cib, "resource") 
        assert returnVal == 0, 'Unable to list resources'
        assert output == "NO resources configured\n", "Bad output"

    def testAddResources(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output.split('\n')[0] == "ERROR: Unable to create resource/fence device"
    
        line = "resource create ClusterIP2 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP3 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP4  ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP5 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create ClusterIP6  ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=31s start interval=32s op stop interval=33s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

# Verify all resource have been added
        output, returnVal = pcs(temp_cib, "resource show")
        assert returnVal == 0
        assert output == ' ClusterIP\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP2\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP3\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP4\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP5\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP6\t(ocf::heartbeat:IPaddr2):\tStopped \n'

        output, returnVal = pcs(temp_cib, "resource show ClusterIP6 --all")
        assert returnVal == 0
        assert output == ' Resource: ClusterIP (type=IPaddr2 class=ocf provider=heartbeat)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s\n Resource: ClusterIP2 (type=IPaddr2 class=ocf provider=heartbeat)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s\n Resource: ClusterIP3 (type=IPaddr2 class=ocf provider=heartbeat)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s\n Resource: ClusterIP4 (type=IPaddr2 class=ocf provider=heartbeat)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s\n Resource: ClusterIP5 (type=IPaddr2 class=ocf provider=heartbeat)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s\n Resource: ClusterIP6 (type=IPaddr2 class=ocf provider=heartbeat)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=31s \n              start interval=32s \n              stop interval=33s\n'

    def testAddBadResources(self):
        line = "resource create bad_resource idontexist test=bad"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: Unable to create resource 'idontexist', it is not installed on this system (use --force to override)\n"

        line = "resource create bad_resource2 idontexist2 test4=bad3 --force"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = "resource show --all"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == " Resource: bad_resource2 (type=idontexist2 class=ocf provider=heartbeat)\n  Attributes: test4=bad3 \n"

    def testDeleteResources(self):
# Verify deleting resources works
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource delete'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = "resource delete ClusterIP"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == "Deleting Resource - ClusterIP\n"
        
        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 1
        assert output == "Error: unable to find resource 'ClusterIP'\n"

        output, returnVal = pcs(temp_cib, "resource show")
        assert returnVal == 0
        assert output == 'NO resources configured\n'

    def testResourceShow(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        assert output == 'Resource: ClusterIP\n  ip: 192.168.0.99\n  cidr_netmask: 32\n  op monitor interval=30s\n'

    def testResourceUpdate(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource update'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        output, returnVal = pcs(temp_cib, "resource update ClusterIP ip=192.168.0.100")
        assert returnVal == 0
        assert output == ""

    def testAddOperation(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource add_operation'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = 'resource remove_operation'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = 'resource add_operation ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource add_operation ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: identical operation already exists for ClusterIP\n"

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        assert output == 'Resource: ClusterIP\n  ip: 192.168.0.99\n  cidr_netmask: 32\n  op monitor interval=30s\n  op monitor interval=31s\n', [output]

    def testRemoveOperation(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource add_operation ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource remove_operation ClusterIP monitor interval=30s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource remove_operation ClusterIP monitor interval=30s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == 'Error: Unable to find operation matching: monitor interval=30s\n'

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        assert output == 'Resource: ClusterIP\n  ip: 192.168.0.99\n  cidr_netmask: 32\n  op monitor interval=31s\n'

        line = 'resource remove_operation ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        assert output == 'Resource: ClusterIP\n  ip: 192.168.0.99\n  cidr_netmask: 32\n'

    def testUpdateOpration(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource update ClusterIP op monitor interval=32s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource update ClusterIP op monitor interval=33s start interval=30s timeout=180s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource update ClusterIP op monitor interval=33s start interval=30s timeout=180s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource update ClusterIP op'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource update ClusterIP op monitor'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource show ClusterIP --all'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ' Resource: ClusterIP (type=IPaddr2 class=ocf provider=heartbeat)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=33s \n              start interval=30s timeout=180s\n'

    def testGroupRemoveTest(self):
        self.setupClusterA(temp_cib)
        output, returnVal = pcs(temp_cib, "constraint location ClusterIP3 prefers rh7-1")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource delete ClusterIP2")
        assert returnVal == 0
        assert output =='Deleting Resource - ClusterIP2\n'

        output, returnVal = pcs(temp_cib, "resource delete ClusterIP3")
        assert returnVal == 0
        assert output =="Removing Constraint - location-ClusterIP3-rh7-1-INFINITY\nDeleting Resource (and group) - ClusterIP3\n"

    def testClusterConfig(self):
        self.setupClusterA(temp_cib)

        output, returnVal = pcs(temp_cib, "config")
        assert returnVal == 0
        assert output == 'Cluster Name: test99\nCorosync Nodes:\n rh7-1 rh7-2 \nPacemaker Nodes:\n \n\nResources: \n Resource: ClusterIP6 (type=IPaddr2 class=ocf provider=heartbeat)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s\n Group: TestGroup1\n  Resource: ClusterIP (type=IPaddr2 class=ocf provider=heartbeat)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s\n Group: TestGroup2\n  Resource: ClusterIP2 (type=IPaddr2 class=ocf provider=heartbeat)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s\n  Resource: ClusterIP3 (type=IPaddr2 class=ocf provider=heartbeat)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s\n Clone: ClusterIP4-clone\n  Resource: ClusterIP4 (type=IPaddr2 class=ocf provider=heartbeat)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s\n Master: Master\n  Resource: ClusterIP5 (type=IPaddr2 class=ocf provider=heartbeat)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s\n\nLocation Constraints:\nOrdering Constraints:\nColocation Constraints:\n\nCluster Properties:\n', output

# Run pcs with -f on specified file
def pcs(testfile, args):
    return utils.run([pcs_location, "-f", testfile] + args.split())

if __name__ == "__main__":
    unittest.main()

