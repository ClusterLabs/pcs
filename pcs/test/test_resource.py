import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils
from pcs_test_functions import pcs

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


    def testDescribe(self):
        output, returnVal = pcs(temp_cib, "resource describe bad_resource") 
        assert returnVal == 1
        assert output == "Error: Unable to find resource: bad_resource\n"

        output, returnVal = pcs(temp_cib, "resource describe Dummy")
        assert returnVal == 0
        assert output == "Resource options for: Dummy\n  state: Location to store the resource state in.\n  fake: Fake attribute that can be changed to cause a reload\n",[output]

    def testAddResources(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output.split('\n')[0] == "Error: Unable to create resource/fence device"
    
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
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)\n Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)\n Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)\n Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)\n Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=31s (ClusterIP6-monitor-interval-31s)\n              start interval=32s (ClusterIP6-start-interval-32s)\n              stop interval=33s (ClusterIP6-stop-interval-33s)\n',[output]

    def testAddBadResources(self):
        line = "resource create bad_resource idontexist test=bad"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: Unable to create resource 'idontexist', it is not installed on this system (use --force to override)\n",[output]

        line = "resource create bad_resource2 idontexist2 test4=bad3 --force"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = "resource show --all"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == " Resource: bad_resource2 (class=ocf provider=heartbeat type=idontexist2)\n  Attributes: test4=bad3 \n",[output]

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
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n', [output]

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
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n              monitor interval=31s (ClusterIP-name-monitor-interval-31s)\n', [output]

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
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=31s (ClusterIP-name-monitor-interval-31s)\n'

        line = 'resource remove_operation ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n'

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
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=33s (ClusterIP-monitor-interval-33s)\n              start interval=30s timeout=180s (ClusterIP-start-interval-30s-timeout-180s)\n',[output]

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

    def testGroupOrder(self):
        output, returnVal = pcs(temp_cib, "resource create A Dummy")
        output, returnVal = pcs(temp_cib, "resource create B Dummy")
        output, returnVal = pcs(temp_cib, "resource create C Dummy")
        output, returnVal = pcs(temp_cib, "resource create D Dummy")
        output, returnVal = pcs(temp_cib, "resource create E Dummy")
        output, returnVal = pcs(temp_cib, "resource create F Dummy")
        output, returnVal = pcs(temp_cib, "resource create G Dummy")
        output, returnVal = pcs(temp_cib, "resource create H Dummy")
        output, returnVal = pcs(temp_cib, "resource create I Dummy")
        output, returnVal = pcs(temp_cib, "resource create J Dummy")
        output, returnVal = pcs(temp_cib, "resource create K Dummy")

        output, returnVal = pcs(temp_cib, "resource group add RGA A B C E D K J I")
        assert returnVal == 0
        assert output == "",output

        output, returnVal = pcs(temp_cib, "resource")
        assert returnVal == 0
        assert output == ' F\t(ocf::heartbeat:Dummy):\tStopped \n G\t(ocf::heartbeat:Dummy):\tStopped \n H\t(ocf::heartbeat:Dummy):\tStopped \n Resource Group: RGA\n     A\t(ocf::heartbeat:Dummy):\tStopped \n     B\t(ocf::heartbeat:Dummy):\tStopped \n     C\t(ocf::heartbeat:Dummy):\tStopped \n     E\t(ocf::heartbeat:Dummy):\tStopped \n     D\t(ocf::heartbeat:Dummy):\tStopped \n     K\t(ocf::heartbeat:Dummy):\tStopped \n     J\t(ocf::heartbeat:Dummy):\tStopped \n     I\t(ocf::heartbeat:Dummy):\tStopped \n',[output]

        output, returnVal = pcs(temp_cib, "resource group list")
        assert returnVal == 0
        assert output == "RGA: A B C E D K J I \n",[output]

    def testClusterConfig(self):
        self.setupClusterA(temp_cib)

        output, returnVal = pcs(temp_cib, "config")
        assert returnVal == 0
        assert output == 'Cluster Name: test99\nCorosync Nodes:\n rh7-1 rh7-2 \nPacemaker Nodes:\n \n\nResources: \n Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)\n Group: TestGroup1\n  Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n Group: TestGroup2\n  Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)\n  Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)\n Clone: ClusterIP4-clone\n  Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)\n Master: Master\n  Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)\n\nLocation Constraints:\nOrdering Constraints:\nColocation Constraints:\n\nCluster Properties:\n', [output]

    def testMasterSlaveRemove(self):
        self.setupClusterA(temp_cib)
        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-2")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource delete Master")
        assert returnVal == 0
        assert output == "Removing Constraint - location-ClusterIP5-rh7-1-INFINITY\nRemoving Constraint - location-ClusterIP5-rh7-2-INFINITY\nRemoving Master - Master\n"

        output, returnVal = pcs(temp_cib, "config")
        assert returnVal == 0
        assert output == "Cluster Name: test99\nCorosync Nodes:\n rh7-1 rh7-2 \nPacemaker Nodes:\n \n\nResources: \n Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)\n Group: TestGroup1\n  Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n Group: TestGroup2\n  Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)\n  Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)\n Clone: ClusterIP4-clone\n  Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)\n\nLocation Constraints:\nOrdering Constraints:\nColocation Constraints:\n\nCluster Properties:\n", [output]

    def testResourceManage(self):
        output, returnVal = pcs(temp_cib, "resource create D0 Dummy")
        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource create D1 Dummy")
        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource create D2 Dummy")
        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource group add DGroup D0")
        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource unmanage D1")
        assert returnVal == 0
        assert output == ""
        output, returnVal = pcs(temp_cib, "resource unmanage D1")
        assert returnVal == 1
        assert output == "Error: D1 is already unmanaged\n",[output]
        output, returnVal = pcs(temp_cib, "resource manage D2")
        assert returnVal == 1
        assert output == "Error: D2 is already managed\n",[output]
        output, returnVal = pcs(temp_cib, "resource manage D1")
        assert returnVal == 0
        assert output == "",[output]
        output, returnVal = pcs(temp_cib, "resource unmanage D1")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource create C1Master Dummy --master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource create C2Master Dummy --master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource create C3Master Dummy --clone")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource create C4Master Dummy --clone")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource unmanage C1Master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource manage C1Master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource unmanage C2Master-master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource manage C2Master-master")
        assert returnVal == 0
        assert output == ""


        output, returnVal = pcs(temp_cib, "resource unmanage C3Master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource manage C3Master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource unmanage C4Master-clone")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource manage C4Master-clone")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource show D1")
        assert returnVal == 0
        assert output == ' Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: is-managed=false \n',[output]
        output, returnVal = pcs(temp_cib, "resource manage noexist")
        assert returnVal == 1
        assert output == "Error: noexist doesn't exist.\n",[output]
        output, returnVal = pcs(temp_cib, "resource manage DGroup")
        assert returnVal == 1
        assert output == 'Error: DGroup is already managed\n',[output]
        output, returnVal = pcs(temp_cib, "resource unmanage DGroup")
        assert returnVal == 0
        assert output == '',[output]
        output, returnVal = pcs(temp_cib, "resource show DGroup")
        assert returnVal == 0
        assert output == ' Group: DGroup\n  Meta Attrs: is-managed=false \n  Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n',[output]
        output, returnVal = pcs(temp_cib, "resource manage DGroup")
        assert returnVal == 0
        assert output == '',[output]
        output, returnVal = pcs(temp_cib, "resource show DGroup")
        assert returnVal == 0
        assert output == ' Group: DGroup\n  Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n',[output]

    def testBadInstanceVariables(self):
        output, returnVal = pcs(temp_cib, "resource create D0 Dummy test=testC test2=test2a op monitor interval=35 meta test7=test7a test6=")
        assert returnVal == 1
        assert output == "Error: resource option(s): 'test, test2', are not recognized for resource type: 'ocf:heartbeat:Dummy' (use --force to override)\n", [output]

        output, returnVal = pcs(temp_cib, "resource create --force D0 Dummy test=testC test2=test2a test4=test4A op monitor interval=35 meta test7=test7a test6=")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource update D0 test=testA test2=testB")
        assert returnVal == 1
        assert output == "Error: resource option(s): 'test, test2', are not recognized for resource type: 'ocf:heartbeat:Dummy' (use --force to override)\n", [output]

        output, returnVal = pcs(temp_cib, "resource update --force D0 test=testB test2=testC test3=testD")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource show D0")
        assert returnVal == 0
        assert output == " Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n  Attributes: test=testB test2=testC test4=test4A test3=testD \n  Meta Attrs: test7=test7a test6= \n  Operations: monitor interval=35 (D0-monitor-interval-35)\n", [output]

    def testMetaAttrs(self):
        output, returnVal = pcs(temp_cib, "resource create --force D0 Dummy test=testA test2=test2a op monitor interval=30 meta test5=test5a test6=test6a")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource create --force D1 Dummy test=testA test2=test2a op monitor interval=30")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource update --force D0 test=testC test2=test2a op monitor interval=35 meta test7=test7a test6=")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource meta D1 d1meta=superd1meta")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource group add TestRG D1")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource meta TestRG testrgmeta=mymeta testrgmeta2=mymeta2")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource show --all")
        assert returnVal == 0
        assert output == " Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n  Attributes: test=testC test2=test2a \n  Meta Attrs: test5=test5a test7=test7a \n  Operations: monitor interval=35 (D0-monitor-interval-35)\n Group: TestRG\n  Meta Attrs: testrgmeta=mymeta testrgmeta2=mymeta2 \n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Attributes: test=testA test2=test2a \n   Meta Attrs: d1meta=superd1meta \n   Operations: monitor interval=30 (D1-monitor-interval-30)\n", [output]

    def testMSGroup(self):
        output, returnVal  = pcs(temp_cib, "resource create D0 Dummy")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create D1 Dummy")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource group add Group D0 D1")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource master GroupMaster Group")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource --all")
        assert returnVal == 0
        assert output == ' Master: GroupMaster\n  Group: Group\n   Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n   Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n', [output]

        output, returnVal = pcs(temp_cib, "resource delete D0")
        assert returnVal == 0
        assert output == "Deleting Resource - D0\n", [output]

        output, returnVal = pcs(temp_cib, "resource delete D1")
        assert returnVal == 0
        assert output == 'Deleting Resource (and group and M/S) - D1\n', [output]

    def testCloneMaster(self):
        output, returnVal  = pcs(temp_cib, "resource create D0 Dummy")
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal  = pcs(temp_cib, "resource create D1 Dummy")
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal  = pcs(temp_cib, "resource create D2 Dummy")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource clone D0")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource unclone D0")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource clone D0")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource master D1-master-custom D1")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource master D2")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource show --all")
        assert returnVal == 0
        assert output == ' Clone: D0-clone\n  Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n Master: D1-master-custom\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n Master: D2-master\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n', [output]

        output, returnVal = pcs(temp_cib, "resource unmaster D0")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource unmaster D2")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource show --all")
        assert returnVal == 0
        assert output == " Master: D1-master-custom\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n", [output]

    def testLSBResource(self):
        output, returnVal  = pcs(temp_cib, "resource create D2 lsb:network")
        assert returnVal == 0
        assert output == "", [output]

        output, returnval = pcs(temp_cib, "resource update D2 blah=blah")
        assert returnVal == 0
        assert output == "", [output]

        output, returnval = pcs(temp_cib, "resource update D2")
        assert returnVal == 0
        assert output == "", [output]

    def testNoMoveMSClone(self):
        output, returnVal  = pcs(temp_cib, "resource create D0 Dummy")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create D1 Dummy --clone")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create D2 Dummy --master")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource move D1")
        assert returnVal == 0
#        assert output == "Error: unable to move Clone resources", [output]

        output, returnVal  = pcs(temp_cib, "resource move D2")
        assert returnVal == 0
#        assert output == "Error: unable to move Master/Slave resources", [output]

        output, returnVal  = pcs(temp_cib, "resource --all")
        assert returnVal == 0
        assert output == ' Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n Clone: D1-clone\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n Master: D2-master\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n', [output]

if __name__ == "__main__":
    unittest.main()

