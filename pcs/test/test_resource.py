import os,sys
import shutil
import re
import datetime
import unittest
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0,parentdir) 
import utils
from pcs_test_functions import pcs,ac

empty_cib = "empty.xml"
temp_cib = "temp.xml"
large_cib = "large.xml"
temp_large_cib = "temp-large.xml"

class ResourceTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        shutil.copy(large_cib, temp_large_cib)
        shutil.copy("corosync.conf.orig", "corosync.conf")

    # Setups up a cluster with Resources, groups, master/slave resource & clones
    def setupClusterA(self,temp_cib):
        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP2 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP3 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP4  ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP6  ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
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
        o,r = pcs(temp_cib, "resource create --no-default-ops D1 dummy")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource create --no-default-ops D2 DUMMY")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource create --no-default-ops D3 ipaddr2 ip=1.1.1.1")
        assert r == 0
        ac(o,'')

        o,r = pcs(temp_cib, "resource create --no-default-ops D4 ipaddr3")
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
        ac(output, """\
ocf:heartbeat:Dummy - Example stateless resource agent

This is a Dummy Resource Agent. It does absolutely nothing except 
keep track of whether its running or not.
Its purpose in life is for testing and to serve as a template for RA writers.

NB: Please pay attention to the timeouts specified in the actions
section below. They should be meaningful for the kind of resource
the agent manages. They should be the minimum advised timeouts,
but they shouldn't/cannot cover _all_ possible resource
instances. So, try to be neither overly generous nor too stingy,
but moderate. The minimum timeouts should never be below 10 seconds.

Resource options:
  state: Location to store the resource state in.
  fake: Fake attribute that can be changed to cause a reload
""")

        output, returnVal = pcs(temp_cib, "resource describe Dummy")
        assert returnVal == 0
        ac(output, """\
ocf:heartbeat:Dummy - Example stateless resource agent

This is a Dummy Resource Agent. It does absolutely nothing except 
keep track of whether its running or not.
Its purpose in life is for testing and to serve as a template for RA writers.

NB: Please pay attention to the timeouts specified in the actions
section below. They should be meaningful for the kind of resource
the agent manages. They should be the minimum advised timeouts,
but they shouldn't/cannot cover _all_ possible resource
instances. So, try to be neither overly generous nor too stingy,
but moderate. The minimum timeouts should never be below 10 seconds.

Resource options:
  state: Location to store the resource state in.
  fake: Fake attribute that can be changed to cause a reload
""")

        output, returnVal = pcs(temp_cib, "resource describe SystemHealth")
        assert returnVal == 0
        ac(output, """\
ocf:pacemaker:SystemHealth - SystemHealth resource agent

This is a SystemHealth Resource Agent.  It is used to monitor
the health of a system via IPMI.

""")

    def testAddResources(self):
        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: unable to create resource/fence device 'ClusterIP', 'ClusterIP' already exists on this system\n",[output]
    
        line = "resource create --no-default-ops ClusterIP2 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP3 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP4  ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP6  ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=31s start interval=32s op stop interval=33s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""
        line = "resource create --no-default-ops ClusterIP7 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s --disabled"
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_large_cib, "resource create dummy0 Dummy")
        assert returnVal == 0
        ac(output, '')

# Verify all resource have been added
        output, returnVal = pcs(temp_cib, "resource show")
        assert returnVal == 0
        assert output == ' ClusterIP\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP2\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP3\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP4\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP5\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP6\t(ocf::heartbeat:IPaddr2):\tStopped \n ClusterIP7\t(ocf::heartbeat:IPaddr2):\tStopped \n'

        output, returnVal = pcs(temp_cib, "resource show ClusterIP6 --full")
        assert returnVal == 0
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)\n Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)\n Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)\n Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)\n Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=31s (ClusterIP6-monitor-interval-31s)\n              start interval=32s (ClusterIP6-start-interval-32s)\n              stop interval=33s (ClusterIP6-stop-interval-33s)\n Resource: ClusterIP7 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Meta Attrs: target-role=Stopped \n  Operations: monitor interval=30s (ClusterIP7-monitor-interval-30s)\n',[output]

        output, returnVal = pcs(
            temp_cib,
            "resource create A dummy op interval=10"
        )
        ac(output, """\
Error: When using 'op' you must specify an operation name and at least one option
""")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create A dummy op interval=10 timeout=5"
        )
        ac(output, """\
Error: When using 'op' you must specify an operation name after 'op'
""")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create A dummy op monitor interval=10 op interval=10 op start timeout=10"
        )
        ac(output, """\
Error: When using 'op' you must specify an operation name and at least one option
""")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create A dummy op monitor"
        )
        ac(output, """\
Error: When using 'op' you must specify an operation name and at least one option
""")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create A dummy op monitor interval=10 op stop op start timeout=10"
        )
        ac(output, """\
Error: When using 'op' you must specify an operation name and at least one option
""")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create A dummy op monitor interval=10 timeout=10 op monitor interval=10 timeout=20"
        )
        ac(output, """\
Error: operation monitor with interval 10s already specified for A:
monitor interval=10 timeout=10 (A-monitor-interval-10)
""")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create A dummy op monitor interval=10 timeout=10 op stop interval=10 timeout=20"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show A")
        ac(output, """\
 Resource: A (class=ocf provider=heartbeat type=Dummy)
  Operations: start interval=0s timeout=20 (A-start-interval-0s)
              monitor interval=10 timeout=10 (A-monitor-interval-10)
              stop interval=10 timeout=20 (A-stop-interval-10)
""")
        self.assertEquals(0, returnVal)

    def testAddBadResources(self):
        line = "resource create --no-default-ops bad_resource idontexist test=bad"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: Unable to create resource 'idontexist', it is not installed on this system (use --force to override)\n",[output]

        line = "resource create --no-default-ops bad_resource2 idontexist2 test4=bad3 --force"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        line = "resource show --full"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == " Resource: bad_resource2 (class=ocf provider=heartbeat type=idontexist2)\n  Attributes: test4=bad3 \n  Operations: monitor interval=60s (bad_resource2-monitor-interval-60s)\n",[output]

        output, returnVal = pcs(temp_cib, "resource create dum:my Dummy")
        assert returnVal == 1
        ac(output, "Error: invalid resource name 'dum:my', ':' is not a valid character for a resource name\n")

    def testDeleteResources(self):
