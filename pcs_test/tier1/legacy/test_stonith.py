# pylint: disable=too-many-lines
import json
import re
import shutil
from textwrap import dedent
from threading import Lock
from unittest import TestCase

from pcs.common.str_tools import indent

from pcs_test.tier1.cib_resource.common import ResourceTest
from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.bin_mock import get_mock_settings
from pcs_test.tools.fixture_cib import CachedCibFixture
from pcs_test.tools.misc import ParametrizedTestMetaClass
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    is_minimum_pacemaker_version,
    outdent,
    skip_unless_crm_rule,
    write_data_to_tmpfile,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import (
    PcsRunner,
    pcs,
)

# pylint: disable=invalid-name
# pylint: disable=line-too-long

PCMK_2_0_3_PLUS = is_minimum_pacemaker_version(2, 0, 3)
ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)

empty_cib = rc("cib-empty.xml")


class StonithDescribeTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(cib_file=None)
        self.pcs_runner.mock_settings = get_mock_settings(
            "crm_resource_binary", "pacemaker_fenced"
        )

    def test_success(self):
        self.assert_pcs_success(
            "stonith describe fence_apc".split(),
            stdout_start=dedent(
                """\
                fence_apc - Fence agent for APC over telnet/ssh

                fence_apc is an I/O Fencing agent which can be used with the APC network power switch. It logs into device via telnet/ssh  and reboots a specified outlet. Lengthy telnet/ssh connections should be avoided while a GFS cluster  is  running  because  the  connection will block any necessary fencing actions.

                Stonith options:
                """
            ),
        )

    def test_full(self):
        stdout, pcs_returncode = self.pcs_runner.run(
            "stonith describe fence_apc --full".split(),
        )
        self.assertEqual(0, pcs_returncode)
        self.assertTrue("pcmk_list_retries" in stdout)

    def test_nonextisting_agent(self):
        self.assert_pcs_fail(
            "stonith describe fence_noexist".split(),
            stdout_full=(
                "Error: Agent 'stonith:fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22), "
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "stonith describe".split(),
            stdout_start="\nUsage: pcs stonith describe...\n",
        )

    def test_too_many_params(self):
        self.assert_pcs_fail(
            "stonith describe agent1 agent2".split(),
            stdout_start="\nUsage: pcs stonith describe...\n",
        )

    def test_pcsd_interface(self):
        self.maxDiff = None
        stdout, returncode = self.pcs_runner.run(
            "stonith get_fence_agent_info stonith:fence_apc".split()
        )
        self.assertEqual(returncode, 0)
        self.assertEqual(
            json.loads(stdout),
            {
                "name": "stonith:fence_apc",
                "standard": "stonith",
                "provider": None,
                "type": "fence_apc",
                "shortdesc": "Fence agent for APC over telnet/ssh",
                "longdesc": "fence_apc is an I/O Fencing agent which can be used with the APC network power switch. It logs into device via telnet/ssh  and reboots a specified outlet. Lengthy telnet/ssh connections should be avoided while a GFS cluster  is  running  because  the  connection will block any necessary fencing actions.",
                "parameters": [
                    {
                        "name": "action",
                        "shortdesc": "Fencing action",
                        "longdesc": None,
                        "type": "string",
                        "default": "reboot",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": True,
                        "deprecated_by": [
                            "pcmk_off_action",
                            "pcmk_reboot_action",
                        ],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "cmd_prompt",
                        "shortdesc": "Force Python regex for command prompt",
                        "longdesc": None,
                        "type": "string",
                        "default": "['\\n>', '\\napc>']",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": True,
                        "deprecated_by": ["command_prompt"],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "command_prompt",
                        "shortdesc": "Force Python regex for command prompt",
                        "longdesc": None,
                        "type": "string",
                        "default": "['\\n>', '\\napc>']",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "identity_file",
                        "shortdesc": "Identity file (private key) for SSH",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "inet4_only",
                        "shortdesc": "Forces agent to use IPv4 addresses only",
                        "longdesc": None,
                        "type": "boolean",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "inet6_only",
                        "shortdesc": "Forces agent to use IPv6 addresses only",
                        "longdesc": None,
                        "type": "boolean",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "ip",
                        "shortdesc": "IP address or hostname of fencing device",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": True,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "ipaddr",
                        "shortdesc": "IP address or hostname of fencing device",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": True,
                        "advanced": False,
                        "deprecated": True,
                        "deprecated_by": ["ip"],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "ipport",
                        "shortdesc": "TCP/UDP port to use for connection with device",
                        "longdesc": None,
                        "type": "integer",
                        "default": "23",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "login",
                        "shortdesc": "Login name",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": True,
                        "advanced": False,
                        "deprecated": True,
                        "deprecated_by": ["username"],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "passwd",
                        "shortdesc": "Login password or passphrase",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": True,
                        "deprecated_by": ["password"],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "passwd_script",
                        "shortdesc": "Script to run to retrieve password",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": True,
                        "deprecated_by": ["password_script"],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "password",
                        "shortdesc": "Login password or passphrase",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "password_script",
                        "shortdesc": "Script to run to retrieve password",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "plug",
                        "shortdesc": "Physical plug number on device, UUID or identification of machine",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "port",
                        "shortdesc": "Physical plug number on device, UUID or identification of machine",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": True,
                        "deprecated_by": ["plug"],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "secure",
                        "shortdesc": "Use SSH connection",
                        "longdesc": None,
                        "type": "boolean",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": True,
                        "deprecated_by": ["ssh"],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "ssh",
                        "shortdesc": "Use SSH connection",
                        "longdesc": None,
                        "type": "boolean",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "ssh_options",
                        "shortdesc": "SSH options to use",
                        "longdesc": None,
                        "type": "string",
                        "default": "-1 -c blowfish",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "switch",
                        "shortdesc": "Physical switch number on device",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "username",
                        "shortdesc": "Login name",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": True,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "quiet",
                        "shortdesc": "Disable logging to stderr. Does not affect --verbose or --debug-file or logging to syslog.",
                        "longdesc": None,
                        "type": "boolean",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "verbose",
                        "shortdesc": "Verbose mode",
                        "longdesc": None,
                        "type": "boolean",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "debug",
                        "shortdesc": "Write debug information to given file",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": True,
                        "deprecated_by": ["debug_file"],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "debug_file",
                        "shortdesc": "Write debug information to given file",
                        "longdesc": None,
                        "type": "string",
                        "default": None,
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "separator",
                        "shortdesc": "Separator for CSV created by 'list' operation",
                        "longdesc": None,
                        "type": "string",
                        "default": ",",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "delay",
                        "shortdesc": "Wait X seconds before fencing is started",
                        "longdesc": None,
                        "type": "second",
                        "default": "0",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "login_timeout",
                        "shortdesc": "Wait X seconds for cmd prompt after login",
                        "longdesc": None,
                        "type": "second",
                        "default": "5",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "power_timeout",
                        "shortdesc": "Test X seconds for status change after ON/OFF",
                        "longdesc": None,
                        "type": "second",
                        "default": "20",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "power_wait",
                        "shortdesc": "Wait X seconds after issuing ON/OFF",
                        "longdesc": None,
                        "type": "second",
                        "default": "0",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "shell_timeout",
                        "shortdesc": "Wait X seconds for cmd prompt after issuing command",
                        "longdesc": None,
                        "type": "second",
                        "default": "3",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "retry_on",
                        "shortdesc": "Count of attempts to retry power on",
                        "longdesc": None,
                        "type": "integer",
                        "default": "1",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "ssh_path",
                        "shortdesc": "Path to ssh binary",
                        "longdesc": None,
                        "type": "string",
                        "default": "/usr/bin/ssh",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "telnet_path",
                        "shortdesc": "Path to telnet binary",
                        "longdesc": None,
                        "type": "string",
                        "default": "/usr/bin/telnet",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_host_argument",
                        "shortdesc": "An alternate parameter to supply instead of 'port'",
                        "longdesc": "An alternate parameter to supply instead of 'port'.\nSome devices do not support the standard 'port' parameter or may provide additional ones. Use this to specify an alternate, device-specific, parameter that should indicate the machine to be fenced. A value of 'none' can be used to tell the cluster not to supply any additional parameters.",
                        "type": "string",
                        "default": "port",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_host_map",
                        "shortdesc": "A mapping of host names to ports numbers for devices that do not support host names.",
                        "longdesc": "A mapping of host names to ports numbers for devices that do not support host names.\nEg. node1:1;node2:2,3 would tell the cluster to use port 1 for node1 and ports 2 and 3 for node2",
                        "type": "string",
                        "default": "",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_host_list",
                        "shortdesc": "A list of machines controlled by this device (Optional unless pcmk_host_check=static-list).",
                        "longdesc": "A list of machines controlled by this device (Optional unless pcmk_host_check=static-list).\nEg. node1,node2,node3",
                        "type": "string",
                        "default": "",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_host_check",
                        "shortdesc": "How to determine which machines are controlled by the device.",
                        "longdesc": "How to determine which machines are controlled by the device.\nAllowed values: dynamic-list (query the device via the 'list' command), static-list (check the pcmk_host_list attribute), status (query the device via the 'status' command), none (assume every device can fence every machine)",
                        "type": "string",
                        "default": "dynamic-list",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_delay_max",
                        "shortdesc": "Enable a delay of no more than the time specified before executing fencing actions. Pacemaker derives the overall delay by taking the value of pcmk_delay_base and adding a random delay value such that the sum is kept below this maximum.",
                        "longdesc": "Enable a delay of no more than the time specified before executing fencing actions. Pacemaker derives the overall delay by taking the value of pcmk_delay_base and adding a random delay value such that the sum is kept below this maximum.\nThis prevents double fencing when using slow devices such as sbd.\nUse this to enable a random delay for fencing actions.\nThe overall delay is derived from this random delay value adding a static delay so that the sum is kept below the maximum delay.",
                        "type": "time",
                        "default": "0s",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_delay_base",
                        "shortdesc": "Enable a base delay for fencing actions and specify base delay value.",
                        "longdesc": 'Enable a base delay for fencing actions and specify base delay value.\nThis enables a static delay for fencing actions, which can help avoid "death matches" where two nodes try to fence each other at the same time. If pcmk_delay_max is also used, a random delay will be added such that the total delay is kept below that value.\nThis can be set to a single time value to apply to any node targeted by this device (useful if a separate device is configured for each target), or to a node map (for example, "node1:1s;node2:5") to set a different value per target.',
                        "type": "string",
                        "default": "0s",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_action_limit",
                        "shortdesc": "The maximum number of actions can be performed in parallel on this device",
                        "longdesc": "The maximum number of actions can be performed in parallel on this device.\nCluster property concurrent-fencing=true needs to be configured first.\nThen use this to specify the maximum number of actions can be performed in parallel on this device. -1 is unlimited.",
                        "type": "integer",
                        "default": "1",
                        "enum_values": None,
                        "required": False,
                        "advanced": False,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_reboot_action",
                        "shortdesc": "An alternate command to run instead of 'reboot'",
                        "longdesc": "An alternate command to run instead of 'reboot'.\nSome devices do not support the standard commands or may provide additional ones.\nUse this to specify an alternate, device-specific, command that implements the 'reboot' action.",
                        "type": "string",
                        "default": "reboot",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_reboot_timeout",
                        "shortdesc": "Specify an alternate timeout to use for reboot actions instead of stonith-timeout",
                        "longdesc": "Specify an alternate timeout to use for reboot actions instead of stonith-timeout.\nSome devices need much more/less time to complete than normal.\nUse this to specify an alternate, device-specific, timeout for 'reboot' actions.",
                        "type": "time",
                        "default": "60s",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_reboot_retries",
                        "shortdesc": "The maximum number of times to retry the 'reboot' command within the timeout period",
                        "longdesc": "The maximum number of times to retry the 'reboot' command within the timeout period.\nSome devices do not support multiple connections. Operations may 'fail' if the device is busy with another task so Pacemaker will automatically retry the operation, if there is time remaining. Use this option to alter the number of times Pacemaker retries 'reboot' actions before giving up.",
                        "type": "integer",
                        "default": "2",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_off_action",
                        "shortdesc": "An alternate command to run instead of 'off'",
                        "longdesc": "An alternate command to run instead of 'off'.\nSome devices do not support the standard commands or may provide additional ones.\nUse this to specify an alternate, device-specific, command that implements the 'off' action.",
                        "type": "string",
                        "default": "off",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_off_timeout",
                        "shortdesc": "Specify an alternate timeout to use for off actions instead of stonith-timeout",
                        "longdesc": "Specify an alternate timeout to use for off actions instead of stonith-timeout.\nSome devices need much more/less time to complete than normal.\nUse this to specify an alternate, device-specific, timeout for 'off' actions.",
                        "type": "time",
                        "default": "60s",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_off_retries",
                        "shortdesc": "The maximum number of times to retry the 'off' command within the timeout period",
                        "longdesc": "The maximum number of times to retry the 'off' command within the timeout period.\nSome devices do not support multiple connections. Operations may 'fail' if the device is busy with another task so Pacemaker will automatically retry the operation, if there is time remaining. Use this option to alter the number of times Pacemaker retries 'off' actions before giving up.",
                        "type": "integer",
                        "default": "2",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_on_action",
                        "shortdesc": "An alternate command to run instead of 'on'",
                        "longdesc": "An alternate command to run instead of 'on'.\nSome devices do not support the standard commands or may provide additional ones.\nUse this to specify an alternate, device-specific, command that implements the 'on' action.",
                        "type": "string",
                        "default": "on",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_on_timeout",
                        "shortdesc": "Specify an alternate timeout to use for on actions instead of stonith-timeout",
                        "longdesc": "Specify an alternate timeout to use for on actions instead of stonith-timeout.\nSome devices need much more/less time to complete than normal.\nUse this to specify an alternate, device-specific, timeout for 'on' actions.",
                        "type": "time",
                        "default": "60s",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_on_retries",
                        "shortdesc": "The maximum number of times to retry the 'on' command within the timeout period",
                        "longdesc": "The maximum number of times to retry the 'on' command within the timeout period.\nSome devices do not support multiple connections. Operations may 'fail' if the device is busy with another task so Pacemaker will automatically retry the operation, if there is time remaining. Use this option to alter the number of times Pacemaker retries 'on' actions before giving up.",
                        "type": "integer",
                        "default": "2",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_list_action",
                        "shortdesc": "An alternate command to run instead of 'list'",
                        "longdesc": "An alternate command to run instead of 'list'.\nSome devices do not support the standard commands or may provide additional ones.\nUse this to specify an alternate, device-specific, command that implements the 'list' action.",
                        "type": "string",
                        "default": "list",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_list_timeout",
                        "shortdesc": "Specify an alternate timeout to use for list actions instead of stonith-timeout",
                        "longdesc": "Specify an alternate timeout to use for list actions instead of stonith-timeout.\nSome devices need much more/less time to complete than normal.\nUse this to specify an alternate, device-specific, timeout for 'list' actions.",
                        "type": "time",
                        "default": "60s",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_list_retries",
                        "shortdesc": "The maximum number of times to retry the 'list' command within the timeout period",
                        "longdesc": "The maximum number of times to retry the 'list' command within the timeout period.\nSome devices do not support multiple connections. Operations may 'fail' if the device is busy with another task so Pacemaker will automatically retry the operation, if there is time remaining. Use this option to alter the number of times Pacemaker retries 'list' actions before giving up.",
                        "type": "integer",
                        "default": "2",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_monitor_action",
                        "shortdesc": "An alternate command to run instead of 'monitor'",
                        "longdesc": "An alternate command to run instead of 'monitor'.\nSome devices do not support the standard commands or may provide additional ones.\nUse this to specify an alternate, device-specific, command that implements the 'monitor' action.",
                        "type": "string",
                        "default": "monitor",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_monitor_timeout",
                        "shortdesc": "Specify an alternate timeout to use for monitor actions instead of stonith-timeout",
                        "longdesc": "Specify an alternate timeout to use for monitor actions instead of stonith-timeout.\nSome devices need much more/less time to complete than normal.\nUse this to specify an alternate, device-specific, timeout for 'monitor' actions.",
                        "type": "time",
                        "default": "60s",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_monitor_retries",
                        "shortdesc": "The maximum number of times to retry the 'monitor' command within the timeout period",
                        "longdesc": "The maximum number of times to retry the 'monitor' command within the timeout period.\nSome devices do not support multiple connections. Operations may 'fail' if the device is busy with another task so Pacemaker will automatically retry the operation, if there is time remaining. Use this option to alter the number of times Pacemaker retries 'monitor' actions before giving up.",
                        "type": "integer",
                        "default": "2",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_status_action",
                        "shortdesc": "An alternate command to run instead of 'status'",
                        "longdesc": "An alternate command to run instead of 'status'.\nSome devices do not support the standard commands or may provide additional ones.\nUse this to specify an alternate, device-specific, command that implements the 'status' action.",
                        "type": "string",
                        "default": "status",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_status_timeout",
                        "shortdesc": "Specify an alternate timeout to use for status actions instead of stonith-timeout",
                        "longdesc": "Specify an alternate timeout to use for status actions instead of stonith-timeout.\nSome devices need much more/less time to complete than normal.\nUse this to specify an alternate, device-specific, timeout for 'status' actions.",
                        "type": "time",
                        "default": "60s",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                    {
                        "name": "pcmk_status_retries",
                        "shortdesc": "The maximum number of times to retry the 'status' command within the timeout period",
                        "longdesc": "The maximum number of times to retry the 'status' command within the timeout period.\nSome devices do not support multiple connections. Operations may 'fail' if the device is busy with another task so Pacemaker will automatically retry the operation, if there is time remaining. Use this option to alter the number of times Pacemaker retries 'status' actions before giving up.",
                        "type": "integer",
                        "default": "2",
                        "enum_values": None,
                        "required": False,
                        "advanced": True,
                        "deprecated": False,
                        "deprecated_by": [],
                        "deprecated_desc": None,
                        "unique_group": None,
                        "reloadable": False,
                    },
                ],
                "actions": [
                    {
                        "name": "on",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "off",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "reboot",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "status",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "list",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "list-status",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "monitor",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "metadata",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "manpage",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "validate-all",
                        "timeout": None,
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "stop",
                        "timeout": "20s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                    {
                        "name": "start",
                        "timeout": "20s",
                        "interval": None,
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    },
                ],
                "default_actions": [
                    {
                        "name": "monitor",
                        "timeout": None,
                        "interval": "60s",
                        "role": None,
                        "start-delay": None,
                        "OCF_CHECK_LEVEL": None,
                        "automatic": False,
                        "on_target": False,
                    }
                ],
            },
        )


class StonithTest(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_stonith")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.temp_corosync_conf = get_tmp_file("tier1_test_stonith")
        write_file_to_tmpfile(rc("corosync.conf"), self.temp_corosync_conf)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.pcs_runner.mock_settings[
            "corosync_conf_file"
        ] = self.temp_corosync_conf.name

    def tearDown(self):
        self.temp_cib.close()
        self.temp_corosync_conf.close()

    @skip_unless_crm_rule()
    def testStonithCreation(self):
        self.assert_pcs_fail(
            "stonith create test1 fence_noexist".split(),
            stdout_full=(
                "Error: Agent 'stonith:fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22), "
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error, use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test1 fence_noexist --force".split(),
            stdout_full=(
                "Warning: Agent 'stonith:fence_noexist' is not installed or does not "
                "provide valid metadata: Agent fence_noexist not found or does "
                "not support meta-data: Invalid argument (22), "
                "Metadata query for stonith:fence_noexist failed: Input/output "
                "error\n"
            ),
        )

        self.assert_pcs_fail(
            "stonith create test2 fence_apc".split(),
            (
                "Error: stonith option 'ip' or 'ipaddr' (deprecated) has to be "
                "specified, use --force to override\n"
                "Error: stonith option 'username' or 'login' (deprecated) has "
                "to be specified, use --force to override\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test2 fence_apc --force".split(),
            stdout_start="Warning: stonith option 'ip' or 'ipaddr' (deprecated) has to be "
            "specified\n"
            "Warning: stonith option 'username' or 'login' (deprecated) has to "
            "be specified\n",
        )

        self.assert_pcs_fail(
            "stonith create test3 fence_apc bad_argument=test".split(),
            stdout_start="Error: invalid stonith option 'bad_argument',"
            " allowed options are:",
        )

        self.assert_pcs_fail(
            "stonith create test9 fence_apc pcmk_status_action=xxx".split(),
            (
                "Error: stonith option 'ip' or 'ipaddr' (deprecated) has to be "
                "specified, use --force to override\n"
                "Error: stonith option 'username' or 'login' (deprecated) has "
                "to be specified, use --force to override\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test9 fence_apc pcmk_status_action=xxx --force".split(),
            stdout_start="Warning: stonith option 'ip' or 'ipaddr' (deprecated) has to be "
            "specified\n"
            "Warning: stonith option 'username' or 'login' (deprecated) has to "
            "be specified\n",
        )

        self.assert_pcs_success(
            "stonith config test9".split(),
            outdent(
                """\
            Resource: test9 (class=stonith type=fence_apc)
              Attributes: test9-instance_attributes
                pcmk_status_action=xxx
              Operations:
                monitor: test9-monitor-interval-60s
                  interval=60s
            """
            ),
        )

        self.assert_pcs_success(
            "stonith delete test9".split(), "Deleting Resource - test9\n"
        )

        self.assert_pcs_fail(
            "stonith create test3 fence_ilo ip=test".split(),
            (
                "Error: stonith option 'username' or 'login' (deprecated) has "
                "to be specified, use --force to override\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test3 fence_ilo ip=test --force".split(),
            stdout_start="Warning: stonith option 'username' or 'login' "
            "(deprecated) has to be specified\n",
        )

        # Testing that pcmk_host_check, pcmk_host_list & pcmk_host_map are
        # allowed for stonith agents
        self.assert_pcs_success(
            "stonith create apc-fencing fence_apc ip=morph-apc username=apc password=apc switch=1 pcmk_host_map=buzz-01:1;buzz-02:2;buzz-03:3;buzz-04:4;buzz-05:5 pcmk_host_check=static-list pcmk_host_list=buzz-01,buzz-02,buzz-03,buzz-04,buzz-05".split(),
        )

        self.assert_pcs_fail(
            "resource config apc-fencing".split(),
            "Warning: Unable to find resource 'apc-fencing'\n"
            "Error: No resource found\n",
        )

        self.assert_pcs_success(
            "stonith config apc-fencing".split(),
            outdent(
                """\
            Resource: apc-fencing (class=stonith type=fence_apc)
              Attributes: apc-fencing-instance_attributes
                ip=morph-apc
                password=apc
                pcmk_host_check=static-list
                pcmk_host_list=buzz-01,buzz-02,buzz-03,buzz-04,buzz-05
                pcmk_host_map=buzz-01:1;buzz-02:2;buzz-03:3;buzz-04:4;buzz-05:5
                switch=1
                username=apc
              Operations:
                monitor: apc-fencing-monitor-interval-60s
                  interval=60s
            """
            ),
        )

        self.assert_pcs_success(
            "stonith remove apc-fencing".split(),
            "Deleting Resource - apc-fencing\n",
        )

        self.assert_pcs_fail(
            (
                "stonith create apc-fencing fence_apc ip=morph-apc username=apc "
                "--agent-validation"
            ).split(),
            stdout_start="Error: Validation result from agent",
        )

        self.assert_pcs_success(
            (
                "stonith create apc-fencing fence_apc ip=morph-apc username=apc "
                "--agent-validation --force"
            ).split(),
            stdout_start="Warning: Validation result from agent",
        )

        self.assert_pcs_success(
            "stonith remove apc-fencing".split(),
            stdout_full="Deleting Resource - apc-fencing\n",
        )

        self.assert_pcs_fail(
            "stonith update test3 bad_ipaddr=test username=login".split(),
            stdout_regexp=(
                "^Error: invalid stonith option 'bad_ipaddr', allowed options"
                " are: [^\n]+, use --force to override\n$"
            ),
        )

        self.assert_pcs_success(
            "stonith update test3 username=testA --agent-validation".split(),
            stdout_start="Warning: The resource was misconfigured before the update,",
        )

        self.assert_pcs_success(
            "stonith config test2".split(),
            outdent(
                """\
            Resource: test2 (class=stonith type=fence_apc)
              Operations:
                monitor: test2-monitor-interval-60s
                  interval=60s
            """
            ),
        )

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
            Resource: test1 (class=stonith type=fence_noexist)
              Operations:
                monitor: test1-monitor-interval-60s
                  interval=60s
            Resource: test2 (class=stonith type=fence_apc)
              Operations:
                monitor: test2-monitor-interval-60s
                  interval=60s
            Resource: test3 (class=stonith type=fence_ilo)
              Attributes: test3-instance_attributes
                ip=test
                username=testA
              Operations:
                monitor: test3-monitor-interval-60s
                  interval=60s
            """
            ),
        )

        self.assert_pcs_success(
            [
                "stonith",
                "create",
                "test-fencing",
                "fence_apc",
                "pcmk_host_list=rhel7-node1 rhel7-node2",
                "op",
                "monitor",
                "interval=61s",
                "--force",
            ],
            stdout_start="Warning: stonith option 'ip' or 'ipaddr' "
            "(deprecated) has to be specified\n"
            "Warning: stonith option 'username' or 'login' (deprecated) has to "
            "be specified\n",
        )

        self.assert_pcs_success(
            "config show".split(),
            outdent(
                """\
            Cluster Name: test99
            Corosync Nodes:
             rh7-1 rh7-2
            Pacemaker Nodes:

            Resources:

            Stonith Devices:
              Resource: test1 (class=stonith type=fence_noexist)
                Operations:
                  monitor: test1-monitor-interval-60s
                    interval=60s
              Resource: test2 (class=stonith type=fence_apc)
                Operations:
                  monitor: test2-monitor-interval-60s
                    interval=60s
              Resource: test3 (class=stonith type=fence_ilo)
                Attributes: test3-instance_attributes
                  ip=test
                  username=testA
                Operations:
                  monitor: test3-monitor-interval-60s
                    interval=60s
              Resource: test-fencing (class=stonith type=fence_apc)
                Attributes: test-fencing-instance_attributes
                  pcmk_host_list="rhel7-node1 rhel7-node2"
                Operations:
                  monitor: test-fencing-monitor-interval-61s
                    interval=61s
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

            Tags:
             No tags defined

            Quorum:
              Options:
            """
            ),
        )

    def test_stonith_create_requires_either_new_or_deprecated(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_fail(
            "stonith create test2 fence_apc".split(),
            (
                "Error: stonith option 'ip' or 'ipaddr' (deprecated) has to be "
                "specified, use --force to override\n"
                "Error: stonith option 'username' or 'login' (deprecated) has "
                "to be specified, use --force to override\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_stonith_create_deprecated_and_obsoleting(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_success(
            "stonith create S fence_apc ip=i login=l password=1234".split(),
            "Warning: stonith option 'login' is deprecated and should not be "
            "used, use 'username' instead\n",
        )
        self.assert_pcs_success(
            "stonith config S".split(),
            outdent(
                """\
            Resource: S (class=stonith type=fence_apc)
              Attributes: S-instance_attributes
                ip=i
                login=l
                password=1234
              Operations:
                monitor: S-monitor-interval-60s
                  interval=60s
            """
            ),
        )

    def test_stonith_create_both_deprecated_and_obsoleting(self):
        # 'ipaddr' and 'login' are obsoleted by 'ip' and 'username'
        self.assert_pcs_success(
            (
                "stonith",
                "create",
                "S",
                "fence_apc",
                "ip=i1",
                "login=l",
                "ipaddr=i2",
                "username=u",
                "password=1234",
            ),
            "Warning: stonith option 'ipaddr' is deprecated and should not be "
            "used, use 'ip' instead\n"
            "Warning: stonith option 'login' is deprecated and should not be "
            "used, use 'username' instead\n",
        )
        self.assert_pcs_success(
            "stonith config S".split(),
            outdent(
                """\
            Resource: S (class=stonith type=fence_apc)
              Attributes: S-instance_attributes
                ip=i1
                ipaddr=i2
                login=l
                password=1234
                username=u
              Operations:
                monitor: S-monitor-interval-60s
                  interval=60s
            """
            ),
        )

    def test_stonith_create_provides_unfencing(self):
        self.assert_pcs_success_ignore_output(
            ("stonith", "create", "f1", "fence_scsi", "--force")
        )
        self.assert_pcs_success_ignore_output(
            (
                "stonith",
                "create",
                "f2",
                "fence_scsi",
                "meta",
                "provides=unfencing",
                "--force",
            )
        )
        self.assert_pcs_success_ignore_output(
            (
                "stonith",
                "create",
                "f3",
                "fence_scsi",
                "meta",
                "provides=something",
                "--force",
            )
        )
        self.assert_pcs_success_ignore_output(
            (
                "stonith",
                "create",
                "f4",
                "fence_xvm",
                "meta",
                "provides=something",
                "--force",
            )
        )
        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
            Resource: f1 (class=stonith type=fence_scsi)
              Meta Attributes: f1-meta_attributes
                provides=unfencing
              Operations:
                monitor: f1-monitor-interval-60s
                  interval=60s
            Resource: f2 (class=stonith type=fence_scsi)
              Meta Attributes: f2-meta_attributes
                provides=unfencing
              Operations:
                monitor: f2-monitor-interval-60s
                  interval=60s
            Resource: f3 (class=stonith type=fence_scsi)
              Meta Attributes: f3-meta_attributes
                provides=unfencing
              Operations:
                monitor: f3-monitor-interval-60s
                  interval=60s
            Resource: f4 (class=stonith type=fence_xvm)
              Meta Attributes: f4-meta_attributes
                provides=something
              Operations:
                monitor: f4-monitor-interval-60s
                  interval=60s
            """
            ),
        )

    def test_stonith_create_action(self):
        self.assert_pcs_fail(
            "stonith create test fence_apc ip=i username=u action=a".split(),
            (
                "Error: stonith option 'action' is deprecated and should not be"
                " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead,"
                " use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )

        self.assert_pcs_success(
            "stonith create test fence_apc ip=i username=u action=a --force".split(),
            stdout_start="Warning: stonith option 'action' is deprecated and should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead\n",
        )

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
                Resource: test (class=stonith type=fence_apc)
                  Attributes: test-instance_attributes
                    action=a
                    ip=i
                    username=u
                  Operations:
                    monitor: test-monitor-interval-60s
                      interval=60s
                """
            ),
        )

    def test_stonith_update_action(self):
        self.assert_pcs_success(
            "stonith create test fence_apc ip=i username=u password=1234".split()
        )

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
                Resource: test (class=stonith type=fence_apc)
                  Attributes: test-instance_attributes
                    ip=i
                    password=1234
                    username=u
                  Operations:
                    monitor: test-monitor-interval-60s
                      interval=60s
                """
            ),
        )

        self.assert_pcs_fail(
            "stonith update test action=a".split(),
            "Error: stonith option 'action' is deprecated and should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead,"
            " use --force to override\n",
        )

        self.assert_pcs_success(
            "stonith update test action=a --force".split(),
            "Warning: stonith option 'action' is deprecated and should not be"
            " used, use 'pcmk_off_action', 'pcmk_reboot_action' instead\n",
        )

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
                Resource: test (class=stonith type=fence_apc)
                  Attributes: test-instance_attributes
                    action=a
                    ip=i
                    password=1234
                    username=u
                  Operations:
                    monitor: test-monitor-interval-60s
                      interval=60s
                """
            ),
        )

        self.assert_pcs_success("stonith update test action=".split())

        self.assert_pcs_success(
            "stonith config".split(),
            outdent(
                """\
                Resource: test (class=stonith type=fence_apc)
                  Attributes: test-instance_attributes
                    ip=i
                    password=1234
                    username=u
                  Operations:
                    monitor: test-monitor-interval-60s
                      interval=60s
                """
            ),
        )

    def testStonithFenceConfirm(self):
        self.pcs_runner.cib_file = None
        self.assert_pcs_fail(
            "stonith fence blah blah".split(),
            "Error: must specify one (and only one) node to fence\n",
        )
        self.assert_pcs_fail(
            "stonith confirm blah blah".split(),
            "Error: must specify one (and only one) node to confirm fenced\n",
        )

    def testPcmkHostList(self):
        self.assert_pcs_success(
            [
                "stonith",
                "create",
                "F1",
                "fence_apc",
                "pcmk_host_list=nodea nodeb",
                "--force",
            ],
            stdout_start="Warning: stonith option 'ip' or 'ipaddr' (deprecated) has to be "
            "specified\n"
            "Warning: stonith option 'username' or 'login' (deprecated) has to "
            "be specified\n",
        )

        self.assert_pcs_success(
            "stonith config F1".split(),
            outdent(
                """\
            Resource: F1 (class=stonith type=fence_apc)
              Attributes: F1-instance_attributes
                pcmk_host_list="nodea nodeb"
              Operations:
                monitor: F1-monitor-interval-60s
                  interval=60s
            """
            ),
        )

    def testStonithDeleteRemovesLevel(self):
        shutil.copyfile(rc("cib-empty-with3nodes.xml"), self.temp_cib.name)

        deprecated_warnings = (
            "Warning: stonith option 'ip' or 'ipaddr' (deprecated) has to be "
            "specified\n"
            "Warning: stonith option 'username' or 'login' (deprecated) has to "
            "be specified\n"
        )
        self.assert_pcs_success(
            "stonith create n1-ipmi fence_apc --force".split(),
            stdout_start=deprecated_warnings,
        )
        self.assert_pcs_success(
            "stonith create n2-ipmi fence_apc --force".split(),
            stdout_start=deprecated_warnings,
        )
        self.assert_pcs_success(
            "stonith create n1-apc1 fence_apc --force".split(),
            stdout_start=deprecated_warnings,
        )
        self.assert_pcs_success(
            "stonith create n1-apc2 fence_apc --force".split(),
            stdout_start=deprecated_warnings,
        )
        self.assert_pcs_success(
            "stonith create n2-apc1 fence_apc --force".split(),
            stdout_start=deprecated_warnings,
        )
        self.assert_pcs_success(
            "stonith create n2-apc2 fence_apc --force".split(),
            stdout_start=deprecated_warnings,
        )
        self.assert_pcs_success(
            "stonith create n2-apc3 fence_apc --force".split(),
            stdout_start=deprecated_warnings,
        )
        self.assert_pcs_success_all(
            [
                "stonith level add 1 rh7-1 n1-ipmi".split(),
                "stonith level add 2 rh7-1 n1-apc1,n1-apc2,n2-apc2".split(),
                "stonith level add 1 rh7-2 n2-ipmi".split(),
                "stonith level add 2 rh7-2 n2-apc1,n2-apc2,n2-apc3".split(),
            ]
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc1\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped
                  * n2-apc1\t(stonith:fence_apc):\tStopped
                  * n2-apc2\t(stonith:fence_apc):\tStopped
                  * n2-apc3\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2,n2-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc1,n2-apc2,n2-apc3
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc1\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped
                 n2-apc1\t(stonith:fence_apc):\tStopped
                 n2-apc2\t(stonith:fence_apc):\tStopped
                 n2-apc3\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2,n2-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc1,n2-apc2,n2-apc3
                """
                ),
            )

        self.assert_pcs_success(
            "stonith delete n2-apc2".split(), "Deleting Resource - n2-apc2\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc1\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped
                  * n2-apc1\t(stonith:fence_apc):\tStopped
                  * n2-apc3\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc1,n2-apc3
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc1\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped
                 n2-apc1\t(stonith:fence_apc):\tStopped
                 n2-apc3\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc1,n2-apc3
                """
                ),
            )

        self.assert_pcs_success(
            "stonith remove n2-apc1".split(), "Deleting Resource - n2-apc1\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc1\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped
                  * n2-apc3\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc3
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc1\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped
                 n2-apc3\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                   Level 2 - n2-apc3
                """
                ),
            )

        self.assert_pcs_success(
            "stonith delete n2-apc3".split(), "Deleting Resource - n2-apc3\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc1\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc1\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc1,n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
            )

        self.assert_pcs_success(
            "resource remove n1-apc1".split(), "Deleting Resource - n1-apc1\n"
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped
                  * n1-apc2\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped
                 n1-apc2\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                   Level 2 - n1-apc2
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
            )

        self.assert_pcs_success(
            "resource delete n1-apc2".split(),
            outdent(
                """\
            Deleting Resource - n1-apc2
            """
            ),
        )

        if PCMK_2_0_3_PLUS:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                  * n1-ipmi\t(stonith:fence_apc):\tStopped
                  * n2-ipmi\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
                despace=True,
            )
        else:
            self.assert_pcs_success(
                ["stonith"],
                outdent(
                    """\
                 n1-ipmi\t(stonith:fence_apc):\tStopped
                 n2-ipmi\t(stonith:fence_apc):\tStopped

                Fencing Levels:
                 Target: rh7-1
                   Level 1 - n1-ipmi
                 Target: rh7-2
                   Level 1 - n2-ipmi
                """
                ),
            )

    def testNoStonithWarning(self):
        # pylint: disable=unused-variable
        corosync_conf = self.temp_corosync_conf.name
        o, r = pcs(
            self.temp_cib.name, ["status"], corosync_conf_opt=corosync_conf
        )
        self.assertIn("No stonith devices and stonith-enabled is not false", o)

        self.assert_pcs_success_ignore_output(
            "stonith create test_stonith fence_apc ip=i username=u pcmk_host_argument=node1 --force".split()
        )

        o, r = pcs(
            self.temp_cib.name, ["status"], corosync_conf_opt=corosync_conf
        )
        self.assertNotIn(
            "No stonith devices and stonith-enabled is not false", o
        )

        self.assert_pcs_success(
            "stonith delete test_stonith".split(),
            "Deleting Resource - test_stonith\n",
        )

        o, r = pcs(
            self.temp_cib.name, ["status"], corosync_conf_opt=corosync_conf
        )
        self.assertIn("No stonith devices and stonith-enabled is not false", o)


_fixture_stonith_level_cache = None
_fixture_stonith_level_cache_lock = Lock()


class StonithLevelTestCibFixture(CachedCibFixture):
    def _fixture_stonith_resource(self, name):
        self.assert_pcs_success_ignore_output(
            [
                "stonith",
                "create",
                name,
                "fence_apc",
                "pcmk_host_list=rh7-1 rh7-2",
                "ip=i",
                "username=u",
                "--force",
            ]
        )

    def _setup_cib(self):
        self._fixture_stonith_resource("F1")
        self._fixture_stonith_resource("F2")
        self._fixture_stonith_resource("F3")

        self.assert_pcs_success("stonith level add 1 rh7-1 F1".split())
        self.assert_pcs_success("stonith level add 2 rh7-1 F2".split())
        self.assert_pcs_success("stonith level add 2 rh7-2 F1".split())
        self.assert_pcs_success("stonith level add 1 rh7-2 F2".split())
        self.assert_pcs_success("stonith level add 4 regexp%rh7-\\d F3".split())
        self.assert_pcs_success(
            "stonith level add 3 regexp%rh7-\\d F2 F1".split()
        )
        self.assert_pcs_success(
            "stonith level add 5 attrib%fencewith=levels1 F3 F2".split()
        )
        self.assert_pcs_success(
            "stonith level add 6 attrib%fencewith=levels2 F3 F1".split()
        )


CIB_FIXTURE = StonithLevelTestCibFixture(
    "fixture_tier1_stonith_level_tests", rc("cib-empty-withnodes.xml")
)


class LevelTestsBase(TestCase, AssertPcsMixin):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_test_stonith_level")
        write_file_to_tmpfile(rc("cib-empty-withnodes.xml"), self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.config = ""
        self.config_lines = []

    def tearDown(self):
        self.temp_cib.close()

    def fixture_stonith_resource(self, name):
        self.assert_pcs_success_ignore_output(
            [
                "stonith",
                "create",
                name,
                "fence_apc",
                "pcmk_host_list=rh7-1 rh7-2",
                "ip=i",
                "username=u",
                "--force",
            ]
        )

    def fixture_full_configuration(self):
        cib, self.config, self.config_lines = self.fixture_cib_config_cache()
        write_data_to_tmpfile(cib, self.temp_cib)

    def fixture_cib_config_cache(self):
        # pylint: disable=global-statement,global-variable-not-assigned
        global _fixture_stonith_level_cache, _fixture_stonith_level_cache_lock
        with _fixture_stonith_level_cache_lock:
            if _fixture_stonith_level_cache is None:
                _fixture_stonith_level_cache = self.fixture_cib_config()
            return _fixture_stonith_level_cache

    @staticmethod
    def fixture_cib_config():
        cib_content = ""
        with open(CIB_FIXTURE.cache_path, "r") as cib_file:
            cib_content = cib_file.read()
        config = outdent(
            """\
            Target: rh7-1
              Level 1 - F1
              Level 2 - F2
            Target: rh7-2
              Level 1 - F2
              Level 2 - F1
            Target (regexp): rh7-\\d
              Level 3 - F2,F1
              Level 4 - F3
            Target: fencewith=levels1
              Level 5 - F3,F2
            Target: fencewith=levels2
              Level 6 - F3,F1
            """
        )
        config_lines = config.splitlines()
        return cib_content, config, config_lines


class LevelBadCommand(LevelTestsBase):
    def test_success(self):
        self.assert_pcs_fail(
            "stonith level nonsense".split(),
            stdout_start="\nUsage: pcs stonith level ...\n",
        )


class LevelAdd(LevelTestsBase):
    def test_not_enough_params(self):
        self.assert_pcs_fail(
            "stonith level add".split(),
            stdout_start="\nUsage: pcs stonith level add...\n",
        )

        self.assert_pcs_fail(
            "stonith level add 1".split(),
            stdout_start="\nUsage: pcs stonith level add...\n",
        )

        self.assert_pcs_fail(
            "stonith level add 1 nodeA".split(),
            stdout_start="\nUsage: pcs stonith level add...\n",
        )

    def test_add_wrong_target_type(self):
        self.assert_pcs_fail(
            "stonith level add 1 error%value F1".split(),
            "Error: 'error' is not an allowed type for 'error%value', "
            "use attrib, node, regexp\n",
        )

    def test_add_bad_level(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add NaN rh7-1 F1".split(),
            (
                "Error: 'NaN' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "-- stonith level add -10 rh7-1 F1".split(),
            (
                "Error: '-10' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "stonith level add 10abc rh7-1 F1".split(),
            (
                "Error: '10abc' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "stonith level add 0 rh7-1 F1".split(),
            (
                "Error: '0' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_fail(
            "stonith level add 000 rh7-1 F1".split(),
            (
                "Error: '000' is not a valid level value, use a positive "
                "integer\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_add_bad_device(self):
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 dev@ce".split(),
            (
                "Error: invalid device id 'dev@ce', '@' is not a valid "
                "character for a device id\n" + ERRORS_HAVE_OCCURRED
            ),
        )

    def test_add_more_errors(self):
        self.assert_pcs_fail(
            "stonith level add x rh7-X F0 dev@ce".split(),
            outdent(
                """\
                Error: 'x' is not a valid level value, use a positive integer
                Error: Node 'rh7-X' does not appear to exist in configuration, use --force to override
                Error: invalid device id 'dev@ce', '@' is not a valid character for a device id
                Error: Stonith resource(s) 'F0' do not exist, use --force to override
                """
            )
            + ERRORS_HAVE_OCCURRED,
        )

        self.assert_pcs_fail(
            "stonith level add x rh7-X F0 dev@ce --force".split(),
            outdent(
                """\
                Error: 'x' is not a valid level value, use a positive integer
                Warning: Node 'rh7-X' does not appear to exist in configuration
                Error: invalid device id 'dev@ce', '@' is not a valid character for a device id
                Warning: Stonith resource(s) 'F0' do not exist
                Error: Errors have occurred, therefore pcs is unable to continue
                """
            ),
        )

    def test_add_level_leading_zero(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success("stonith level add 0002 rh7-1 F1".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 2 - F1
                """
            ),
        )

    def test_add_node(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success("stonith level add 1 rh7-1 F1".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            ),
        )

        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1".split(),
            (
                "Error: Fencing level for 'rh7-1' at level '1' with device(s) "
                "'F1' already exists\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            ),
        )

    def test_add_node_pattern(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success("stonith level add 1 regexp%rh7-\\d F1".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target (regexp): rh7-\\d
                  Level 1 - F1
                """
            ),
        )

        self.assert_pcs_fail(
            "stonith level add 1 regexp%rh7-\\d F1".split(),
            (
                r"Error: Fencing level for 'rh7-\d' at level '1' with device(s) "
                "'F1' already exists\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target (regexp): rh7-\\d
                  Level 1 - F1
                """
            ),
        )

    def test_add_node_attribute(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_success(
            "stonith level add 1 attrib%fencewith=levels F1".split()
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: fencewith=levels
                  Level 1 - F1
                """
            ),
        )

        self.assert_pcs_fail(
            "stonith level add 1 attrib%fencewith=levels F1".split(),
            (
                "Error: Fencing level for 'fencewith=levels' at level '1' with "
                "device(s) 'F1' already exists\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: fencewith=levels
                  Level 1 - F1
                """
            ),
        )

    def test_add_more_devices(self):
        self.fixture_stonith_resource("F1")
        self.fixture_stonith_resource("F2")
        self.assert_pcs_success("stonith level add 1 rh7-1 F1 F2".split())
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                """
            ),
        )

    def test_add_more_devices_old_syntax(self):
        self.fixture_stonith_resource("F1")
        self.fixture_stonith_resource("F2")
        self.fixture_stonith_resource("F3")

        self.assert_pcs_success(
            "stonith level add 1 rh7-1 F1,F2".split(),
            "Warning: Delimiting stonith devices with ',' is deprecated and "
            "will be removed. Please use a space to delimit stonith devices.\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                """
            ),
        )

        self.assert_pcs_success(
            "stonith level add 2 rh7-1 F1,F2 F3".split(),
            "Warning: Delimiting stonith devices with ',' is deprecated and "
            "will be removed. Please use a space to delimit stonith devices.\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                  Level 2 - F1,F2,F3
                """
            ),
        )

        self.assert_pcs_success(
            "stonith level add 3 rh7-1 F1 F2,F3".split(),
            "Warning: Delimiting stonith devices with ',' is deprecated and "
            "will be removed. Please use a space to delimit stonith devices.\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2
                  Level 2 - F1,F2,F3
                  Level 3 - F1,F2,F3
                """
            ),
        )

    def test_nonexistent_node(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add 1 rh7-X F1".split(),
            (
                "Error: Node 'rh7-X' does not appear to exist in configuration"
                ", use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-X F1 --force".split(),
            "Warning: Node 'rh7-X' does not appear to exist in configuration\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-X
                  Level 1 - F1
                """
            ),
        )

    def test_nonexistent_device(self):
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1".split(),
            (
                "Error: Stonith resource(s) 'F1' do not exist"
                ", use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-1 F1 --force".split(),
            "Warning: Stonith resource(s) 'F1' do not exist\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1
                """
            ),
        )

    def test_nonexistent_devices(self):
        self.fixture_stonith_resource("F1")
        self.assert_pcs_fail(
            "stonith level add 1 rh7-1 F1 F2 F3".split(),
            (
                "Error: Stonith resource(s) 'F2', 'F3' do not exist"
                ", use --force to override\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-1 F1 F2 F3 --force".split(),
            "Warning: Stonith resource(s) 'F2', 'F3' do not exist\n",
        )
        self.assert_pcs_success(
            "stonith level".split(),
            outdent(
                """\
                Target: rh7-1
                  Level 1 - F1,F2,F3
                """
            ),
        )


@skip_unless_crm_rule()
class LevelConfig(LevelTestsBase):
    full_config = outdent(
        """\
        Cluster Name: test99
        Corosync Nodes:
         rh7-1 rh7-2
        Pacemaker Nodes:
         rh7-1 rh7-2

        Resources:

        Stonith Devices:{devices}
        Fencing Levels:{levels}

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

        Tags:
         No tags defined

        Quorum:
          Options:
        """
    )

    def test_empty(self):
        self.assert_pcs_success("stonith level config".split(), "")
        self.assert_pcs_success("stonith level".split(), "")
        self.assert_pcs_success(["stonith"], "NO stonith devices configured\n")
        self.pcs_runner.mock_settings["corosync_conf_file"] = rc(
            "corosync.conf"
        )
        self.assert_pcs_success(
            ["config"], self.full_config.format(devices="", levels="")
        )

    def test_all_possibilities(self):
        self.fixture_full_configuration()
        self.assert_pcs_success("stonith level config".split(), self.config)
        self.assert_pcs_success("stonith level".split(), self.config)
        if PCMK_2_0_3_PLUS:
            result = outdent(
                """\
                  * F1\t(stonith:fence_apc):\tStopped
                  * F2\t(stonith:fence_apc):\tStopped
                  * F3\t(stonith:fence_apc):\tStopped
                """
            )
        else:
            result = outdent(
                """\
                 F1\t(stonith:fence_apc):\tStopped
                 F2\t(stonith:fence_apc):\tStopped
                 F3\t(stonith:fence_apc):\tStopped
                """
            )
        self.assert_pcs_success(
            ["stonith"],
            result
            + "\n"
            + "\n".join(["Fencing Levels:"] + indent(self.config_lines, 1))
            + "\n",
            despace=True,
        )
        self.pcs_runner.mock_settings["corosync_conf_file"] = rc(
            "corosync.conf"
        )
        self.assert_pcs_success(
            ["config"],
            self.full_config.format(
                devices="""
  Resource: F1 (class=stonith type=fence_apc)
    Attributes: F1-instance_attributes
      ip=i
      pcmk_host_list="rh7-1 rh7-2"
      username=u
    Operations:
      monitor: F1-monitor-interval-60s
        interval=60s
  Resource: F2 (class=stonith type=fence_apc)
    Attributes: F2-instance_attributes
      ip=i
      pcmk_host_list="rh7-1 rh7-2"
      username=u
    Operations:
      monitor: F2-monitor-interval-60s
        interval=60s
  Resource: F3 (class=stonith type=fence_apc)
    Attributes: F3-instance_attributes
      ip=i
      pcmk_host_list="rh7-1 rh7-2"
      username=u
    Operations:
      monitor: F3-monitor-interval-60s
        interval=60s\
""",
                levels=("\n" + "\n".join(indent(self.config_lines, 2))),
            ),
        )


class LevelClearDeprecatedSyntax(LevelTestsBase):
    deprecated_syntax = (
        "Warning: Syntax 'pcs stonith level clear [<target> | <stonith id(s)>] "
        "is deprecated and will be removed. Please use 'pcs stonith level "
        "clear [target <target>] | [stonith <stonith id>...]'.\n"
    )

    def setUp(self):
        super().setUp()
        self.fixture_full_configuration()

    def test_clear_all(self):
        self.assert_pcs_success("stonith level clear".split())
        self.assert_pcs_success("stonith level config".split(), "")

    def test_clear_nonexistent_node_or_device(self):
        self.assert_pcs_success(
            "stonith level clear rh-X".split(), self.deprecated_syntax
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def test_clear_nonexistent_devices(self):
        self.assert_pcs_success(
            "stonith level clear F1,F5".split(), self.deprecated_syntax
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def test_pattern_is_not_device(self):
        self.assert_pcs_success(
            "stonith level clear regexp%F1".split(), self.deprecated_syntax
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def test_clear_node(self):
        self.assert_pcs_success(
            "stonith level clear rh7-1".split(), self.deprecated_syntax
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[3:]) + "\n",
        )

    def test_clear_pattern(self):
        self.assert_pcs_success(
            "stonith level clear regexp%rh7-\\d".split(), self.deprecated_syntax
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:6] + self.config_lines[9:]) + "\n",
        )

    def test_clear_attribute(self):
        self.assert_pcs_success(
            "stonith level clear attrib%fencewith=levels2".split(),
            self.deprecated_syntax,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )

    def test_clear_device(self):
        self.assert_pcs_success(
            "stonith level clear F1".split(), self.deprecated_syntax
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(
                self.config_lines[0:1]
                + self.config_lines[2:5]
                + self.config_lines[6:]
            )
            + "\n",
        )

    def test_clear_devices(self):
        self.assert_pcs_success(
            "stonith level clear F2,F1".split(), self.deprecated_syntax
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )


class LevelClear(LevelTestsBase):
    def setUp(self):
        super().setUp()
        self.fixture_full_configuration()

    def test_missing_target(self):
        self.assert_pcs_fail(
            "stonith level clear target".split(),
            "Error: Missing value after 'target'\n",
        )

    def test_missing_device(self):
        self.assert_pcs_fail(
            "stonith level clear stonith".split(),
            "Error: Missing value after 'stonith'\n",
        )

    def test_target_and_device(self):
        self.assert_pcs_fail(
            "stonith level clear target rh7-1 stonith F1".split(),
            "Error: Only one of 'target' and 'stonith' can be used\n",
        )

    def test_clear_all(self):
        self.assert_pcs_success("stonith level clear".split())
        self.assert_pcs_success("stonith level config".split(), "")

    def test_clear_nonexistent_node(self):
        self.assert_pcs_fail(
            "stonith level clear target rh-X".split(),
            "Error: Fencing level for 'rh-X' does not exist\n"
            + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def test_clear_nonexistent_devices(self):
        self.assert_pcs_fail(
            "stonith level clear stonith F1 F5".split(),
            "Error: Fencing level with device(s) 'F1', 'F5' does not exist\n"
            + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def test_clear_node(self):
        self.assert_pcs_success("stonith level clear target rh7-1".split())
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[3:]) + "\n",
        )

    def test_clear_pattern(self):
        self.assert_pcs_success(
            "stonith level clear target regexp%rh7-\\d".split()
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:6] + self.config_lines[9:]) + "\n",
        )

    def test_clear_attribute(self):
        self.assert_pcs_success(
            "stonith level clear target attrib%fencewith=levels2".split()
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )

    def test_clear_device(self):
        self.assert_pcs_success("stonith level clear stonith F1".split())
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(
                self.config_lines[0:1]
                + self.config_lines[2:5]
                + self.config_lines[6:]
            )
            + "\n",
        )

    def test_clear_devices(self):
        self.assert_pcs_success("stonith level clear stonith F2 F1".split())
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def test_clear_devices_comma(self):
        # test that old syntax doesn't work in the new command
        self.assert_pcs_fail(
            "stonith level clear stonith F2,F1".split(),
            "Error: invalid stonith id 'F2,F1', ',' is not a valid character "
            "for a stonith id\n" + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_success("stonith level config".split(), self.config)


class LevelDeleteRemoveDeprecatedSyntax(LevelTestsBase):
    command = None
    deprecation_warning = (
        "Warning: Syntax 'pcs stonith level delete | remove <level> [<target>] "
        "[<stonith id>...]' is deprecated and will be removed. Please use 'pcs "
        "stonith level delete | remove <level> [target <target>] [stonith "
        "<stonith id>...]'.\n"
    )

    def setUp(self):
        super().setUp()
        self.fixture_full_configuration()

    def _test_usage(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command],
            stdout_start=outdent(
                f"""
                Usage: pcs stonith level {self.command}...
                    level {self.command} <"""
            ),
        )

    def _test_nonexisting_level_node_device(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "1", "rh7-1", "F3"],
            self.deprecation_warning
            + outdent(
                """\
                Error: Fencing level for 'rh7-1' at level '1' with device(s) 'F3' does not exist
                Error: Fencing level at level '1' with device(s) 'F3', 'rh7-1' does not exist
                """
            )
            + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_nonexisting_level_pattern_device(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "1", r"regexp%rh7-\d", "F3"],
            (
                self.deprecation_warning
                + "Error: Fencing level for 'rh7-\\d' at level '1' with "
                "device(s) 'F3' does not exist\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

        self.assert_pcs_fail(
            ["stonith", "level", self.command, "3", r"regexp%rh7-\d", "F1,F2"],
            (
                self.deprecation_warning
                + "Warning: Delimiting stonith devices with ',' is deprecated "
                "and will be removed. Please use a space to delimit stonith "
                "devices.\n"
                "Error: Fencing level for 'rh7-\\d' at level '3' with "
                "device(s) 'F1', 'F2' does not exist\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_nonexisting_level(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "9"],
            (
                "Error: Fencing level at level '9' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_remove_level(self):
        self.assert_pcs_success(["stonith", "level", self.command, "1"])
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(
                self.config_lines[0:1]
                + self.config_lines[2:4]
                + self.config_lines[5:]
            )
            + "\n",
        )

    def _test_remove_level_node(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "1", "rh7-2"],
            self.deprecation_warning,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_pattern(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "3", r"regexp%rh7-\d"],
            self.deprecation_warning,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_remove_level_attrib(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "6", "attrib%fencewith=levels2"],
            self.deprecation_warning,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )

    def _test_remove_level_device(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "1", "F2"],
            self.deprecation_warning,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_devices(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "3", "F2", "F1"],
            self.deprecation_warning,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_remove_level_devices_old_syntax(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "3", "F2,F1"],
            self.deprecation_warning
            + "Warning: Delimiting stonith devices with ',' is deprecated "
            "and will be removed. Please use a space to delimit stonith "
            "devices.\n",
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_remove_level_node_device(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "1", "rh7-2", "F2"],
            self.deprecation_warning,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_pattern_device(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "3",
                r"regexp%rh7-\d",
                "F2",
                "F1",
            ],
            self.deprecation_warning,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_remove_level_attrib_device(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "6",
                "attrib%fencewith=levels2",
                "F3",
                "F1",
            ],
            self.deprecation_warning,
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )


class LevelDeleteDeprecatedSyntax(
    LevelDeleteRemoveDeprecatedSyntax, metaclass=ParametrizedTestMetaClass
):
    command = "delete"


class LevelRemoveDeprecatedSyntax(
    LevelDeleteRemoveDeprecatedSyntax, metaclass=ParametrizedTestMetaClass
):
    command = "remove"


class LevelDeleteRemove(LevelTestsBase):
    command = None

    def setUp(self):
        super().setUp()
        self.fixture_full_configuration()

    def _test_usage(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command],
            stdout_start=outdent(
                f"""
                Usage: pcs stonith level {self.command}...
                    level {self.command} <"""
            ),
        )

    def _test_nonexisting_level_node_device(self):
        self.assert_pcs_fail(
            [
                "stonith",
                "level",
                self.command,
                "1",
                "target",
                "rh7-1",
                "stonith",
                "F3",
            ],
            outdent(
                """\
                Error: Fencing level for 'rh7-1' at level '1' with device(s) 'F3' does not exist
                """
            )
            + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_nonexisting_level_pattern_device(self):
        self.assert_pcs_fail(
            [
                "stonith",
                "level",
                self.command,
                "1",
                "target",
                r"regexp%rh7-\d",
                "stonith",
                "F3",
            ],
            (
                "Error: Fencing level for 'rh7-\\d' at level '1' with "
                "device(s) 'F3' does not exist\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

        self.assert_pcs_fail(
            [
                "stonith",
                "level",
                self.command,
                "3",
                "target",
                r"regexp%rh7-\d",
                "stonith",
                "F1",
                "F2",
            ],
            (
                "Error: Fencing level for 'rh7-\\d' at level '3' with "
                "device(s) 'F1', 'F2' does not exist\n" + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_nonexisting_level(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "9"],
            (
                "Error: Fencing level at level '9' does not exist\n"
                + ERRORS_HAVE_OCCURRED
            ),
        )
        self.assert_pcs_success("stonith level config".split(), self.config)

    def _test_remove_level(self):
        self.assert_pcs_success(["stonith", "level", self.command, "1"])
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(
                self.config_lines[0:1]
                + self.config_lines[2:4]
                + self.config_lines[5:]
            )
            + "\n",
        )

    def _test_remove_level_node(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "1", "target", "rh7-2"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_pattern(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "3", "target", r"regexp%rh7-\d"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_remove_level_attrib(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "6",
                "target",
                "attrib%fencewith=levels2",
            ]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )

    def _test_remove_level_device(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "1", "stonith", "F2"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_devices(self):
        self.assert_pcs_success(
            ["stonith", "level", self.command, "3", "stonith", "F2", "F1"]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_comma_separated_devices_not_supported(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "3", "stonith", "F2,F1"],
            "Error: invalid stonith id 'F2,F1', ',' is not a valid character "
            "for a stonith id\n" + ERRORS_HAVE_OCCURRED,
        )

    def _test_remove_level_node_device(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "1",
                "target",
                "rh7-2",
                "stonith",
                "F2",
            ]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_device_node(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "1",
                "stonith",
                "F2",
                "target",
                "rh7-2",
            ]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:4] + self.config_lines[5:]) + "\n",
        )

    def _test_remove_level_pattern_device(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "3",
                "target",
                r"regexp%rh7-\d",
                "stonith",
                "F2",
                "F1",
            ]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:7] + self.config_lines[8:]) + "\n",
        )

    def _test_remove_level_attrib_device(self):
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                self.command,
                "6",
                "target",
                "attrib%fencewith=levels2",
                "stonith",
                "F3",
                "F1",
            ]
        )
        self.assert_pcs_success(
            "stonith level config".split(),
            "\n".join(self.config_lines[:11]) + "\n",
        )

    def _test_missing_stonith_keyword(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "1", "target", "rh7-2", "F2"],
            "Error: At most one target can be specified\n",
        )

    def _test_missing_target_stonith_values(self):
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "1", "target"],
            "Error: Missing value after 'target'\n",
        )
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "1", "stonith"],
            "Error: Missing value after 'stonith'\n",
        )
        self.assert_pcs_fail(
            ["stonith", "level", self.command, "1", "target", "stonith"],
            "Error: Missing value after 'target' and 'stonith'\n",
        )


