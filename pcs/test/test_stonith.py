from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil

from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.misc import (
    ac,
    get_test_resource as rc,
)
from pcs.test.tools.pcs_runner import pcs, PcsRunner
from pcs.test.tools import pcs_unittest as unittest

from pcs import utils

empty_cib = rc("cib-empty.xml")
temp_cib = rc("temp-cib.xml")


class StonithDescribeTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(temp_cib)


    def test_success(self):
        self.assert_pcs_success(
            "stonith describe fence_apc",
            stdout_start="""\
fence_apc - Fence agent for APC over telnet/ssh

fence_apc is an I/O Fencing agent which can be used with the APC network power switch. It logs into device via telnet/ssh  and reboots a specified outlet. Lengthy telnet/ssh connections should be avoided while a GFS cluster  is  running  because  the  connection will block any necessary fencing actions.

Stonith options:
"""
        )


    def test_nonextisting_agent(self):
        self.assert_pcs_fail(
            "stonith describe fence_noexist",
            (
                "Error: Agent 'fence_noexist' is not installed or does not"
                " provide valid metadata: Metadata query for"
                " stonith:fence_noexist failed: -5\n"
            )
        )


    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "stonith describe",
            stdout_start="\nUsage: pcs stonith describe...\n"
        )


    def test_too_many_params(self):
        self.assert_pcs_fail(
            "stonith describe agent1 agent2",
            stdout_start="\nUsage: pcs stonith describe...\n"
        )


class StonithTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def testStonithCreation(self):
        output, returnVal = pcs(temp_cib, "stonith create test1 fence_noxist")
        ac(output, "Error: Agent 'fence_noxist' is not installed or does not provide valid metadata: Metadata query for stonith:fence_noxist failed: -5, use --force to override\n")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "stonith create test1 fence_noxist --force")
        ac(output, "Warning: Agent 'fence_noxist' is not installed or does not provide valid metadata: Metadata query for stonith:fence_noxist failed: -5\n")
        self.assertEqual(returnVal, 0)

        output, returnVal = pcs(temp_cib, "stonith create test2 fence_apc")
        assert returnVal == 1
        ac(output,"Error: missing required option(s): 'ipaddr, login' for resource type: stonith:fence_apc (use --force to override)\n")

        output, returnVal = pcs(temp_cib, "stonith create test2 fence_ilo --force")
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, "stonith create test3 fence_ilo bad_argument=test")
        assert returnVal == 1
        assert output == "Error: resource option(s): 'bad_argument', are not recognized for resource type: 'stonith:fence_ilo' (use --force to override)\n",[output]

        output, returnVal = pcs(temp_cib, "stonith create test9 fence_apc pcmk_status_action=xxx")
        assert returnVal == 1
        ac(output,"Error: missing required option(s): 'ipaddr, login' for resource type: stonith:fence_apc (use --force to override)\n")

        output, returnVal = pcs(temp_cib, "stonith create test9 fence_ilo pcmk_status_action=xxx --force")
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, "stonith show test9")
        ac(output, """\
 Resource: test9 (class=stonith type=fence_ilo)
  Attributes: pcmk_status_action=xxx
  Operations: monitor interval=60s (test9-monitor-interval-60s)
""")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, "stonith delete test9")
        assert returnVal == 0
        assert output == "Deleting Resource - test9\n",[output]

        output, returnVal = pcs(temp_cib, "stonith create test3 fence_ilo ipaddr=test")
        assert returnVal == 1
        ac(output,"Error: missing required option(s): 'login' for resource type: stonith:fence_ilo (use --force to override)\n")

        output, returnVal = pcs(temp_cib, "stonith create test3 fence_ilo ipaddr=test --force")
        assert returnVal == 0
        ac(output,"")