# Verify deleting resources works
        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
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
        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        assert output == ' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n', [output]

    def testResourceUpdate(self):
        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
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
        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        ac(output,"")
        assert returnVal == 0

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
        ac(output, """\
Error: operation monitor with interval 31s already specified for ClusterIP:
monitor interval=31s (ClusterIP-monitor-interval-31s)
""")
        assert returnVal == 1

        line = 'resource op add ClusterIP monitor interval=31'
        output, returnVal = pcs(temp_cib, line) 
        ac(output, """\
Error: operation monitor with interval 31s already specified for ClusterIP:
monitor interval=31s (ClusterIP-monitor-interval-31s)
""")
        assert returnVal == 1

        output, returnVal = pcs(
            temp_cib,
            "resource op add ClusterIP moni=tor interval=60"
        )
        ac(output, """\
Error: moni=tor does not appear to be a valid operation action
""")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        ac (output,' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n              monitor interval=31s (ClusterIP-monitor-interval-31s)\n')

        o, r = pcs(temp_cib, "resource create --no-default-ops OPTest Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource show OPTest")
        ac(o," Resource: OPTest (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest-monitor-interval-30s)\n              monitor interval=25s OCF_CHECK_LEVEL=1 (OPTest-monitor-interval-25s)\n")
        assert r == 0

        o, r = pcs(temp_cib, "resource create --no-default-ops OPTest2 Dummy op monitor interval=30s OCF_CHECK_LEVEL=1 op monitor interval=25s OCF_CHECK_LEVEL=1 op start timeout=30s")
        ac(o,"")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource op add OPTest2 start timeout=1800s")
        ac(o, """\
Error: operation start with interval 0s already specified for OPTest2:
start interval=0s timeout=30s (OPTest2-start-interval-0s)
""")
        assert r == 1
        
        o, r = pcs(temp_cib, "resource op add OPTest2 monitor timeout=1800s")
        ac(o,"")
        assert r == 0
        
        o, r = pcs(temp_cib, "resource show OPTest2")
        ac(o," Resource: OPTest2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest2-monitor-interval-30s)\n              monitor interval=25s OCF_CHECK_LEVEL=1 (OPTest2-monitor-interval-25s)\n              start interval=0s timeout=30s (OPTest2-start-interval-0s)\n              monitor interval=60s timeout=1800s (OPTest2-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest3 Dummy op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest3")
        ac(o," Resource: OPTest3 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest3-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest4 Dummy op monitor interval=30s")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest4 op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest4")
        ac(o," Resource: OPTest4 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest4-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest5 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest5 op monitor OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest5")
        ac(o," Resource: OPTest5 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest5-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest6 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest6 monitor interval=30s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest6")
        ac(o," Resource: OPTest6 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (OPTest6-monitor-interval-60s)\n              monitor interval=30s OCF_CHECK_LEVEL=1 (OPTest6-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops OPTest7 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update OPTest7 op monitor interval=60s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest7 monitor interval=61s OCF_CHECK_LEVEL=1")
        ac(o,"")
        assert r == 0

        o, r = pcs(temp_cib, "resource show OPTest7")
        ac(o," Resource: OPTest7 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)\n              monitor interval=61s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-61s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add OPTest7 monitor interval=60s OCF_CHECK_LEVEL=1")
        ac(o, """\
Error: operation monitor with interval 60s already specified for OPTest7:
monitor interval=60s OCF_CHECK_LEVEL=1 (OPTest7-monitor-interval-60s)
""")
        assert r == 1

        o,r = pcs("resource create --no-default-ops OCFTest1 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource op add OCFTest1 monitor interval=31s")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource op add OCFTest1 monitor interval=30s OCF_CHECK_LEVEL=15")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource show OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (OCFTest1-monitor-interval-60s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs("resource update OCFTest1 op monitor interval=61s OCF_CHECK_LEVEL=5")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource show OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=61s OCF_CHECK_LEVEL=5 (OCFTest1-monitor-interval-61s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs("resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource show OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s OCF_CHECK_LEVEL=4 (OCFTest1-monitor-interval-60s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

        o,r = pcs("resource update OCFTest1 op monitor OCF_CHECK_LEVEL=4 interval=35s")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource show OCFTest1")
        ac(o," Resource: OCFTest1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=35s OCF_CHECK_LEVEL=4 (OCFTest1-monitor-interval-35s)\n              monitor interval=31s (OCFTest1-monitor-interval-31s)\n              monitor interval=30s OCF_CHECK_LEVEL=15 (OCFTest1-monitor-interval-30s)\n")
        assert r == 0

    def testRemoveOperation(self):
        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
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

        line = 'resource op remove ClusterIP-monitor-interval-32s-xxxxx'
        output, returnVal = pcs(temp_cib, line) 
        assert returnVal == 1
        assert output == "Error: unable to find operation id: ClusterIP-monitor-interval-32s-xxxxx\n"

        line = 'resource op remove ClusterIP-monitor-interval-32s'
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
        ac(output,' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=31s (ClusterIP-monitor-interval-31s)\n')

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

        line = 'resource op add ClusterIP stop timeout=34s'
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""

        line = 'resource op add ClusterIP start timeout=33s'
        output, returnVal = pcs(temp_cib, line)
        assert returnVal == 0
        assert output == ""

        line = 'resource op remove ClusterIP monitor'
        output, returnVal = pcs(temp_cib, line)
        ac(output,"")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource show ClusterIP")
        assert returnVal == 0
        ac (output,' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: stop interval=0s timeout=34s (ClusterIP-stop-interval-0s)\n              start interval=0s timeout=33s (ClusterIP-start-interval-0s)\n')

    def testUpdateOpration(self):
        line = "resource create --no-default-ops ClusterIP ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s"
        output, returnVal = pcs(temp_cib, line) 
        assert output == ""
        assert returnVal == 0

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
        ac(output,' Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=33s (ClusterIP-monitor-interval-33s)\n              start interval=30s timeout=180s (ClusterIP-start-interval-30s)\n')

        output, returnVal = pcs(
            temp_cib,
            "resource create A dummy op monitor interval=10 op monitor interval=20"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show A")
        ac(output, """\
 Resource: A (class=ocf provider=heartbeat type=Dummy)
  Operations: start interval=0s timeout=20 (A-start-interval-0s)
              stop interval=0s timeout=20 (A-stop-interval-0s)
              monitor interval=10 (A-monitor-interval-10)
              monitor interval=20 (A-monitor-interval-20)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update A op monitor interval=20"
        )
        ac(output, """\
Error: operation monitor with interval 20s already specified for A:
monitor interval=20 (A-monitor-interval-20)
""")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update A op monitor interval=11"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show A")
        ac(output, """\
 Resource: A (class=ocf provider=heartbeat type=Dummy)
  Operations: start interval=0s timeout=20 (A-start-interval-0s)
              stop interval=0s timeout=20 (A-stop-interval-0s)
              monitor interval=11 (A-monitor-interval-11)
              monitor interval=20 (A-monitor-interval-20)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource create B dummy --no-default-ops"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource op remove B-monitor-interval-60s"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=60s"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=60s (B-monitor-interval-60s)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=30"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=30 (B-monitor-interval-30)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op start interval=0 timeout=10"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=30 (B-monitor-interval-30)
              start interval=0 timeout=10 (B-start-interval-0)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op start interval=0 timeout=20"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=30 (B-monitor-interval-30)
              start interval=0 timeout=20 (B-start-interval-0)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=33"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=33 (B-monitor-interval-33)
              start interval=0 timeout=20 (B-start-interval-0)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op monitor interval=100 role=Master"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=33 (B-monitor-interval-33)
              start interval=0 timeout=20 (B-start-interval-0)
              monitor interval=100 role=Master (B-monitor-interval-100)
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "resource update B op start interval=0 timeout=22"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource show B")
        ac(output, """\
 Resource: B (class=ocf provider=heartbeat type=Dummy)
  Operations: monitor interval=33 (B-monitor-interval-33)
              start interval=0 timeout=22 (B-start-interval-0)
              monitor interval=100 role=Master (B-monitor-interval-100)
""")
        self.assertEquals(0, returnVal)

    def testGroupDeleteTest(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops A1 Dummy --group AGroup")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A2 Dummy --group AGroup")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A3 Dummy --group AGroup")
        assert r == 0

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o," Resource Group: AGroup\n     A1\t(ocf::heartbeat:Dummy):\tStopped \n     A2\t(ocf::heartbeat:Dummy):\tStopped \n     A3\t(ocf::heartbeat:Dummy):\tStopped \n")

        o,r = pcs(temp_cib, "resource delete AGroup")
        ac(o,"Removing group: AGroup (and all resources within group)\nStopping all resources in group: AGroup...\nDeleting Resource - A1\nDeleting Resource - A2\nDeleting Resource (and group) - A3\n")
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

        o,r = pcs(temp_cib, "resource create --no-default-ops A1 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A2 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A3 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A4 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A5 Dummy")
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
        o,r = pcs(temp_cib, "resource create --no-default-ops A1 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A2 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A3 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A4 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A5 Dummy")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A6 Dummy --group")
        assert r == 1
        o,r = pcs(temp_cib, "resource create --no-default-ops A6 Dummy --group Dgroup")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A7 Dummy --group Dgroup")
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

        o, r = pcs(temp_cib, "resource create --no-default-ops A6 Dummy")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource create --no-default-ops A7 Dummy")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A6 --after A1")
        ac(o, "")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A7 --before A1")
        ac(o, "")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A7\t(ocf::heartbeat:Dummy):\tStopped 
     A1\t(ocf::heartbeat:Dummy):\tStopped 
     A6\t(ocf::heartbeat:Dummy):\tStopped 
     A2\t(ocf::heartbeat:Dummy):\tStopped 
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped 
     A4\t(ocf::heartbeat:Dummy):\tStopped 
     A5\t(ocf::heartbeat:Dummy):\tStopped 
""")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup2 A6 --before A5")
        ac(o, "")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup2 A7 --after A5")
        ac(o, "")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped 
     A2\t(ocf::heartbeat:Dummy):\tStopped 
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped 
     A4\t(ocf::heartbeat:Dummy):\tStopped 
     A6\t(ocf::heartbeat:Dummy):\tStopped 
     A5\t(ocf::heartbeat:Dummy):\tStopped 
     A7\t(ocf::heartbeat:Dummy):\tStopped 
""")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A6 A7 --before A2")
        ac(o, "")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped 
     A6\t(ocf::heartbeat:Dummy):\tStopped 
     A7\t(ocf::heartbeat:Dummy):\tStopped 
     A2\t(ocf::heartbeat:Dummy):\tStopped 
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped 
     A4\t(ocf::heartbeat:Dummy):\tStopped 
     A5\t(ocf::heartbeat:Dummy):\tStopped 