class LevelDelete(LevelDeleteRemove, metaclass=ParametrizedTestMetaClass):
    command = "delete"


class LevelRemove(LevelDeleteRemove, metaclass=ParametrizedTestMetaClass):
    command = "remove"


class LevelVerify(LevelTestsBase):
    def test_success(self):
        self.fixture_full_configuration()
        self.assert_pcs_success("stonith level verify".split(), "")

    def test_errors(self):
        self.fixture_stonith_resource("F1")

        self.assert_pcs_success("stonith level add 1 rh7-1 F1".split())
        self.assert_pcs_success(
            "stonith level add 2 rh7-1 FX --force".split(),
            "Warning: Stonith resource(s) 'FX' do not exist\n",
        )
        self.assert_pcs_success(
            "stonith level add 1 rh7-X FX --force".split(),
            outdent(
                """\
                Warning: Node 'rh7-X' does not appear to exist in configuration
                Warning: Stonith resource(s) 'FX' do not exist
                """
            ),
        )
        self.assert_pcs_success(
            "stonith level add 2 rh7-Y FY --force".split(),
            outdent(
                """\
                Warning: Node 'rh7-Y' does not appear to exist in configuration
                Warning: Stonith resource(s) 'FY' do not exist
                """
            ),
        )
        self.assert_pcs_success(
            "stonith level add 4 regexp%rh7-\\d FX --force".split(),
            "Warning: Stonith resource(s) 'FX' do not exist\n",
        )
        self.assert_pcs_success(
            [
                "stonith",
                "level",
                "add",
                "3",
                r"regexp%rh7-\d",
                "FY",
                "FZ",
                "--force",
            ],
            "Warning: Stonith resource(s) 'FY', 'FZ' do not exist\n",
        )

        self.assert_pcs_fail(
            "stonith level verify".split(),
            (
                "Error: Stonith resource(s) 'FX', 'FY', 'FZ' do not exist\n"
                "Error: Node 'rh7-X' does not appear to exist in "
                "configuration\n"
                "Error: Node 'rh7-Y' does not appear to exist in "
                "configuration\n" + ERRORS_HAVE_OCCURRED
            ),
        )