# Testing that pcmk_host_check, pcmk_host_list & pcmk_host_map are allowed for
# stonith agents
        output, returnVal = pcs(temp_cib, 'stonith create apc-fencing fence_apc params ipaddr="morph-apc" login="apc" passwd="apc" switch="1" pcmk_host_map="buzz-01:1;buzz-02:2;buzz-03:3;buzz-04:4;buzz-05:5" pcmk_host_check="static-list" pcmk_host_list="buzz-01,buzz-02,buzz-03,buzz-04,buzz-05"')
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, 'resource show apc-fencing')
        assert returnVal == 1
        assert output == 'Error: unable to find resource \'apc-fencing\'\n',[output]

        output, returnVal = pcs(temp_cib, 'stonith show apc-fencing')
        ac(output, """\
 Resource: apc-fencing (class=stonith type=fence_apc)
  Attributes: ipaddr="morph-apc" login="apc" passwd="apc" switch="1" pcmk_host_map="buzz-01:1;buzz-02:2;buzz-03:3;buzz-04:4;buzz-05:5" pcmk_host_check="static-list" pcmk_host_list="buzz-01,buzz-02,buzz-03,buzz-04,buzz-05"
  Operations: monitor interval=60s (apc-fencing-monitor-interval-60s)
""")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, 'stonith delete apc-fencing')
        assert returnVal == 0
        assert output == 'Deleting Resource - apc-fencing\n',[output]

        output, returnVal = pcs(temp_cib, "stonith update test3 bad_ipaddr=test")
        assert returnVal == 1
        assert output == "Error: resource option(s): 'bad_ipaddr', are not recognized for resource type: 'stonith::fence_ilo' (use --force to override)\n",[output]

        output, returnVal = pcs(temp_cib, "stonith update test3 login=testA")
        assert returnVal == 0
        assert output == "",[output]

        output, returnVal = pcs(temp_cib, "stonith show test2")
        assert returnVal == 0
        assert output == " Resource: test2 (class=stonith type=fence_ilo)\n  Operations: monitor interval=60s (test2-monitor-interval-60s)\n",[output]

        output, returnVal = pcs(temp_cib, "stonith show --full")
        ac(output, """\
 Resource: test1 (class=stonith type=fence_noxist)
  Operations: monitor interval=60s (test1-monitor-interval-60s)
 Resource: test2 (class=stonith type=fence_ilo)
  Operations: monitor interval=60s (test2-monitor-interval-60s)
 Resource: test3 (class=stonith type=fence_ilo)
  Attributes: ipaddr=test login=testA
  Operations: monitor interval=60s (test3-monitor-interval-60s)
""")
        assert returnVal == 0

        output, returnVal = pcs(temp_cib, 'stonith create test-fencing fence_apc pcmk_host_list="rhel7-node1 rhel7-node2" op monitor interval=61s --force')
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, 'config show')
        ac(output, """\
Cluster Name: test99
Corosync Nodes:
 rh7-1 rh7-2
Pacemaker Nodes:

Resources:

Stonith Devices:
 Resource: test1 (class=stonith type=fence_noxist)
  Operations: monitor interval=60s (test1-monitor-interval-60s)
 Resource: test2 (class=stonith type=fence_ilo)
  Operations: monitor interval=60s (test2-monitor-interval-60s)
 Resource: test3 (class=stonith type=fence_ilo)
  Attributes: ipaddr=test login=testA
  Operations: monitor interval=60s (test3-monitor-interval-60s)
 Resource: test-fencing (class=stonith type=fence_apc)
  Attributes: pcmk_host_list="rhel7-node1
  Operations: monitor interval=61s (test-fencing-monitor-interval-61s)
Fencing Levels:

Location Constraints:
Ordering Constraints:
Colocation Constraints:
Ticket Constraints:

Alerts:
 No alerts defined

Resources Defaults:
 No defaults set
Operations Defaults:
 No defaults set

Cluster Properties:

Quorum:
  Options:
""")
        assert returnVal == 0

    def test_stonith_create_provides_unfencing(self):
        if utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "stonith create f1 fence_scsi"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "stonith create f2 fence_scsi meta provides=unfencing"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "stonith create f3 fence_scsi meta provides=something"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "stonith create f4 fence_xvm meta provides=something"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "stonith show --full")
        ac(output, """\
 Resource: f1 (class=stonith type=fence_scsi)
  Meta Attrs: provides=unfencing 
  Operations: monitor interval=60s (f1-monitor-interval-60s)
 Resource: f2 (class=stonith type=fence_scsi)
  Meta Attrs: provides=unfencing 
  Operations: monitor interval=60s (f2-monitor-interval-60s)
 Resource: f3 (class=stonith type=fence_scsi)
  Meta Attrs: provides=unfencing 
  Operations: monitor interval=60s (f3-monitor-interval-60s)
 Resource: f4 (class=stonith type=fence_xvm)
  Meta Attrs: provides=something 
  Operations: monitor interval=60s (f4-monitor-interval-60s)
""")
        self.assertEqual(0, returnVal)

    def test_stonith_create_provides_unfencing_rhel6(self):
        if not utils.is_rhel6():
            return

        output, returnVal = pcs(
            temp_cib,
            "stonith create f1 fence_mpath key=abc"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "stonith create f2 fence_mpath key=abc meta provides=unfencing"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "stonith create f3 fence_mpath key=abc meta provides=something"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "stonith create f4 fence_xvm meta provides=something"
        )
        ac(output, "")
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "stonith show --full")
        ac(output, """\
 Resource: f1 (class=stonith type=fence_mpath)
  Attributes: key=abc
  Meta Attrs: provides=unfencing 
  Operations: monitor interval=60s (f1-monitor-interval-60s)
 Resource: f2 (class=stonith type=fence_mpath)
  Attributes: key=abc
  Meta Attrs: provides=unfencing 
  Operations: monitor interval=60s (f2-monitor-interval-60s)
 Resource: f3 (class=stonith type=fence_mpath)
  Attributes: key=abc
  Meta Attrs: provides=unfencing 
  Operations: monitor interval=60s (f3-monitor-interval-60s)
 Resource: f4 (class=stonith type=fence_xvm)
  Meta Attrs: provides=something 
  Operations: monitor interval=60s (f4-monitor-interval-60s)
""")
        self.assertEqual(0, returnVal)

    def testStonithFenceConfirm(self):
        output, returnVal = pcs(temp_cib, "stonith fence blah blah")
        assert returnVal == 1
        assert output == "Error: must specify one (and only one) node to fence\n"

        output, returnVal = pcs(temp_cib, "stonith confirm blah blah")
        assert returnVal == 1
        assert output == "Error: must specify one (and only one) node to confirm fenced\n"

    def testPcmkHostList(self):
        output, returnVal = pcs(temp_cib, "stonith create F1 fence_apc 'pcmk_host_list=nodea nodeb' --force")
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, "stonith show F1")
        ac(output, """\
 Resource: F1 (class=stonith type=fence_apc)
  Attributes: pcmk_host_list="nodea nodeb"
  Operations: monitor interval=60s (F1-monitor-interval-60s)
""")
        assert returnVal == 0

    def testPcmkHostAllowsMissingPort(self):
        # Test that port is not required when pcmk_host_argument or
        # pcmk_host_list or pcmk_host_map is specified
        # Port is temporarily an optional parameter. Once we are getting
        # metadata from pacemaker, this will be reviewed and fixed.
        output, returnVal = pcs(
            temp_cib,
            'stonith create apc-1 fence_apc params ipaddr="ip" login="apc"'
        )