""")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup2 A6 A7 --after A4")
        ac(o, "")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped 
     A2\t(ocf::heartbeat:Dummy):\tStopped 
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped 
     A4\t(ocf::heartbeat:Dummy):\tStopped 
     A6\t(ocf::heartbeat:Dummy):\tStopped 
     A7\t(ocf::heartbeat:Dummy):\tStopped 
     A5\t(ocf::heartbeat:Dummy):\tStopped 
""")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A6 --before A0")
        ac(o, "Error: there is no resource 'A0' in the group 'MyGroup'\n")
        self.assertEquals(1, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A6 --after A0")
        ac(o, "Error: there is no resource 'A0' in the group 'MyGroup'\n")
        self.assertEquals(1, r)

        o, r = pcs(
            temp_cib,
            "resource group add MyGroup A6 --after A1 --before A2"
        )
        ac(o, "Error: you cannot specify both --before and --after\n")
        self.assertEquals(1, r)

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A8 Dummy --group MyGroup --before A1"
        )
        ac(o, "")
        self.assertEquals(0, r)

        o,r = pcs(
            temp_cib,
            "resource create --no-default-ops A9 Dummy --group MyGroup --after A1"
        )
        ac(o, "")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A8\t(ocf::heartbeat:Dummy):\tStopped 
     A1\t(ocf::heartbeat:Dummy):\tStopped 
     A9\t(ocf::heartbeat:Dummy):\tStopped 
     A2\t(ocf::heartbeat:Dummy):\tStopped 
 Resource Group: MyGroup2
     A3\t(ocf::heartbeat:Dummy):\tStopped 
     A4\t(ocf::heartbeat:Dummy):\tStopped 
     A6\t(ocf::heartbeat:Dummy):\tStopped 
     A7\t(ocf::heartbeat:Dummy):\tStopped 
     A5\t(ocf::heartbeat:Dummy):\tStopped 
""")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup A1 --before A8")
        self.assertEquals(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource group add MyGroup2 A3 --after A6")
        self.assertEquals(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource show")
        ac(o, """\
 Resource Group: MyGroup
     A1\t(ocf::heartbeat:Dummy):\tStopped 
     A8\t(ocf::heartbeat:Dummy):\tStopped 
     A9\t(ocf::heartbeat:Dummy):\tStopped 
     A2\t(ocf::heartbeat:Dummy):\tStopped 
 Resource Group: MyGroup2
     A4\t(ocf::heartbeat:Dummy):\tStopped 
     A6\t(ocf::heartbeat:Dummy):\tStopped 
     A3\t(ocf::heartbeat:Dummy):\tStopped 
     A7\t(ocf::heartbeat:Dummy):\tStopped 
     A5\t(ocf::heartbeat:Dummy):\tStopped 
""")
        self.assertEquals(0, r)

        o, r = pcs(temp_cib, "resource group add MyGroup2 A3 --after A3")
        self.assertEquals(1, r)
        ac(o, "Error: cannot put resource after itself\n")

        o, r = pcs(temp_cib, "resource group add MyGroup2 A3 --before A3")
        self.assertEquals(1, r)
        ac(o, "Error: cannot put resource before itself\n")

        o, r = pcs(temp_cib, "resource group add A7 A6")
        ac(o, "Error: 'A7' is already a resource\n")
        self.assertEquals(1, r)

        o, r = pcs(temp_cib, "resource create --no-default-ops A0 Dummy --clone")
        self.assertEquals(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource group add A0-clone A6")
        ac(o, "Error: 'A0-clone' is already a clone resource\n")
        self.assertEquals(1, r)

        o, r = pcs(temp_cib, "resource unclone A0-clone")
        self.assertEquals(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource master A0")
        self.assertEquals(0, r)
        ac(o, "")

        o, r = pcs(temp_cib, "resource group add A0-master A6")
        ac(o, "Error: 'A0-master' is already a master/slave resource\n")
        self.assertEquals(1, r)

        output, returnVal = pcs(temp_large_cib, "resource group add dummyGroup dummy1")
        assert returnVal == 0
        ac(output, '')

        output, returnVal = pcs(temp_cib, "resource group add group:dummy dummy1")
        assert returnVal == 1
        ac(output, "Error: invalid group name 'group:dummy', ':' is not a valid character for a group name\n")

    def testGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            temp_large_cib, "resource group add dummies dummylarge"
        )
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummies")
        ac(output, """\