class StonithUpdate(ResourceTest):
    def setUp(self):
        super().setUp()
        self.pcs_runner.mock_settings = get_mock_settings("crm_resource_binary")
        self.fixture_create_stonith()

    def fixture_create_stonith(self):
        self.assert_effect(
            "stonith create S fence_apc ip=i login=l ssh=0 debug=d password=1234".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-password" name="password"
                            value="1234"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
            output_start=(
                "Warning: stonith option 'login' is deprecated and should not "
                "be used, use 'username' instead\n"
                "Warning: stonith option 'debug' is deprecated and should not "
                "be used, use 'debug_file' instead\n"
            ),
        )

    def test_set_deprecated_param(self):
        self.assert_effect(
            "stonith update S debug=D".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="D"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-password" name="password"
                            value="1234"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
            output_start=(
                "Warning: stonith option 'debug' is deprecated and should not "
                "be used, use 'debug_file' instead\n"
            ),
        )

    def test_unset_deprecated_param(self):
        self.assert_effect(
            "stonith update S debug=".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-password" name="password"
                            value="1234"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
            # older versions of fence-agents may return non-empty validation
            # output
            output_regexp=re.compile(
                r"(^Warning: Validation result from agent:$.*|^$)",
                re.MULTILINE | re.UNICODE,
            ),
        )

    def test_unset_deprecated_required_param(self):
        self.assert_pcs_fail(
            "stonith update S login=".split(),
            "Error: stonith option 'username' or 'login' (deprecated) has to "
            "be specified, use --force to override\n",
        )

    def test_set_obsoleting_param(self):
        self.assert_effect(
            "stonith update S ssh=1".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-password" name="password"
                            value="1234"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="1"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unset_obsoleting_param(self):
        self.assert_effect(
            "stonith update S ssh=".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-password" name="password"
                            value="1234"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
        )

    def test_unset_obsoleting_required_param(self):
        self.assert_pcs_fail(
            "stonith update S ip=".split(),
            "Error: stonith option 'ip' or 'ipaddr' (deprecated) has to be "
            "specified, use --force to override\n",
        )

    def test_unset_deprecated_required_set_obsoleting(self):
        self.assert_effect(
            "stonith update S login= username=u".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="i"
                        />
                        <nvpair id="S-instance_attributes-password" name="password"
                            value="1234"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                        <nvpair id="S-instance_attributes-username"
                            name="username" value="u"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
            # older versions of fence-agents may return non-empty validation
            # output
            output_regexp=re.compile(
                r"(^Warning: Validation result from agent:$.*|^$)",
                re.MULTILINE | re.UNICODE,
            ),
        )

    def test_unset_obsoleting_required_set_deprecated(self):
        self.assert_effect(
            "stonith update S ip= ipaddr=I".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-password" name="password"
                            value="1234"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                        <nvpair id="S-instance_attributes-ipaddr" name="ipaddr"
                            value="I"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
            output_start=(
                "Warning: stonith option 'ipaddr' is deprecated and should not "
                "be used, use 'ip' instead\n"
            ),
        )

    def test_set_both_deprecated_and_obsoleting(self):
        self.assert_effect(
            "stonith update S ip=I1 ipaddr=I2".split(),
            """
            <resources>
                <primitive class="stonith" id="S" type="fence_apc">
                    <instance_attributes id="S-instance_attributes">
                        <nvpair id="S-instance_attributes-debug" name="debug"
                            value="d"
                        />
                        <nvpair id="S-instance_attributes-ip" name="ip"
                            value="I1"
                        />
                        <nvpair id="S-instance_attributes-login" name="login"
                            value="l"
                        />
                        <nvpair id="S-instance_attributes-password" name="password"
                            value="1234"
                        />
                        <nvpair id="S-instance_attributes-ssh" name="ssh"
                            value="0"
                        />
                        <nvpair id="S-instance_attributes-ipaddr" name="ipaddr"
                            value="I2"
                        />
                    </instance_attributes>
                    <operations>
                        <op id="S-monitor-interval-60s" interval="60s"
                            name="monitor"
                        />
                    </operations>
                </primitive>
            </resources>
            """,
            output_start=(
                "Warning: stonith option 'ipaddr' is deprecated and should not "
                "be used, use 'ip' instead\n"
            ),
        )