#        ac(output, """\
#Error: missing required option(s): 'port' for resource type: stonith:fence_apc (use --force to override)
#""")
#        self.assertEquals(returnVal, 1)
        ac(output, "")
        self.assertEqual(returnVal, 0)

        output, returnVal = pcs(
            temp_cib,
            'stonith create apc-2 fence_apc params ipaddr="ip" login="apc" pcmk_host_map="buzz-01:1;buzz-02:2"'
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        output, returnVal = pcs(
            temp_cib,
            'stonith create apc-3 fence_apc params ipaddr="ip" login="apc" pcmk_host_list="buzz-01,buzz-02"'
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

        output, returnVal = pcs(
            temp_cib,
            'stonith create apc-4 fence_apc params ipaddr="ip" login="apc" pcmk_host_argument="buzz-01"'
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)

    def testFenceLevels(self):
        output, returnVal = pcs(temp_cib, "stonith level remove 1 rh7-2 F1")
        assert returnVal == 1
        ac (output,'Error: unable to remove fencing level, fencing level for node: rh7-2, at level: 1, with device: F1 doesn\'t exist\n')

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith create F1 fence_apc 'pcmk_host_list=nodea nodeb' ipaddr=ip login=lgn")
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, "stonith create F2 fence_apc 'pcmk_host_list=nodea nodeb' ipaddr=ip login=lgn")
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, "stonith create F3 fence_apc 'pcmk_host_list=nodea nodeb' ipaddr=ip login=lgn")
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, "stonith create F4 fence_apc 'pcmk_host_list=nodea nodeb' ipaddr=ip login=lgn")
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, "stonith create F5 fence_apc 'pcmk_host_list=nodea nodeb' ipaddr=ip login=lgn")
        assert returnVal == 0
        ac(output,"")

        output, returnVal = pcs(temp_cib, "stonith level add NaN rh7-1 F3,F4")
        ac(output, "Error: invalid level 'NaN', use a positive integer\n")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "stonith level add -10 rh7-1 F3,F4")
        ac(output, "Error: invalid level '-10', use a positive integer\n")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "stonith level add 10abc rh7-1 F3,F4")
        ac(output, "Error: invalid level '10abc', use a positive integer\n")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "stonith level add 0 rh7-1 F3,F4")
        ac(output, "Error: invalid level '0', use a positive integer\n")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "stonith level add 000 rh7-1 F3,F4")
        ac(output, "Error: invalid level '000', use a positive integer\n")
        assert returnVal == 1

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-1 F3,F4")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith level add 2 rh7-1 F5,F2")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith level add 2 rh7-1 F5,F2")
        assert returnVal == 1
        assert output == 'Error: unable to add fencing level, fencing level for node: rh7-1, at level: 2, with device: F5,F2 already exists\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-2 F1")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith level add 002 rh7-2 F2")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith show")
        assert returnVal == 0
        ac(output,"""\
 F1\t(stonith:fence_apc):\tStopped
 F2\t(stonith:fence_apc):\tStopped
 F3\t(stonith:fence_apc):\tStopped
 F4\t(stonith:fence_apc):\tStopped
 F5\t(stonith:fence_apc):\tStopped
 Node: rh7-1
  Level 1 - F3,F4
  Level 2 - F5,F2
 Node: rh7-2
  Level 1 - F1
  Level 2 - F2
""")

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ' Node: rh7-1\n  Level 1 - F3,F4\n  Level 2 - F5,F2\n Node: rh7-2\n  Level 1 - F1\n  Level 2 - F2\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level remove 1 rh7-2 F1")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith level remove 1 rh7-2 F1")
        assert returnVal == 1
        assert output == 'Error: unable to remove fencing level, fencing level for node: rh7-2, at level: 1, with device: F1 doesn\'t exist\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ' Node: rh7-1\n  Level 1 - F3,F4\n  Level 2 - F5,F2\n Node: rh7-2\n  Level 2 - F2\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level clear rh7-1a")
        assert returnVal == 0
        output = ""

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ' Node: rh7-1\n  Level 1 - F3,F4\n  Level 2 - F5,F2\n Node: rh7-2\n  Level 2 - F2\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level clear rh7-1")
        assert returnVal == 0
        output = ""

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ' Node: rh7-2\n  Level 2 - F2\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level add 2 rh7-1 F5,F2")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-1 F3,F4")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ' Node: rh7-1\n  Level 1 - F3,F4\n  Level 2 - F5,F2\n Node: rh7-2\n  Level 2 - F2\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level clear")
        assert returnVal == 0
        assert output == ""

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == '',[output]

        output, returnVal = pcs(temp_cib, "stonith level 1")
        assert returnVal == 1
        assert output.startswith("pcs stonith level: invalid option")