Removing group: dummies (and all resources within group)
Stopping all resources in group: dummies...
Deleting Resource (and group) - dummylarge
""")
        assert returnVal == 0

    def testGroupOrder(self):
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops A Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops B Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops C Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops D Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops E Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops F Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops G Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops H Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops I Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops J Dummy")
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops K Dummy")

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
        ac (output,'Cluster Name: test99\nCorosync Nodes:\n rh7-1 rh7-2 \nPacemaker Nodes:\n \n\nResources: \n Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)\n Group: TestGroup1\n  Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n Group: TestGroup2\n  Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)\n  Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)\n Clone: ClusterIP4-clone\n  Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)\n Master: Master\n  Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)\n\nStonith Devices: \nFencing Levels: \n\nLocation Constraints:\nOrdering Constraints:\nColocation Constraints:\n\nResources Defaults:\n No defaults set\nOperations Defaults:\n No defaults set\n\nCluster Properties:\n')

    def testCloneRemove(self):
        o,r = pcs("resource create --no-default-ops D1 Dummy --clone")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location D1-clone prefers rh7-1")
        ac(o,"")
        assert r == 0

        o,r = pcs("constraint location D1 prefers rh7-1 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource --full")
        ac(o," Clone: D1-clone\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs("resource delete D1-clone")
        assert r == 0
        ac(o, """\
Removing Constraint - location-D1-clone-rh7-1-INFINITY
Removing Constraint - location-D1-rh7-1-INFINITY
Deleting Resource - D1
""")

        o,r = pcs("resource --full")
        assert r == 0
        ac(o,"")

        o, r = pcs("resource create d99 Dummy clone globally-unique=true")
        ac(o, "")
        assert r == 0

        o, r = pcs("resource delete d99")
        ac(o, "Deleting Resource - d99\n")
        assert r == 0

        output, returnVal = pcs(temp_large_cib, "resource clone dummylarge")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummylarge")
        ac(output, 'Deleting Resource - dummylarge\n')
        assert returnVal == 0

    def testCloneGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            temp_large_cib, "resource group add dummies dummylarge"
        )
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource clone dummies")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummies")
        ac(output, """\
Removing group: dummies (and all resources within group)
Stopping all resources in group: dummies...
Deleting Resource (and group and clone) - dummylarge
""")
        assert returnVal == 0

    def testMasterSlaveRemove(self):
        self.setupClusterA(temp_cib)
        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1 --force")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "constraint location Master prefers rh7-2")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource delete Master")
        assert returnVal == 0
        ac(output, """\
Removing Constraint - location-Master-rh7-2-INFINITY
Removing Constraint - location-ClusterIP5-rh7-1-INFINITY
Deleting Resource - ClusterIP5
""")

        output, returnVal = pcs(temp_cib, "resource create --no-default-ops ClusterIP5 Dummy")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-1")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "constraint location ClusterIP5 prefers rh7-2")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource delete ClusterIP5")
        assert returnVal == 0
        assert output == "Removing Constraint - location-ClusterIP5-rh7-1-INFINITY\nRemoving Constraint - location-ClusterIP5-rh7-2-INFINITY\nDeleting Resource - ClusterIP5\n",[output]

        output, returnVal = pcs(temp_cib, "resource create --no-default-ops ClusterIP5 ocf:heartbeat:IPaddr2 ip=192.168.0.99 cidr_netmask=32 op monitor interval=30s")
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
        ac(output,'Cluster Name: test99\nCorosync Nodes:\n rh7-1 rh7-2 \nPacemaker Nodes:\n \n\nResources: \n Resource: ClusterIP6 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP6-monitor-interval-30s)\n Group: TestGroup1\n  Resource: ClusterIP (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP-monitor-interval-30s)\n Group: TestGroup2\n  Resource: ClusterIP2 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP2-monitor-interval-30s)\n  Resource: ClusterIP3 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP3-monitor-interval-30s)\n Clone: ClusterIP4-clone\n  Resource: ClusterIP4 (class=ocf provider=heartbeat type=IPaddr2)\n   Attributes: ip=192.168.0.99 cidr_netmask=32 \n   Operations: monitor interval=30s (ClusterIP4-monitor-interval-30s)\n Resource: ClusterIP5 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=192.168.0.99 cidr_netmask=32 \n  Operations: monitor interval=30s (ClusterIP5-monitor-interval-30s)\n\nStonith Devices: \nFencing Levels: \n\nLocation Constraints:\n  Resource: ClusterIP5\n    Enabled on: rh7-1 (score:INFINITY) (id:location-ClusterIP5-rh7-1-INFINITY)\n    Enabled on: rh7-2 (score:INFINITY) (id:location-ClusterIP5-rh7-2-INFINITY)\nOrdering Constraints:\nColocation Constraints:\n\nResources Defaults:\n No defaults set\nOperations Defaults:\n No defaults set\n\nCluster Properties:\n')

        output, returnVal = pcs(temp_large_cib, "resource master dummylarge")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummylarge")
        ac(output, 'Deleting Resource - dummylarge\n')
        assert returnVal == 0

    def testMasterSlaveGroupLargeResourceRemove(self):
        output, returnVal = pcs(
            temp_large_cib, "resource group add dummies dummylarge"
        )
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource master dummies")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource delete dummies")
        ac(output, """\
