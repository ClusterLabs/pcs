import os,sys
import shutil
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils
from pcs_test_functions import pcs,ac

empty_cib = "empty.xml"
temp_cib = "temp.xml"

class ResourceTest(unittest.TestCase):
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

    def testCaseInsensitive(self):
        o,r = pcs(temp_cib, "resource create D1 dummy")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource create D2 DUMMY")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource create D3 ipaddr2")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource create D4 ipaddr3")
        assert r == 1
        ac(o,"Error: Unable to create resource 'ipaddr3', it is not installed on this system (use --force to override)\n")

    def testEmpty(self):
        output, returnVal = pcs(temp_cib, "resource") 
        assert returnVal == 0, 'Unable to list resources'
        assert output == "NO resources configured\n", "Bad output"


    def testDescribe(self):
        output, returnVal = pcs(temp_cib, "resource describe bad_resource") 
        assert returnVal == 1
        assert output == "Error: Unable to find resource: bad_resource\n"

        output, returnVal = pcs(temp_cib, "resource describe ocf:heartbeat:Dummy")
        assert returnVal == 0
        ac(output,"Resource options for: ocf:heartbeat:Dummy\n  state: Location to store the resource state in.\n  fake: Fake attribute that can be changed to cause a reload\n")

        output, returnVal = pcs(temp_cib, "resource describe Dummy")
        assert returnVal == 0
        ac(output,"Resource options for: ocf:heartbeat:Dummy\n  state: Location to store the resource state in.\n  fake: Fake attribute that can be changed to cause a reload\nResource options for: ocf:pacemaker:Dummy\n  state: Location to store the resource state in.\n  fake: Fake attribute that can be changed to cause a reload\n  op_sleep: Number of seconds to sleep during operations. This can be used to\n            test how the cluster reacts to operation timeouts.\n")

    def testAddResources(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: unable to create resource/fence device 'ClusterIP', 'ClusterIP' already exists on this system\n",[output]
    
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

        output, returnVal = pcs(temp_cib, "resource show ClusterIP6 --full")
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

        line = "resource show --full"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == " Resource: bad_resource2 (class=ocf provider=heartbeat type=idontexist2)\n  Attributes: test4=bad3 \n  Operations: monitor interval=60s (bad_resource2-monitor-interval-60s)\n",[output]

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
        ac(output,"")

        o,r = pcs(temp_cib, "resource add_operation")
        assert r == 1
        assert o == "Error: add_operation has been deprecated, please use 'op add'\n",[o]

        o,r = pcs(temp_cib, "resource remove_operation")
        assert r == 1
        assert o == "Error: remove_operation has been deprecated, please use 'op remove'\n"

        line = 'resource op add'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = 'resource op remove'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output.startswith("\nUsage: pcs resource")

        line = 'resource op add ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource op add ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: identical operation already exists for ClusterIP\n"

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n              monitor interval=31s (ClusterIP-name-monitor-interval-31s)\n', [output]

        o, r = pcs(temp_cib, "resource create OPTest Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource show OPTest")
        ac(o," Resource: OPTest (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest-monitor-interval-30s)\n              monitor interval=25s OCF_CHECK_LEVEL=1 (OPTest-monitor-interval-25s)\n")
        assert r == 0

        o, r = pcs(temp_cib, "resource create OPTest2 Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=1 op start timeout=30s")
        ac(o,"")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource op add OPTest2 start timeout=1800s")
        ac(o,"")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource op add OPTest2 monitor timeout=1800s")
        ac(o,"")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource show OPTest2")
        ac(o," Resource: OPTest2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest2-monitor-interval-30s)\n              monitor interval=25s OCF_CHECK_LEVEL=1 (OPTest2-monitor-interval-25s)\n              start interval=0s timeout=30s (OPTest2-start-timeout-30s)\n              start interval=0s timeout=1800s (OPTest2-name-start-timeout-1800s)\n              monitor interval=60s timeout=1800s (OPTest2-name-monitor-timeout-1800s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create OPTest3 Dummy op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest3")
        ac(o," Resource: OPTest3 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest3-monitor)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create OPTest4 Dummy op monitor interval=30s")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest4 op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest4")
        ac(o," Resource: OPTest4 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest4-monitor)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create OPTest5 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest5 op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest5")
        ac(o," Resource: OPTest5 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest5-monitor)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create OPTest6 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest6 monitor interval=30s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest6")
        ac(o," Resource: OPTest6 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (OPTest6-monitor-interval-60s)\n              monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest6-name-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create OPTest7 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest7 op monitor interval=60s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest7 monitor interval=61s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest7")
        ac(o," Resource: OPTest7 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)\n              monitor interval=61s OCF_CHECK_LEVEL=1 (OPTest7-name-monitor-interval-61s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest7 monitor interval=60s OCF_CHECK_LEVEL=1")
        ac(o,"Error: identical operation already exists for OPTest7\n")
        assert r == 1

    def testRemoveOperation(self):
        line = "resource create ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource op add ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource op add ClusterIP monitor interval=32s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource op remove ClusterIP-name-monitor-interval-32s-xxxxx'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: unable to find operation id: ClusterIP-name-monitor-interval-32s-xxxxx\n"

        line = 'resource op remove ClusterIP-name-monitor-interval-32s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource op remove ClusterIP monitor interval=30s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource op remove ClusterIP monitor interval=30s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == 'Error: Unable to find operation matching: monitor interval=30s\n'

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        ac(output,' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=31s (ClusterIP-name-monitor-interval-31s)\n')

        line = 'resource op remove ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n'

        line = 'resource op add ClusterIP monitor interval=31s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource op add ClusterIP monitor interval=32s'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = 'resource op remove ClusterIP monitor'
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

        line = 'resource show ClusterIP --full'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=33s (ClusterIP-monitor-interval-33s)\n              start interval=30s timeout=180s (ClusterIP-start-interval-30s-timeout-180s)\n',[output]

    def testGroupDeleteTest(self):
        o,r = pcs(temp_cib, "resource create A1 Dummy --group AGroup")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A2 Dummy --group AGroup")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A3 Dummy --group AGroup")
        assert r == 0

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o," Resource Group: AGroup\n     A1\t(ocf::heartbeat:Dummy):\tStopped \n     A2\t(ocf::heartbeat:Dummy):\tStopped \n     A3\t(ocf::heartbeat:Dummy):\tStopped \n")

        o,r = pcs(temp_cib, "resource delete AGroup")
        ac(o,"Removing group: AGroup (and all resources within group)\nDeleting Resource - A1\nDeleting Resource - A2\nDeleting Resource (and group) - A3\n")
        assert r == 0
        
        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,"NO resources configured\n")

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

        o,r = pcs(temp_cib, "resource create A1 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A2 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A3 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A4 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A5 Dummy")
        assert r == 0

        o,r = pcs(temp_cib, "resource group add AGroup A1 A2 A3 A4 A5")
        assert r == 0

        o,r = pcs(temp_cib, "resource show AGroup")
        assert r == 0
        ac(o,' Group: AGroup\n  Resource: A1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (A1-monitor-interval-60s)\n  Resource: A2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (A2-monitor-interval-60s)\n  Resource: A3 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (A3-monitor-interval-60s)\n  Resource: A4 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (A4-monitor-interval-60s)\n  Resource: A5 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (A5-monitor-interval-60s)\n')


        o,r = pcs(temp_cib, "resource ungroup Noexist")
        assert r == 1
        ac(o,"Error: Group 'Noexist' does not exist\n")

        o,r = pcs(temp_cib, "resource ungroup AGroup A1 A3")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,' ClusterIP6\t(ocf::heartbeat:IPaddr2):\tStopped \n Resource Group: TestGroup1\n     ClusterIP\t(ocf::heartbeat:IPaddr2):\tStopped \n Clone Set: ClusterIP4-clone [ClusterIP4]\n Master/Slave Set: Master [ClusterIP5]\n Resource Group: AGroup\n     A2\t(ocf::heartbeat:Dummy):\tStopped \n     A4\t(ocf::heartbeat:Dummy):\tStopped \n     A5\t(ocf::heartbeat:Dummy):\tStopped \n A1\t(ocf::heartbeat:Dummy):\tStopped \n A3\t(ocf::heartbeat:Dummy):\tStopped \n')

        o,r = pcs(temp_cib, "resource ungroup AGroup")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource show AGroup")
        assert r == 1
        ac(o,"Error: unable to find resource 'AGroup'\n")

        o,r = pcs(temp_cib, "resource show A1 A2 A3 A4 A5")
        assert r == 0
        ac(o,' Resource: A1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (A1-monitor-interval-60s)\n Resource: A2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (A2-monitor-interval-60s)\n Resource: A3 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (A3-monitor-interval-60s)\n Resource: A4 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (A4-monitor-interval-60s)\n Resource: A5 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (A5-monitor-interval-60s)\n')

    def testGroupAdd(self):
        o,r = pcs(temp_cib, "resource create A1 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A2 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A3 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A4 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A5 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A6 Dummy --group")
        assert r == 1
        o,r = pcs(temp_cib, "resource create A6 Dummy --group Dgroup")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A7 Dummy --group Dgroup")
        assert r == 0

        o,r = pcs(temp_cib, "resource group add MyGroup A1 B1")
        assert r == 1
        ac(o,'Error: Unable to find resource: B1\n')

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,' A1\t(ocf::heartbeat:Dummy):\tStopped \n A2\t(ocf::heartbeat:Dummy):\tStopped \n A3\t(ocf::heartbeat:Dummy):\tStopped \n A4\t(ocf::heartbeat:Dummy):\tStopped \n A5\t(ocf::heartbeat:Dummy):\tStopped \n Resource Group: Dgroup\n     A6\t(ocf::heartbeat:Dummy):\tStopped \n     A7\t(ocf::heartbeat:Dummy):\tStopped \n')

        o,r = pcs(temp_cib, "resource delete A6")
        assert r == 0

        o,r = pcs(temp_cib, "resource delete A7")
        assert r == 0

        o,r = pcs(temp_cib, "resource group add MyGroup A1 A2 A3")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource group add MyGroup A1 A2 A3")
        assert r == 1
        ac(o,'Error: A1 already exists in MyGroup\n')

        o,r = pcs(temp_cib, "resource group add MyGroup2 A3 A4 A5")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,' Resource Group: MyGroup\n     A1\t(ocf::heartbeat:Dummy):\tStopped \n     A2\t(ocf::heartbeat:Dummy):\tStopped \n Resource Group: MyGroup2\n     A3\t(ocf::heartbeat:Dummy):\tStopped \n     A4\t(ocf::heartbeat:Dummy):\tStopped \n     A5\t(ocf::heartbeat:Dummy):\tStopped \n')

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
        ac (output,'Cluster Name: test99\nCorosync Nodes:\n rh7-1 rh7-2 \nPacemaker Nodes:\n \n\nResources: \n Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)\n Group: TestGroup1\n  Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n Group: TestGroup2\n  Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)\n  Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)\n Clone: ClusterIP4-clone\n  Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)\n Master: Master\n  Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)\n\nStonith Devices: \nFencing Levels: \n\nLocation Constraints:\nOrdering Constraints:\nColocation Constraints:\n\nCluster Properties:\n')

    def testMasterSlaveRemove(self):
        self.setupClusterA(temp_cib)
        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-2")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource delete Master")
        assert returnVal == 1
        assert output == "Error: Master is not a resource (it can be removed by removing the resource it constains)\n",[output]

        output, returnVal = pcs(temp_cib, "resource delete ClusterIP5")
        assert returnVal == 0
        assert output == "Removing Constraint - location-ClusterIP5-rh7-1-INFINITY\nRemoving Constraint - location-ClusterIP5-rh7-2-INFINITY\nDeleting Resource - ClusterIP5\n",[output]

        output, returnVal = pcs(temp_cib, "resource create ClusterIP5 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-2")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "config")
        assert returnVal == 0
        ac(output,'Cluster Name: test99\nCorosync Nodes:\n rh7-1 rh7-2 \nPacemaker Nodes:\n \n\nResources: \n Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)\n Group: TestGroup1\n  Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n Group: TestGroup2\n  Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)\n  Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)\n Clone: ClusterIP4-clone\n  Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)\n Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)\n\nStonith Devices: \nFencing Levels: \n\nLocation Constraints:\n  Resource: ClusterIP5\n    Enabled on: rh7-1 (score:INFINITY) (id:location-ClusterIP5-rh7-1-INFINITY)\n    Enabled on: rh7-2 (score:INFINITY) (id:location-ClusterIP5-rh7-2-INFINITY)\nOrdering Constraints:\nColocation Constraints:\n\nCluster Properties:\n')

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
        assert returnVal == 0
        assert output == "",[output]
        output, returnVal = pcs(temp_cib, "resource manage D2")
        assert returnVal == 0
        assert output == "",[output]
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

        output, returnVal = pcs(temp_cib, "resource create C4Master Dummy clone")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource unmanage C1Master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource manage C1Master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource unmanage C2Master-master")
        ac(output,"")
        assert returnVal == 0

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
        assert output == ' Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: is-managed=false \n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n',[output]

        output, returnVal = pcs(temp_cib, "resource manage noexist")
        assert returnVal == 1
        assert output == "Error: noexist doesn't exist.\n",[output]

        output, returnVal = pcs(temp_cib, "resource manage DGroup")
        assert returnVal == 0
        assert output == '',[output]

        output, returnVal = pcs(temp_cib, "resource unmanage DGroup")
        assert returnVal == 0
        assert output == '',[output]

        output, returnVal = pcs(temp_cib, "resource show DGroup")
        assert returnVal == 0
        ac (output,' Group: DGroup\n  Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n   Meta Attrs: is-managed=false \n   Operations: monitor interval=60s (D0-monitor-interval-60s)\n')

        output, returnVal = pcs(temp_cib, "resource manage DGroup")
        assert returnVal == 0
        assert output == '',[output]

        output, returnVal = pcs(temp_cib, "resource show DGroup")
        assert returnVal == 0
        assert output == ' Group: DGroup\n  Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D0-monitor-interval-60s)\n',[output]

    def testGroupManage(self):
        o,r = pcs(temp_cib, "resource create D1 Dummy --group AG")
        ac(o,"")

        o,r = pcs(temp_cib, "resource create D2 Dummy --group AG")
        ac(o,"")

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "resource unmanage AG")
        ac(o,"")

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Meta Attrs: is-managed=false \n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Meta Attrs: is-managed=false \n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "resource manage AG")
        ac(o,"")

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "resource unmanage D2")
        ac(o,"")

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Meta Attrs: is-managed=false \n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "resource manage AG")
        ac(o,"")

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        o,r = pcs(temp_cib, "resource unmanage D2")
        ac(o,"")

        o,r = pcs(temp_cib, "resource unmanage D1")
        ac(o,"")

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Meta Attrs: is-managed=false \n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Meta Attrs: is-managed=false \n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

        os.system("CIB_file="+temp_cib+" crm_resource --resource AG --set-parameter is-managed --meta --parameter-value false")

        o,r = pcs(temp_cib, "resource manage AG")
        ac(o,"")

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n")

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

        output, returnVal = pcs(temp_cib, "resource show --full")
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

        output, returnVal  = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == ' Master: GroupMaster\n  Group: Group\n   Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (D0-monitor-interval-60s)\n   Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (D1-monitor-interval-60s)\n', [output]

        output, returnVal = pcs(temp_cib, "resource delete D0")
        assert returnVal == 0
        assert output == "Deleting Resource - D0\n", [output]

        output, returnVal = pcs(temp_cib, "resource delete D1")
        assert returnVal == 0
        assert output == 'Deleting Resource (and group and M/S) - D1\n', [output]

    def testUncloneWithConstraints(self):
        o,r = pcs(temp_cib, "resource create D0 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource clone D0")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "constraint location D0-clone prefers rh7-1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "constraint")
        ac(o,"Location Constraints:\n  Resource: D0-clone\n    Enabled on: rh7-1\nOrdering Constraints:\nColocation Constraints:\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource unclone D0-clone")
        ac(o,"")
        assert r == 0

    def testCloneGroupMember(self):
        o,r = pcs(temp_cib, "resource create D0 Dummy --group AG")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create D1 Dummy --group AG")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource clone D0")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource")
        ac(o," Resource Group: AG\n     D1\t(ocf::heartbeat:Dummy):\tStopped \n Clone Set: D0-clone [D0]\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource clone D1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource")
        ac(o," Clone Set: D0-clone [D0]\n Clone Set: D1-clone [D1]\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create D2 Dummy --group AG2")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create D3 Dummy --group AG2")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource master D2")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource")
        ac(o," Clone Set: D0-clone [D0]\n Clone Set: D1-clone [D1]\n Resource Group: AG2\n     D3\t(ocf::heartbeat:Dummy):\tStopped \n Master/Slave Set: D2-master [D2]\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource master D3")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource")
        ac(o," Clone Set: D0-clone [D0]\n Clone Set: D1-clone [D1]\n Master/Slave Set: D2-master [D2]\n Master/Slave Set: D3-master [D3]\n")
        assert r == 0

    def testResourceCreationWithGroupOperations(self):
        o,r = pcs(temp_cib, "resource create D1 Dummy --group AG2 op monitor interval=32s")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create D3 Dummy op monitor interval=34s --group AG2 ")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create D4 Dummy op monitor interval=35s --group=AG2 ")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG2\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=32s (D1-monitor-interval-32s)\n  Resource: D3 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=34s (D3-monitor-interval-34s)\n  Resource: D4 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=35s (D4-monitor-interval-35s)\n")
        assert r == 0

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

        output, returnVal = pcs(temp_cib, "resource show --full")
        assert returnVal == 0
        assert output == ' Clone: D0-clone\n  Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D0-monitor-interval-60s)\n Master: D1-master-custom\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n Master: D2-master\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n', [output]

        output, returnVal = pcs(temp_cib, "resource delete D0")
        assert returnVal == 0
        assert output == "Deleting Resource - D0\n", [output]

        output, returnVal = pcs(temp_cib, "resource delete D2")
        assert returnVal == 0
        assert output == "Deleting Resource - D2\n", [output]

        output, returnVal  = pcs(temp_cib, "resource create D0 Dummy")
        output, returnVal  = pcs(temp_cib, "resource create D2 Dummy")

        output, returnVal = pcs(temp_cib, "resource show --full")
        assert returnVal == 0
        assert output == " Master: D1-master-custom\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D0-monitor-interval-60s)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D2-monitor-interval-60s)\n", [output]

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
        assert returnVal == 1
        assert output == "Error: cannot move cloned resources\n", [output]

        output, returnVal  = pcs(temp_cib, "resource move D2")
        assert returnVal == 1
        assert output == "Error: unable to move Master/Slave resources\n", [output]

        output, returnVal  = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == ' Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D0-monitor-interval-60s)\n Clone: D1-clone\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n Master: D2-master\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n', [output]

    def testGroupCloneCreation(self):
        o,r = pcs(temp_cib, "resource create D1 Dummy --group DGroup")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource clone DGroup")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o," Clone Set: DGroup-clone [DGroup]\n")

    def testGroupRemoveWithConstraints(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib

        o,r = utils.run(["cibadmin","-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create D1 Dummy --group DGroup")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "resource create D2 Dummy --group DGroup")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o," Resource Group: DGroup\n     D1\t(ocf::heartbeat:Dummy):\tStopped \n     D2\t(ocf::heartbeat:Dummy):\tStopped \n")

        o,r = pcs(temp_cib, "resource move DGroup rh7-1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "constraint")
        assert r == 0
        ac(o,"Location Constraints:\n  Resource: DGroup\n    Enabled on: rh7-1\nOrdering Constraints:\nColocation Constraints:\n")

        o,r = pcs(temp_cib, "resource delete D1")
        ac(o,"Deleting Resource - D1\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource delete D2")
        ac(o,"Removing Constraint - cli-prefer-DGroup\nDeleting Resource (and group) - D2\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o,"NO resources configured\n")

    def testResourceCloneCreation(self):
        output, returnVal  = pcs(temp_cib, "resource create D1 Dummy --clone")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create D2 Dummy --clone")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == ' Clone: D1-clone\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n Clone: D2-clone\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n', [output]

        output, returnVal  = pcs(temp_cib, "resource delete D1")
        assert returnVal == 0
        assert output == "Deleting Resource - D1\n", [output]

        output, returnVal  = pcs(temp_cib, "resource delete D2")
        assert returnVal == 0
        assert output == "Deleting Resource - D2\n", [output]

        output,returnVal = pcs(temp_cib, "resource create --clone dlm ocf:pacemaker:controld op monitor interval=10s --cloneopt meta interleave=true clone-node-max=1 ordered=true")
        assert returnVal == 0
        assert output == "", [output]

        output,returnVal = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == " Clone: dlm-clone\n  Meta Attrs: interleave=true clone-node-max=1 ordered=true \n  Resource: dlm (class=ocf provider=pacemaker type=controld)\n   Operations: monitor interval=10s (dlm-monitor-interval-10s)\n", [output]

        output, returnVal  = pcs(temp_cib, "resource delete dlm")
        assert returnVal == 0
        assert output == "Deleting Resource - dlm\n", [output]

        output,returnVal = pcs(temp_cib, "resource create --clone dlm ocf:pacemaker:controld op monitor interval=10s clone meta interleave=true clone-node-max=1 ordered=true")
        assert returnVal == 0
        assert output == "", [output]

        output,returnVal = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == " Clone: dlm-clone\n  Meta Attrs: interleave=true clone-node-max=1 ordered=true \n  Resource: dlm (class=ocf provider=pacemaker type=controld)\n   Operations: monitor interval=10s (dlm-monitor-interval-10s)\n", [output]

        output, returnVal  = pcs(temp_cib, "resource delete dlm")
        assert returnVal == 0
        assert output == "Deleting Resource - dlm\n", [output]

        output,returnVal = pcs(temp_cib, "resource create dlm ocf:pacemaker:controld op monitor interval=10s clone meta interleave=true clone-node-max=1 ordered=true")
        assert returnVal == 0
        assert output == "", [output]

        output,returnVal = pcs(temp_cib, "resource create dlm ocf:pacemaker:controld op monitor interval=10s clone meta interleave=true clone-node-max=1 ordered=true")
        assert returnVal == 1
        assert output == "Error: unable to create resource/fence device 'dlm', 'dlm' already exists on this system\n", [output]

        output,returnVal = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == " Clone: dlm-clone\n  Meta Attrs: interleave=true clone-node-max=1 ordered=true \n  Resource: dlm (class=ocf provider=pacemaker type=controld)\n   Operations: monitor interval=10s (dlm-monitor-interval-10s)\n", [output]

    def testGroupRemoveWithConstraints(self):
        o,r = pcs(temp_cib, "resource create A Dummy --group AG")
        assert r == 0

        o,r = pcs(temp_cib, "resource create B Dummy --group AG")
        assert r == 0

        o,r = pcs(temp_cib, "constraint location AG prefers rh7-1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource ungroup AG")
        ac(o,"Removing Constraint - location-AG-rh7-1-INFINITY\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource --full")
        ac(o, " Resource: A (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (A-monitor-interval-60s)\n Resource: B (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (B-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create A1 Dummy --group AA")
        assert r == 0
        o,r = pcs(temp_cib, "resource create A2 Dummy --group AA")
        assert r == 0
        o,r = pcs(temp_cib, "resource master AA")
        assert r == 0
        o,r = pcs(temp_cib, "constraint location AA prefers rh7-1")
        assert r == 0

        o,r = pcs(temp_cib, "resource delete A1")
        ac(o,"Deleting Resource - A1\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource delete A2")
        ac(o,"Deleting Resource (and group and M/S) - A2\n")
        assert r == 0

    def testMasteredGroup(self):
        o,r = pcs(temp_cib, "resource create A Dummy --group AG")
        assert r == 0

        o,r = pcs(temp_cib, "resource create B Dummy --group AG")
        assert r == 0

        o,r = pcs(temp_cib, "resource create C Dummy --group AG")
        assert r == 0

        o,r = pcs(temp_cib, "resource master AGMaster AG")
        assert r == 0

        o,r = pcs(temp_cib, "resource ungroup AG")
        ac(o,"Error: Groups that have more than one resource and are master/slave resources cannot be removed.  The group may be deleted with 'pcs resource delete AG'.\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource delete B")
        assert r == 0
        o,r = pcs(temp_cib, "resource delete C")
        assert r == 0

        o,r = pcs(temp_cib, "resource ungroup AG")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource show --full")
        ac(o," Master: AGMaster\n  Resource: A (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (A-monitor-interval-60s)\n")
        assert r == 0

    def testResourceEnable(self):
        o,r = pcs(temp_cib, "resource create D1 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource disable D1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource show D1 --full")
        ac(o," Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Meta Attrs: target-role=Stopped \n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource enable D1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource show D1 --full")
        ac(o," Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D1-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource enable NoExist")
        ac(o,"Error: Resource 'NoExist' not found: No such device or address\nError performing operation: No such device or address\n\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource disable NoExist")
        ac(o,"Error: Resource 'NoExist' not found: No such device or address\nError performing operation: No such device or address\n\n")
        assert r == 1




if __name__ == "__main__":
    unittest.main()