#        ac (output,"pcs stonith level: invalid option -- '1'\n\nUsage: pcs stonith level...\n    level\n        Lists all of the fencing levels currently configured\n\n    level add <level> <node> <devices>\n        Add the fencing level for the specified node with a comma separated\n        list of devices (stonith ids) to attempt for that node at that level.\n        Fence levels are attempted in numerical order (starting with 1) if\n        a level succeeds (meaning all devices are successfully fenced in that\n        level) then no other levels are tried, and the node is considered\n        fenced.\n\n    level remove <level> [node id] [devices id] ... [device id]\n        Removes the fence level for the level, node and/or devices specified\n        If no nodes or devices are specified then the fence level is removed\n\n    level clear [node|device id(s)]\n        Clears the fence levels on the node (or device id) specified or clears\n        all fence levels if a node/device id is not specified.  If more than\n        one device id is specified they must be separated by a comma and no\n        spaces.  Example: pcs stonith level clear dev_a,dev_b\n\n    level verify\n        Verifies all fence devices and nodes specified in fence levels exist\n\n")

        output, returnVal = pcs(temp_cib, "stonith level abcd")
        assert returnVal == 1
        assert output.startswith("pcs stonith level: invalid option")
#        assert output == "pcs stonith level: invalid option -- 'abcd'\n\nUsage: pcs stonith level...\n    level\n        Lists all of the fencing levels currently configured\n\n    level add <level> <node> <devices>\n        Add the fencing level for the specified node with a comma separated\n        list of devices (stonith ids) to attempt for that node at that level.\n        Fence levels are attempted in numerical order (starting with 1) if\n        a level succeeds (meaning all devices are successfully fenced in that\n        level) then no other levels are tried, and the node is considered\n        fenced.\n\n    level remove <level> [node id] [devices id] ... [device id]\n        Removes the fence level for the level, node and/or devices specified\n        If no nodes or devices are specified then the fence level is removed\n\n    level clear [node|device id(s)]\n        Clears the fence levels on the node (or device id) specified or clears\n        all fence levels if a node/device id is not specified.  If more than\n        one device id is specified they must be separated by a comma and no\n        spaces.  Example: pcs stonith level clear dev_a,dev_b\n\n    level verify\n        Verifies all fence devices and nodes specified in fence levels exist\n\n",[output]

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-1 blah")
        assert returnVal == 1
        assert output == 'Error: blah is not a stonith id (use --force to override)\n'

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-1 blah --force")
        assert returnVal == 0
        assert output == ''

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ' Node: rh7-1\n  Level 1 - blah\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-9 F1")
        assert returnVal == 1
        assert output == 'Error: rh7-9 is not currently a node (use --force to override)\n'

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ' Node: rh7-1\n  Level 1 - blah\n',[output]

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-9 F1 --force")
        assert returnVal == 0
        assert output == ''

        output, returnVal = pcs(temp_cib, "stonith level")
        assert returnVal == 0
        assert output == ' Node: rh7-1\n  Level 1 - blah\n Node: rh7-9\n  Level 1 - F1\n',[output]

        o,r = pcs(temp_cib, "stonith level remove 1")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "stonith level add 1 rh7-1 F1,F2")
        o,r = pcs(temp_cib, "stonith level add 2 rh7-1 F1,F2")
        o,r = pcs(temp_cib, "stonith level add 3 rh7-1 F1,F2")
        o,r = pcs(temp_cib, "stonith level add 4 rh7-1 F1,F2")
        o,r = pcs(temp_cib, "stonith level add 5 rh7-1 F1,F2")
        o,r = pcs(temp_cib, "stonith level add 1 rh7-2 F3")
        o,r = pcs(temp_cib, "stonith level add 2 rh7-2 F3")

        o,r = pcs(temp_cib, "stonith level remove 5 rh7-1")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "stonith level remove 4 rh7-1 F2")
        assert r == 1
        assert o == "Error: unable to remove fencing level, fencing level for node: rh7-1, at level: 4, with device: F2 doesn't exist\n"

        o,r = pcs(temp_cib, "stonith level remove 4 rh7-1 F1")
        assert r == 1
        assert o == "Error: unable to remove fencing level, fencing level for node: rh7-1, at level: 4, with device: F1 doesn't exist\n"

        o,r = pcs(temp_cib, "stonith level remove 4 rh7-1")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "stonith level remove 3")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "stonith level remove 2 F1 F2")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "stonith level")
        assert r == 0
        ac(o," Node: rh7-1\n  Level 1 - F1,F2\n Node: rh7-2\n  Level 1 - F3\n  Level 2 - F3\n")

        o,r = pcs(temp_cib, "stonith level remove 2 F3")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "stonith level remove 1 rh7-1")
        assert r == 0
        assert o == ""

        o,r = pcs(temp_cib, "stonith level")
        assert r == 0
        ac(o," Node: rh7-2\n  Level 1 - F3\n")

        o,r = pcs(temp_cib, "stonith level add 1 rh7-1 F1,F2")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level clear F4")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level clear F2")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level")
        assert r == 0
        ac(o," Node: rh7-1\n  Level 1 - F1,F2\n Node: rh7-2\n  Level 1 - F3\n")

        o,r = pcs(temp_cib, "stonith level clear F1,F2")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level")
        assert r == 0
        ac(o," Node: rh7-2\n  Level 1 - F3\n")

        o,r = pcs(temp_cib, "stonith level clear")
        o,r = pcs(temp_cib, "stonith level")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level add 10 rh7-1 F1")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level add 010 rh7-1 F2")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level")
        assert r == 0
        ac(o, """\
 Node: rh7-1
  Level 10 - F1
  Level 10 - F2
""")

        o,r = pcs(temp_cib, "stonith level clear")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level add 1 rh7-bad F1 --force")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level verify")
        assert r == 1
        ac(o,"Error: rh7-bad is not currently a node\n")

        o,r = pcs(temp_cib, "stonith level clear")
        o,r = pcs(temp_cib, "stonith level add 1 rh7-1 F1,FBad --force")
        assert r == 0
        ac(o,"")

        o,r = pcs(temp_cib, "stonith level verify")
        assert r == 1
        ac(o,"Error: FBad is not a stonith id\n")

        o,r = pcs(temp_cib, "cluster verify")
        assert r == 1
        ac(o,"Error: FBad is not a stonith id\n")

    def testStonithDeleteRemovesLevel(self):
        output, returnVal = pcs(
            temp_cib, "stonith create n1-ipmi fence_ilo --force"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(
            temp_cib, "stonith create n2-ipmi fence_ilo --force"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(
            temp_cib, "stonith create n1-apc1 fence_apc --force"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(
            temp_cib, "stonith create n1-apc2 fence_apc --force"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(
            temp_cib, "stonith create n2-apc1 fence_apc --force"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(
            temp_cib, "stonith create n2-apc2 fence_apc --force"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(
            temp_cib, "stonith create n2-apc3 fence_apc --force"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-1 n1-ipmi")
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(
            temp_cib, "stonith level add 2 rh7-1 n1-apc1,n1-apc2,n2-apc2"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(temp_cib, "stonith level add 1 rh7-2 n2-ipmi")
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(
            temp_cib, "stonith level add 2 rh7-2 n2-apc1,n2-apc2,n2-apc3"
        )
        self.assertEqual(returnVal, 0)
        ac(output, "")

        output, returnVal = pcs(temp_cib, "stonith")
        self.assertEqual(returnVal, 0)
        ac(output, """\
 n1-ipmi\t(stonith:fence_ilo):\tStopped
 n2-ipmi\t(stonith:fence_ilo):\tStopped
 n1-apc1\t(stonith:fence_apc):\tStopped
 n1-apc2\t(stonith:fence_apc):\tStopped
 n2-apc1\t(stonith:fence_apc):\tStopped
 n2-apc2\t(stonith:fence_apc):\tStopped
 n2-apc3\t(stonith:fence_apc):\tStopped
 Node: rh7-1
  Level 1 - n1-ipmi
  Level 2 - n1-apc1,n1-apc2,n2-apc2
 Node: rh7-2
  Level 1 - n2-ipmi
  Level 2 - n2-apc1,n2-apc2,n2-apc3
""")

        output, returnVal = pcs(temp_cib, "stonith delete n2-apc2")
        self.assertEqual(returnVal, 0)
        ac(output, "Deleting Resource - n2-apc2\n")

        output, returnVal = pcs(temp_cib, "stonith")
        self.assertEqual(returnVal, 0)
        ac(output, """\
 n1-ipmi\t(stonith:fence_ilo):\tStopped
 n2-ipmi\t(stonith:fence_ilo):\tStopped
 n1-apc1\t(stonith:fence_apc):\tStopped
 n1-apc2\t(stonith:fence_apc):\tStopped
 n2-apc1\t(stonith:fence_apc):\tStopped
 n2-apc3\t(stonith:fence_apc):\tStopped
 Node: rh7-1
  Level 1 - n1-ipmi
  Level 2 - n1-apc1,n1-apc2
 Node: rh7-2
  Level 1 - n2-ipmi
  Level 2 - n2-apc1,n2-apc3
""")

        output, returnVal = pcs(temp_cib, "stonith delete n2-apc1")
        self.assertEqual(returnVal, 0)
        ac(output, "Deleting Resource - n2-apc1\n")

        output, returnVal = pcs(temp_cib, "stonith")
        self.assertEqual(returnVal, 0)
        ac(output, """\
 n1-ipmi\t(stonith:fence_ilo):\tStopped
 n2-ipmi\t(stonith:fence_ilo):\tStopped
 n1-apc1\t(stonith:fence_apc):\tStopped
 n1-apc2\t(stonith:fence_apc):\tStopped
 n2-apc3\t(stonith:fence_apc):\tStopped
 Node: rh7-1
  Level 1 - n1-ipmi
  Level 2 - n1-apc1,n1-apc2
 Node: rh7-2
  Level 1 - n2-ipmi
  Level 2 - n2-apc3
""")

        output, returnVal = pcs(temp_cib, "stonith delete n2-apc3")
        self.assertEqual(returnVal, 0)
        ac(output, "Deleting Resource - n2-apc3\n")

        output, returnVal = pcs(temp_cib, "stonith")
        self.assertEqual(returnVal, 0)
        ac(output, """\
 n1-ipmi\t(stonith:fence_ilo):\tStopped
 n2-ipmi\t(stonith:fence_ilo):\tStopped
 n1-apc1\t(stonith:fence_apc):\tStopped
 n1-apc2\t(stonith:fence_apc):\tStopped
 Node: rh7-1
  Level 1 - n1-ipmi
  Level 2 - n1-apc1,n1-apc2
 Node: rh7-2
  Level 1 - n2-ipmi
""")

        output, returnVal = pcs(temp_cib, "resource delete n1-apc1")
        self.assertEqual(returnVal, 0)
        ac(output, "Deleting Resource - n1-apc1\n")

        output, returnVal = pcs(temp_cib, "stonith")
        self.assertEqual(returnVal, 0)
        ac(output, """\
 n1-ipmi\t(stonith:fence_ilo):\tStopped
 n2-ipmi\t(stonith:fence_ilo):\tStopped
 n1-apc2\t(stonith:fence_apc):\tStopped
 Node: rh7-1
  Level 1 - n1-ipmi
  Level 2 - n1-apc2
 Node: rh7-2
  Level 1 - n2-ipmi
""")

        output, returnVal = pcs(temp_cib, "resource delete n1-apc2")
        self.assertEqual(returnVal, 0)
        ac(output, "Deleting Resource - n1-apc2\n")

        output, returnVal = pcs(temp_cib, "stonith")
        self.assertEqual(returnVal, 0)
        ac(output, """\
 n1-ipmi\t(stonith:fence_ilo):\tStopped
 n2-ipmi\t(stonith:fence_ilo):\tStopped
 Node: rh7-1
  Level 1 - n1-ipmi
 Node: rh7-2
  Level 1 - n2-ipmi
""")

    def testNoStonithWarning(self):
        o,r = pcs(temp_cib, "status")
        assert "WARNING: no stonith devices and " in o

        o,r = pcs(temp_cib, "stonith create test_stonith fence_apc ipaddr=ip login=lgn,  pcmk_host_argument=node1")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "status")
        assert "WARNING: no stonith devices and " not in o

        o,r = pcs(temp_cib, "stonith delete test_stonith")
        ac(o,"Deleting Resource - test_stonith\n")
        assert r == 0

        o,r = pcs(temp_cib, "stonith create test_stonith fence_apc ipaddr=ip login=lgn,  pcmk_host_argument=node1 --clone")
        ac(o,"")
        assert r == 0

        o,r = pcs(temp_cib, "status")
        assert "WARNING: no stonith devices and " not in o