Removing group: dummies (and all resources within group)
Stopping all resources in group: dummies...
Deleting Resource (and group and M/S) - dummylarge
""")
        assert returnVal == 0

    def testResourceManage(self):
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops D0 Dummy")
        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops D1 Dummy")
        assert returnVal == 0
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops D2 Dummy")
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

        output, returnVal = pcs(temp_cib, "resource create --no-default-ops C1Master Dummy --master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource create --no-default-ops C2Master Dummy --master")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource create --no-default-ops C3Master Dummy --clone")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "resource create --no-default-ops C4Master Dummy clone")
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
        o,r = pcs(temp_cib, "resource create --no-default-ops D1 Dummy --group AG")
        ac(o,"")

        o,r = pcs(temp_cib, "resource create --no-default-ops D2 Dummy --group AG")
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

    def testMasterMetaCreate(self):
        o,r = pcs('resource create --no-default-ops F0 Dummy op monitor interval=10s role=Master op monitor interval=20s role=Slave --master meta notify=true')
        ac (o,"")
        assert r==0

        o,r = pcs("resource --full")
        ac (o," Master: F0-master\n  Meta Attrs: notify=true \n  Resource: F0 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=10s role=Master (F0-monitor-interval-10s)\n               monitor interval=20s role=Slave (F0-monitor-interval-20s)\n")
        assert r==0

    def testBadInstanceVariables(self):
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops D0 Dummy test=testC test2=test2a op monitor interval=35 meta test7=test7a test6=")
        assert returnVal == 1
        assert output == "Error: resource option(s): 'test, test2', are not recognized for resource type: 'ocf:heartbeat:Dummy' (use --force to override)\n", [output]

        output, returnVal = pcs(temp_cib, "resource create --no-default-ops --force D0 Dummy test=testC test2=test2a test4=test4A op monitor interval=35 meta test7=test7a test6=")
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
        output, returnVal = pcs(temp_cib, "resource create --no-default-ops --force D0 Dummy test=testA test2=test2a op monitor interval=30 meta test5=test5a test6=test6a")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal = pcs(temp_cib, "resource create --no-default-ops --force D1 Dummy test=testA test2=test2a op monitor interval=30")
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
        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D0 Dummy")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D1 Dummy")
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
        o,r = pcs(temp_cib, "resource create --no-default-ops D0 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource clone D0")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "constraint location D0-clone prefers rh7-1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "constraint")
        ac(o,"Location Constraints:\n  Resource: D0-clone\n    Enabled on: rh7-1 (score:INFINITY)\nOrdering Constraints:\nColocation Constraints:\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource unclone D0-clone")
        ac(o,"")
        assert r == 0

    def testCloneGroupMember(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops D0 Dummy --group AG")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops D1 Dummy --group AG")
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

        o,r = pcs(temp_cib, "resource create --no-default-ops D2 Dummy --group AG2")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops D3 Dummy --group AG2")
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
        o,r = pcs(temp_cib, "resource create --no-default-ops D1 Dummy --group AG2 op monitor interval=32s")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops D3 Dummy op monitor interval=34s --group AG2 ")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops D4 Dummy op monitor interval=35s --group=AG2 ")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource --full")
        ac(o," Group: AG2\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=32s (D1-monitor-interval-32s)\n  Resource: D3 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=34s (D3-monitor-interval-34s)\n  Resource: D4 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=35s (D4-monitor-interval-35s)\n")
        assert r == 0

    def testCloneMaster(self):
        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D0 Dummy")
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D1 Dummy")
        assert returnVal == 0
        assert output == "", [output]
        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D2 Dummy")
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

        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D0 Dummy")
        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D2 Dummy")

        output, returnVal = pcs(temp_cib, "resource show --full")
        assert returnVal == 0
        assert output == " Master: D1-master-custom\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D0-monitor-interval-60s)\n Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D2-monitor-interval-60s)\n", [output]

    def testLSBResource(self):
        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D2 lsb:network")
        assert returnVal == 0
        assert output == "", [output]

        output, returnval = pcs(temp_cib, "resource update D2 blah=blah")
        assert returnVal == 0
        assert output == "", [output]

        output, returnval = pcs(temp_cib, "resource update D2")
        assert returnVal == 0
        assert output == "", [output]

    def testResourceMoveBanClear(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib

        output, returnVal = utils.run(["cibadmin", "-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "resource create --no-default-ops dummy Dummy"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource move dummy")
        ac(output, """\
Error: You must specify a node when moving/banning a stopped resource
""")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move dummy rh7-1")
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: dummy
    Enabled on: rh7-1 (score:INFINITY) (role: Started) (id:cli-prefer-dummy)
Ordering Constraints:
Colocation Constraints:
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear dummy")
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
""")

        output, returnVal = pcs(temp_cib, "resource ban dummy rh7-1")
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: dummy
    Disabled on: rh7-1 (score:-INFINITY) (role: Started) (id:cli-ban-dummy-on-rh7-1)
Ordering Constraints:
Colocation Constraints:
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear dummy")
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
""")

        output, returnVal = pcs(
            temp_cib, "resource move dummy rh7-1 lifetime=1H"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        output = re.sub("\d{4}-\d\d-\d\d \d\d:\d\d:\d\dZ", "{datetime}", output)
        ac(output, """\
Location Constraints:
  Resource: dummy
    Constraint: cli-prefer-dummy
      Rule: score=INFINITY boolean-op=and  (id:cli-prefer-rule-dummy)
        Expression: #uname eq string rh7-1  (id:cli-prefer-expr-dummy)
        Expression: date lt {datetime}  (id:cli-prefer-lifetime-end-dummy)
Ordering Constraints:
Colocation Constraints:
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear dummy")
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
""")

        output, returnVal = pcs(
            temp_cib, "resource ban dummy rh7-1 lifetime=P1H"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        output = re.sub("\d{4}-\d\d-\d\d \d\d:\d\d:\d\dZ", "{datetime}", output)
        ac(output, """\
Location Constraints:
  Resource: dummy
    Constraint: cli-ban-dummy-on-rh7-1
      Rule: score=-INFINITY boolean-op=and  (id:cli-ban-dummy-on-rh7-1-rule)
        Expression: #uname eq string rh7-1  (id:cli-ban-dummy-on-rh7-1-expr)
        Expression: date lt {datetime}  (id:cli-ban-dummy-on-rh7-1-lifetime)
Ordering Constraints:
Colocation Constraints:
""")
        self.assertEquals(0, returnVal)


        output, returnVal = pcs(temp_cib, "resource ban dummy rh7-1 rh7-1")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(
            temp_cib, "resource ban dummy rh7-1 lifetime=1H lifetime=1H"
        )
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move dummy rh7-1 --master")
        ac(output, """\
Error: when specifying --master you must use the master id
""")
        self.assertEquals(1, returnVal)

    def testCloneMoveBanClear(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib
        output, returnVal = utils.run(["cibadmin", "-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "resource create --no-default-ops D1 Dummy --clone"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "resource create --no-default-ops D2 Dummy --group DG"
        )
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clone DG")
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D1-clone")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move D2")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource move DG-clone")
        ac(output, "Error: cannot move cloned resources\n")
        self.assertEquals(1, returnVal)

        output, returnVal = pcs(temp_cib, "resource ban DG-clone rh7-1")
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
  Resource: DG-clone
    Disabled on: rh7-1 (score:-INFINITY) (role: Started) (id:cli-ban-DG-clone-on-rh7-1)
Ordering Constraints:
Colocation Constraints:
""")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "resource clear DG-clone")
        ac(output, "")
        self.assertEquals(0, returnVal)

        output, returnVal = pcs(temp_cib, "constraint --full")
        ac(output, """\
Location Constraints:
Ordering Constraints:
Colocation Constraints:
""")
        self.assertEquals(0, returnVal)

    def testNoMoveMSClone(self):
        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D0 Dummy")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D1 Dummy --clone")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D2 Dummy --master")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource move D1")
        assert returnVal == 1
        assert output == "Error: cannot move cloned resources\n", [output]

        output, returnVal  = pcs(temp_cib, "resource move D1-clone")
        assert returnVal == 1
        assert output == "Error: cannot move cloned resources\n", [output]

        output, returnVal  = pcs(temp_cib, "resource move D2")
        assert returnVal == 1
        assert output == "Error: to move Master/Slave resources you must use --master and the master id (D2-master)\n", [output]

        output, returnVal  = pcs(temp_cib, "resource move D2 --master")
        ac(output,"Error: when specifying --master you must use the master id (D2-master)\n")
        assert returnVal == 1

        output, returnVal  = pcs(temp_cib, "resource move D2-master --master")
        ac(output,"Error: error moving/banning/clearing resource\nResource 'D2-master' not moved: active in 0 locations (promoted in 0).\nYou can prevent 'D2-master' from running on a specific location with: --ban --host <name>\nYou can prevent 'D2-master' from being promoted at a specific location with: --ban --master --host <name>\nError performing operation: Invalid argument\n\n")
        assert returnVal == 1

        output, returnVal  = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == ' Resource: D0 (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (D0-monitor-interval-60s)\n Clone: D1-clone\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n Master: D2-master\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n', [output]

    def testMasterOfGroupMove(self):
        o,r = pcs("resource create stateful Stateful --group group1")
        ac(o, """\
Warning: changing a monitor operation interval from 10 to 11 to make the operation unique
""")
        assert r == 0

        o,r = pcs("resource master group1")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource move group1-master --master")
        ac(o,"Error: error moving/banning/clearing resource\nResource 'group1-master' not moved: active in 0 locations (promoted in 0).\nYou can prevent 'group1-master' from running on a specific location with: --ban --host <name>\nYou can prevent 'group1-master' from being promoted at a specific location with: --ban --master --host <name>\nError performing operation: Invalid argument\n\n")
        assert r == 1

    def testDebugStartCloneGroup(self):
        o,r = pcs("resource create D0 Dummy --group DGroup")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create D1 Dummy --group DGroup")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create D2 Dummy --clone")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create D3 Dummy --master")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource debug-start DGroup")
        ac(o,"Error: unable to debug-start a group, try one of the group's resource(s) (D0,D1)\n")
        assert r == 1

        o,r = pcs("resource debug-start D2-clone")
        ac(o,"Error: unable to debug-start a clone, try the clone's resource: D2\n")
        assert r == 1

        o,r = pcs("resource debug-start D3-master")
        ac(o,"Error: unable to debug-start a master, try the master's resource: D3\n")
        assert r == 1

    def testGroupCloneCreation(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops D1 Dummy --group DGroup")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource clone DGroup1")
        ac(o,"Error: unable to find group or resource: DGroup1\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource clone DGroup")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "resource show")
        assert r == 0
        ac(o," Clone Set: DGroup-clone [DGroup]\n")

        o,r = pcs(temp_cib, "resource clone DGroup")
        ac(o,"Error: cannot clone a group that has already been cloned\n")
        assert r == 1

    def testGroupRemoveWithConstraints1(self):
        # Load nodes into cib so move will work
        utils.usefile = True
        utils.filename = temp_cib

        o,r = utils.run(["cibadmin","-M", '--xml-text', '<nodes><node id="1" uname="rh7-1"><instance_attributes id="nodes-1"/></node><node id="2" uname="rh7-2"><instance_attributes id="nodes-2"/></node></nodes>'])
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops D1 Dummy --group DGroup")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "resource create --no-default-ops D2 Dummy --group DGroup")
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
        ac(o,"Location Constraints:\n  Resource: DGroup\n    Enabled on: rh7-1 (score:INFINITY) (role: Started)\nOrdering Constraints:\nColocation Constraints:\n")

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
        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D1 Dummy --clone")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D2 Dummy --clone")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource create --no-default-ops D3 Dummy --clone globaly-unique=true")
        assert returnVal == 0
        assert output == "", [output]

        output, returnVal  = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        ac(output,' Clone: D1-clone\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n Clone: D2-clone\n  Resource: D2 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D2-monitor-interval-60s)\n Clone: D3-clone\n  Meta Attrs: globaly-unique=true \n  Resource: D3 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D3-monitor-interval-60s)\n')

        output, returnVal  = pcs(temp_cib, "resource delete D1")
        assert returnVal == 0
        assert output == "Deleting Resource - D1\n", [output]

        output, returnVal  = pcs(temp_cib, "resource delete D2")
        assert returnVal == 0
        assert output == "Deleting Resource - D2\n", [output]

        output, returnVal  = pcs(temp_cib, "resource delete D3")
        assert returnVal == 0
        assert output == "Deleting Resource - D3\n", [output]

        output,returnVal = pcs(temp_cib, "resource create --no-default-ops dlm ocf:pacemaker:controld op monitor interval=10s --clone meta interleave=true clone-node-max=1 ordered=true")
        assert output == "", [output]
        assert returnVal == 0

        output,returnVal = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        ac(output," Clone: dlm-clone\n  Meta Attrs: interleave=true clone-node-max=1 ordered=true \n  Resource: dlm (class=ocf provider=pacemaker type=controld)\n   Operations: monitor interval=10s (dlm-monitor-interval-10s)\n")

        output, returnVal  = pcs(temp_cib, "resource delete dlm")
        assert returnVal == 0
        assert output == "Deleting Resource - dlm\n", [output]

        output,returnVal = pcs(temp_cib, "resource create --no-default-ops dlm ocf:pacemaker:controld op monitor interval=10s clone meta interleave=true clone-node-max=1 ordered=true")
        assert output == "", [output]
        assert returnVal == 0

        output,returnVal = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == " Clone: dlm-clone\n  Meta Attrs: interleave=true clone-node-max=1 ordered=true \n  Resource: dlm (class=ocf provider=pacemaker type=controld)\n   Operations: monitor interval=10s (dlm-monitor-interval-10s)\n", [output]

        output, returnVal  = pcs(temp_cib, "resource delete dlm")
        assert returnVal == 0
        assert output == "Deleting Resource - dlm\n", [output]

        output,returnVal = pcs(temp_cib, "resource create --no-default-ops dlm ocf:pacemaker:controld op monitor interval=10s clone meta interleave=true clone-node-max=1 ordered=true")
        assert returnVal == 0
        assert output == "", [output]

        output,returnVal = pcs(temp_cib, "resource create --no-default-ops dlm ocf:pacemaker:controld op monitor interval=10s clone meta interleave=true clone-node-max=1 ordered=true")
        assert returnVal == 1
        assert output == "Error: unable to create resource/fence device 'dlm', 'dlm' already exists on this system\n", [output]

        output,returnVal = pcs(temp_cib, "resource --full")
        assert returnVal == 0
        assert output == " Clone: dlm-clone\n  Meta Attrs: interleave=true clone-node-max=1 ordered=true \n  Resource: dlm (class=ocf provider=pacemaker type=controld)\n   Operations: monitor interval=10s (dlm-monitor-interval-10s)\n", [output]

        output, returnVal = pcs(temp_large_cib, "resource clone dummy1")
        ac(output, '')
        assert returnVal == 0

        output, returnVal = pcs(temp_large_cib, "resource unclone dummy1")
        ac(output, '')
        assert returnVal == 0

    def testResourceCloneUpdate(self):
        o, r  = pcs(temp_cib, "resource create --no-default-ops D1 Dummy --clone")
        assert r == 0
        ac(o, "")

        o, r  = pcs(temp_cib, "resource --full")
        assert r == 0
        ac(o, ' Clone: D1-clone\n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n')

        o, r = pcs(temp_cib, 'resource update D1-clone foo=bar')
        assert r == 0
        ac(o, "")

        o, r  = pcs(temp_cib, "resource --full")
        assert r == 0
        ac(o, ' Clone: D1-clone\n  Meta Attrs: foo=bar \n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n')

        o, r = pcs(temp_cib, 'resource update D1-clone bar=baz')
        assert r == 0
        ac(o, "")

        o, r  = pcs(temp_cib, "resource --full")
        assert r == 0
        ac(o, ' Clone: D1-clone\n  Meta Attrs: foo=bar bar=baz \n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n')

        o, r = pcs(temp_cib, 'resource update D1-clone foo=')
        assert r == 0
        ac(o, "")

        o, r  = pcs(temp_cib, "resource --full")
        assert r == 0
        ac(o, ' Clone: D1-clone\n  Meta Attrs: bar=baz \n  Resource: D1 (class=ocf provider=heartbeat type=Dummy)\n   Operations: monitor interval=60s (D1-monitor-interval-60s)\n')

    def testGroupRemoveWithConstraints2(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops A Dummy --group AG")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops B Dummy --group AG")
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

        o,r = pcs(temp_cib, "resource create --no-default-ops A1 Dummy --group AA")
        assert r == 0
        o,r = pcs(temp_cib, "resource create --no-default-ops A2 Dummy --group AA")
        assert r == 0
        o,r = pcs(temp_cib, "resource master AA")
        assert r == 0
        o,r = pcs(temp_cib, "constraint location AA-master prefers rh7-1")
        assert r == 0

        o,r = pcs(temp_cib, "resource delete A1")
        ac(o,"Deleting Resource - A1\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource delete A2")
        ac(o,"""\
Removing Constraint - location-AA-master-rh7-1-INFINITY
Deleting Resource (and group and M/S) - A2
""")
        assert r == 0

    def testMasteredGroup(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops A Dummy --group AG")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops B Dummy --group AG")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops C Dummy --group AG")
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
        o,r = pcs(temp_cib, "resource create --no-default-ops D1 Dummy")
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
        ac(o,"Error: unable to find a resource/clone/master/group: NoExist\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource disable NoExist")
        ac(o,"Error: unable to find a resource/clone/master/group: NoExist\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource create --no-default-ops D2 Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource unmanage D2")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable D2")
        ac(o,"Warning: 'D2' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable D2")
        ac(o,"Warning: 'D2' is unmanaged\n")
        assert r == 0

        o,r = pcs(temp_cib, "property set is-managed-default=false")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable D1")
        ac(o,"Warning: 'D1' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable D1")
        ac(o,"Warning: 'D1' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "property set is-managed-default=")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops D3 Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource group add DG D3")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource unmanage DG")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable D3")
        ac(o,"Warning: 'D3' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable D3")
        ac(o,"Warning: 'D3' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable DG")
        ac(o,"Warning: 'DG' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable DG")
        ac(o,"Warning: 'DG' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource manage DG")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource create --no-default-ops D4 Dummy")
        ac(o,"")
        assert r == 0
        o,r = pcs("resource group add DG D4")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource unmanage D4")
        ac(o,"")
        assert r == 0
        o,r = pcs(temp_cib, "resource disable DG")
        ac(o,"Warning: 'DG' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource enable DG")
        ac(o,"Warning: 'DG' is unmanaged\n")
        assert r == 0
        o,r = pcs(temp_cib, "resource manage D4")
        ac(o,"")
        assert r == 0

        output, retVal = pcs(temp_cib, "resource create dummy0 Dummy --group group0")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource clone group0")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show group0-clone")
        ac(output," Clone: group0-clone\n  Group: group0\n   Resource: dummy0 (class=ocf provider=heartbeat type=Dummy)\n    Operations: start interval=0s timeout=20 (dummy0-start-interval-0s)\n                stop interval=0s timeout=20 (dummy0-stop-interval-0s)\n                monitor interval=10 timeout=20 (dummy0-monitor-interval-10)\n")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource disable group0")
        ac(output, "")
        assert retVal == 0

    def testOPOption(self):
        o,r = pcs(temp_cib, "resource create --no-default-ops A Dummy op monitor interval=30s blah=blah")
        ac(o,"Error: blah is not a valid op option (use --force to override)\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource create --no-default-ops A Dummy op monitor interval=30s op monitor interval=40s blah=blah")
        ac(o,"Error: blah is not a valid op option (use --force to override)\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource create --no-default-ops B Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource update B Dummy op monitor interval=30s blah=blah")
        ac(o,"Error: blah is not a valid op option (use --force to override)\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource create --no-default-ops C Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource op add C monitor interval=30s blah=blah")
        ac(o,"Error: blah is not a valid op option (use --force to override)\n")
        assert r == 1

        output, returnVal = pcs(
            temp_cib,
            "resource op add C monitor interval=60 role=role"
        )
        ac(output, """\
Error: role must be: Stopped, Started, Slave or Master (use --force to override)
""")
        assert returnVal == 1

        o,r = pcs(temp_cib, "resource show --full")
        ac(o," Resource: B (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (B-monitor-interval-60s)\n Resource: C (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (C-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource update B Dummy op monitor interval=30s monitor interval=31s role=master")
        ac(o,"Error: role must be: Stopped, Started, Slave or Master (use --force to override)\n")
        assert r == 1

        o,r = pcs(temp_cib, "resource update B Dummy op monitor interval=30s monitor interval=31s role=Master")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "resource show --full")
        ac(o," Resource: B (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=30s (B-monitor-interval-30s)\n              monitor interval=31s role=Master (B-monitor-interval-31s)\n Resource: C (class=ocf provider=heartbeat type=Dummy)\n  Operations: monitor interval=60s (C-monitor-interval-60s)\n")
        assert r == 0

        o,r = pcs(temp_cib, "resource update B dummy op interval=5s")
        ac(o,"Error: interval=5s does not appear to be a valid operation action\n")
        assert r == 1

    def testCloneMasterBadResources(self):
        self.setupClusterA(temp_cib)
        o,r = pcs("resource clone ClusterIP4")
        ac(o,"Error: ClusterIP4 is already a clone resource\n")
        assert r == 1

        o,r = pcs("resource clone ClusterIP5")
        ac(o,"Error: ClusterIP5 is already a master/slave resource\n")
        assert r == 1

        o,r = pcs("resource master ClusterIP4")
        ac(o,"Error: ClusterIP4 is already a clone resource\n")
        assert r == 1

        o,r = pcs("resource master ClusterIP5")
        ac(o,"Error: ClusterIP5 is already a master/slave resource\n")
        assert r == 1

#    def testMasterLargeFile(self):
#        o,r = pcs("largefile.xml","resource")
#        ac(o,"")
#        assert r == 0

#        o,r = pcs("largefile.xml","resource master lxc-ms-master-4")
#        ac(o,"")
#        assert r == 0

    def groupMSAndClone(self):
        o,r = pcs("resource create --no-default-ops D1 Dummy --clone")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create --no-default-ops D2 Dummy --master")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource group add DG D1")
        ac(o,"Error: cannot group clone resources\n")
        assert r == 1

        o,r = pcs("resource group add DG D2")
        ac(o,"Error: cannot group master/slave resources\n")
        assert r == 1

        o,r = pcs("resource create --no-default-ops D3 Dummy --master --group xxx --clone")
        ac(o,"Warning: --group ignored when creating a clone\nWarning: --master ignored when creating a clone\n")
        assert r == 0

        o,r = pcs("resource create --no-default-ops D4 Dummy --master --group xxx")
        ac(o,"Warning: --group ignored when creating a master\n")
        assert r == 0

    def testResourceCloneGroup(self):
        o,r = pcs("resource create --no-default-ops dummy0 Dummy --group group")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource clone group")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource delete dummy0")
        ac(o,"Deleting Resource (and group and clone) - dummy0\n")
        assert r == 0

    def testVirtualDomainResource(self):
        o,r = pcs("resource describe VirtualDomain")
        assert r == 0

    def testResourceMissingValues(self):
        o,r = pcs("resource create --no-default-ops myip IPaddr2")
        ac(o,"Error: missing required option(s): 'ip' for resource type: ocf:heartbeat:IPaddr2 (use --force to override)\n")
        assert r == 1

        o,r = pcs("resource create --no-default-ops myip IPaddr2 --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create --no-default-ops myip2 IPaddr2 ip=3.3.3.3")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create --no-default-ops myfs Filesystem")
        ac(o,"Error: missing required option(s): 'device, directory, fstype' for resource type: ocf:heartbeat:Filesystem (use --force to override)\n")
        assert r == 1

        o,r = pcs("resource create --no-default-ops myfs Filesystem --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create --no-default-ops myfs2 Filesystem device=x directory=y --force")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create --no-default-ops myfs3 Filesystem device=x directory=y fstype=z")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource --full")
        ac(o," Resource: myip (class=ocf provider=heartbeat type=IPaddr2)\n  Operations: monitor interval=60s (myip-monitor-interval-60s)\n Resource: myip2 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=3.3.3.3 \n  Operations: monitor interval=60s (myip2-monitor-interval-60s)\n Resource: myfs (class=ocf provider=heartbeat type=Filesystem)\n  Operations: monitor interval=60s (myfs-monitor-interval-60s)\n Resource: myfs2 (class=ocf provider=heartbeat type=Filesystem)\n  Attributes: device=x directory=y \n  Operations: monitor interval=60s (myfs2-monitor-interval-60s)\n Resource: myfs3 (class=ocf provider=heartbeat type=Filesystem)\n  Attributes: device=x directory=y fstype=z \n  Operations: monitor interval=60s (myfs3-monitor-interval-60s)\n")
        assert r == 0

    def testDefaultOps(self):
        o,r = pcs("resource create X0 Dummy")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create X1 Dummy op monitor interval=90s")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create X2 IPaddr2 ip=1.1.1.1")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource create X3 IPaddr2 ip=1.1.1.1 op monitor interval=1s start timeout=1s stop timeout=1s")
        ac(o,"")
        assert r == 0

        o,r = pcs("resource --full")
        ac(o," Resource: X0 (class=ocf provider=heartbeat type=Dummy)\n  Operations: start interval=0s timeout=20 (X0-start-interval-0s)\n              stop interval=0s timeout=20 (X0-stop-interval-0s)\n              monitor interval=10 timeout=20 (X0-monitor-interval-10)\n Resource: X1 (class=ocf provider=heartbeat type=Dummy)\n  Operations: start interval=0s timeout=20 (X1-start-interval-0s)\n              stop interval=0s timeout=20 (X1-stop-interval-0s)\n              monitor interval=90s (X1-monitor-interval-90s)\n Resource: X2 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=1.1.1.1 \n  Operations: start interval=0s timeout=20s (X2-start-interval-0s)\n              stop interval=0s timeout=20s (X2-stop-interval-0s)\n              monitor interval=10s timeout=20s (X2-monitor-interval-10s)\n Resource: X3 (class=ocf provider=heartbeat type=IPaddr2)\n  Attributes: ip=1.1.1.1 \n  Operations: monitor interval=1s (X3-monitor-interval-1s)\n              start interval=0s timeout=1s (X3-start-interval-0s)\n              stop interval=0s timeout=1s (X3-stop-interval-0s)\n")
        assert r == 0

    def testClonedMasteredGroup(self):
        output, retVal = pcs(temp_cib, "resource create dummy1 Dummy --no-default-ops --group dummies")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource create dummy2 Dummy --no-default-ops --group dummies")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource create dummy3 Dummy --no-default-ops --group dummies")
        ac(output, "")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource clone dummies")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show dummies-clone")
        ac(output, " Clone: dummies-clone\n  Group: dummies\n   Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy1-monitor-interval-60s)\n   Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy2-monitor-interval-60s)\n   Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy3-monitor-interval-60s)\n")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource unclone dummies-clone")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show")
        ac(output, " Resource Group: dummies\n     dummy1\t(ocf::heartbeat:Dummy):\tStopped \n     dummy2\t(ocf::heartbeat:Dummy):\tStopped \n     dummy3\t(ocf::heartbeat:Dummy):\tStopped \n")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource clone dummies")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show dummies-clone")
        ac(output, " Clone: dummies-clone\n  Group: dummies\n   Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy1-monitor-interval-60s)\n   Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy2-monitor-interval-60s)\n   Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy3-monitor-interval-60s)\n")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource delete dummies-clone")
        ac(output, "Removing group: dummies (and all resources within group)\nStopping all resources in group: dummies...\nDeleting Resource - dummy1\nDeleting Resource - dummy2\nDeleting Resource (and group and clone) - dummy3\n")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show")
        ac(output, "NO resources configured\n")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource create dummy1 Dummy --no-default-ops --group dummies")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource create dummy2 Dummy --no-default-ops --group dummies")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource create dummy3 Dummy --no-default-ops --group dummies")
        ac(output, "")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource master dummies")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show dummies-master")
        ac(output, " Master: dummies-master\n  Group: dummies\n   Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy1-monitor-interval-60s)\n   Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy2-monitor-interval-60s)\n   Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy3-monitor-interval-60s)\n")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource unclone dummies-master")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show")
        ac(output, " Resource Group: dummies\n     dummy1\t(ocf::heartbeat:Dummy):\tStopped \n     dummy2\t(ocf::heartbeat:Dummy):\tStopped \n     dummy3\t(ocf::heartbeat:Dummy):\tStopped \n")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource master dummies")
        ac(output, "")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show dummies-master")
        ac(output, " Master: dummies-master\n  Group: dummies\n   Resource: dummy1 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy1-monitor-interval-60s)\n   Resource: dummy2 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy2-monitor-interval-60s)\n   Resource: dummy3 (class=ocf provider=heartbeat type=Dummy)\n    Operations: monitor interval=60s (dummy3-monitor-interval-60s)\n")
        assert retVal == 0

        output, retVal = pcs(temp_cib, "resource delete dummies-master")
        ac(output, "Removing group: dummies (and all resources within group)\nStopping all resources in group: dummies...\nDeleting Resource - dummy1\nDeleting Resource - dummy2\nDeleting Resource (and group and M/S) - dummy3\n")
        assert retVal == 0
        output, retVal = pcs(temp_cib, "resource show")
        ac(output, "NO resources configured\n")
        assert retVal == 0


if __name__ == "__main__":
    unittest.main()

