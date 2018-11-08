import os
import shutil
import unittest
from unittest import mock
from functools import partial

from pcs.test.tools.assertions import (
    ac,
    AssertPcsMixin,
)
from pcs.test.tools.misc import (
    get_test_resource as rc,
    skip_unless_pacemaker_version,
    skip_unless_root,
)
from pcs.test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

from pcs import cluster
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.common import report_codes

# pylint: disable=invalid-name, too-many-statements, bad-whitespace, line-too-long, too-many-public-methods

empty_cib = rc("cib-empty-withnodes.xml")
temp_cib = rc("temp-cib.xml")

def _dict_to_modifiers(options):
    def _convert_val(val):
        if val is True:
            return ""
        return val
    return InputModifiers(
        {
            f"--{opt}": _convert_val(val)
            for opt, val in options.items()
            if val is not False
        }
    )


class UidGidTest(unittest.TestCase):
    def setUp(self):
        self.uid_gid_dir = rc("uid_gid.d")
        if not os.path.exists(self.uid_gid_dir):
            os.mkdir(self.uid_gid_dir)

    def tearDown(self):
        shutil.rmtree(self.uid_gid_dir)

    def testUIDGID(self):
        _pcs = partial(pcs, None, uid_gid_dir=self.uid_gid_dir)
        o,r = _pcs("cluster uidgid")
        ac(o, "No uidgids configured\n")
        assert r == 0

        o,r = _pcs("cluster uidgid add")
        assert r == 1
        assert o.startswith("\nUsage:")

        o,r = _pcs("cluster uidgid rm")
        assert r == 1
        assert o.startswith("\nUsage:")

        o,r = _pcs("cluster uidgid xx")
        assert r == 1
        assert o.startswith("\nUsage:")

        o,r = _pcs("cluster uidgid add uid=testuid gid=testgid")
        assert r == 0
        ac(o, "")

        o,r = _pcs("cluster uidgid add uid=testuid gid=testgid")
        ac(o, "Error: uidgid file with uid=testuid and gid=testgid already exists\n")
        assert r == 1

        o,r = _pcs("cluster uidgid delete uid=testuid2 gid=testgid2")
        assert r == 1
        ac(o, "Error: no uidgid files with uid=testuid2 and gid=testgid2 found\n")

        o,r = _pcs("cluster uidgid remove uid=testuid gid=testgid2")
        assert r == 1
        ac(o, "Error: no uidgid files with uid=testuid and gid=testgid2 found\n")

        o,r = _pcs("cluster uidgid rm uid=testuid2 gid=testgid")
        assert r == 1
        ac(
            o,
            "'pcs cluster uidgid rm' has been deprecated, use 'pcs cluster "
                "uidgid delete' or 'pcs cluster uidgid remove' instead\n"
            "Error: no uidgid files with uid=testuid2 and gid=testgid found\n"
        )

        o,r = _pcs("cluster uidgid")
        assert r == 0
        ac(o, "UID/GID: uid=testuid gid=testgid\n")

        o,r = _pcs("cluster uidgid delete uid=testuid gid=testgid")
        ac(o, "")
        assert r == 0

        o,r = _pcs("cluster uidgid add uid=testuid gid=testgid")
        assert r == 0
        ac(o, "")

        o,r = _pcs("cluster uidgid")
        assert r == 0
        ac(o, "UID/GID: uid=testuid gid=testgid\n")

        o,r = _pcs("cluster uidgid remove uid=testuid gid=testgid")
        ac(o, "")
        assert r == 0

        o,r = _pcs("cluster uidgid add uid=testuid gid=testgid")
        assert r == 0
        ac(o, "")

        o,r = _pcs("cluster uidgid")
        assert r == 0
        ac(o, "UID/GID: uid=testuid gid=testgid\n")

        o,r = _pcs("cluster uidgid rm uid=testuid gid=testgid")
        ac(
            o,
            "'pcs cluster uidgid rm' has been deprecated, use 'pcs cluster "
                "uidgid delete' or 'pcs cluster uidgid remove' instead\n"
        )
        assert r == 0

        o,r = _pcs("cluster uidgid")
        assert r == 0
        ac(o, "No uidgids configured\n")


class ClusterUpgradeTest(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(rc("cib-empty-1.2.xml"), temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    @skip_unless_pacemaker_version((2, 0, 0), "CIB schema upgrade")
    def testClusterUpgrade(self):
        # pylint: disable=no-self-use
        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") != -1
            assert data.find("pacemaker-2.") == -1

        o,r = pcs(temp_cib, "cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0

        with open(temp_cib) as myfile:
            data = myfile.read()
            assert data.find("pacemaker-1.2") == -1
            assert data.find("pacemaker-2.") == -1
            assert data.find("pacemaker-3.") != -1

        o,r = pcs(temp_cib, "cluster cib-upgrade")
        ac(o,"Cluster CIB has been upgraded to latest version\n")
        assert r == 0


@skip_unless_root()
class ClusterStartStop(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(cib_file=None)

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "cluster stop rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )
        self.assert_pcs_fail(
            "cluster start rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )


@skip_unless_root()
class ClusterEnableDisable(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(cib_file=None)

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "cluster enable rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )
        self.assert_pcs_fail(
            "cluster disable rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )

def _node(name, **kwargs):
    """ node dictionary fixture """
    return dict(name=name, **kwargs)

DEFAULT_TRANSPORT_TYPE = "knet"
class ClusterSetup(unittest.TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.cluster = mock.Mock(spec_set=["setup"])
        self.lib.cluster = self.cluster
        self.cluster_name = "cluster_name"

    def assert_setup_called_with(self, node_list, **kwargs):
        default_kwargs = dict(
            transport_type=DEFAULT_TRANSPORT_TYPE,
            transport_options={},
            link_list=[],
            compression_options={},
            crypto_options={},
            totem_options={},
            quorum_options={},
            wait=False,
            start=False,
            enable=False,
            no_keys_sync=False,
            force_flags=[],
        )
        default_kwargs.update(kwargs)
        self.cluster.setup.assert_called_once_with(
            self.cluster_name, node_list, **default_kwargs
        )

    def call_cmd_without_cluster_name(self, argv, modifiers=None):
        cluster.cluster_setup(
            self.lib, argv, _dict_to_modifiers(modifiers or {})
        )

    def call_cmd(self, argv, modifiers=None):
        self.call_cmd_without_cluster_name(
            [self.cluster_name] + argv,
            modifiers
        )

    def test_no_cluster_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd_without_cluster_name([])
        self.assertIsNone(cm.exception.message)

    def test_no_node(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([])
        self.assertIsNone(cm.exception.message)

    def test_invalid_node_name(self):
        node = "node="
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([node])
        self.assertEqual(
            "Invalid character '=' in node name '{}'".format(node),
            cm.exception.message,
        )

    def test_node_defined_multiple_times(self):
        node = "node"
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([node, node])
        self.assertEqual(
            "Node name '{}' defined multiple times".format(node),
            cm.exception.message,
        )

    def test_one_node_no_addrs(self):
        node_name = "node"
        self.call_cmd([node_name])
        self.assert_setup_called_with([_node(node_name)])

    def test_one_node_empty_addrs(self):
        node_name = "node"
        self.call_cmd([node_name, "addr="])
        self.assert_setup_called_with([_node(node_name, addrs=[''])])

    def test_one_node_with_single_address(self):
        node_name = "node"
        addr = "node_addr"
        self.call_cmd([node_name, "addr={}".format(addr)])
        self.assert_setup_called_with([_node(node_name, addrs=[addr])])

    def test_one_node_with_multiple_addresses(self):
        node_name = "node"
        addr_list = ["addr{}".format(i) for i in range(3)]
        self.call_cmd([node_name] + [f"addr={addr}" for addr in addr_list])
        self.assert_setup_called_with([_node(node_name, addrs=addr_list)])

    def test_node_unknown_options(self):
        node_name = "node"
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                [node_name, "unknown=option", "another=one", "addr=addr"]
            )
        self.assertEqual(
            "Unknown options 'another', 'unknown' for node 'node'",
            cm.exception.message,
        )

    def test_multiple_nodes(self):
        self.call_cmd(
            ["node1", "addr=addr1", "addr=addr2", "node2", "node3", "addr=addr"]
        )
        self.assert_setup_called_with(
            [
                _node("node1", addrs=["addr1", "addr2"]),
                _node("node2"),
                _node("node3", addrs=["addr"]),
            ]
        )

    def test_multiple_nodes_without_addrs(self):
        node_list = ["node{}".format(i) for i in range(4)]
        self.call_cmd(node_list)
        self.assert_setup_called_with(
            [_node(node) for node in node_list]
        )

    def test_transport_type_missing(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node", "transport"])
        self.assertEqual("Transport type not defined", cm.exception.message)

    def test_transport_type_unknown(self):
        node = "node"
        self.call_cmd([
            node, "transport", "unknown", "a=1", "link", "b=2", "c=3",
        ])
        self.assert_setup_called_with(
            [_node(node)],
            transport_type="unknown",
            transport_options=dict(a="1"),
            link_list=[
                dict(b="2", c="3"),
            ]
        )

    def test_transport_with_unknown_keywords(self):
        node = "node"
        self.call_cmd(["node", "transport", "udp", "crypto", "a=1"])
        self.assert_setup_called_with(
            [_node(node)],
            transport_type="udp",
            crypto_options=dict(a="1"),
        )

    def test_transport_independent_options(self):
        node = "node"
        self.call_cmd([node, "quorum", "a=1", "b=2", "totem", "c=3", "a=2"])
        self.assert_setup_called_with(
            [_node(node)],
            quorum_options=dict(a="1", b="2"),
            totem_options=dict(c="3", a="2")
        )

    def test_knet_links(self):
        node = "node"
        self.call_cmd([
            node, "transport", "knet", "link", "c=3", "a=2", "link", "a=1",
        ])
        self.assert_setup_called_with(
            [_node(node)],
            transport_type="knet",
            link_list=[
                dict(c="3", a="2"),
                dict(a="1"),
            ]
        )

    def test_knet_links_repetable_correctly(self):
        node = "node"
        self.call_cmd([
            node, "transport", "knet", "link", "c=3", "a=2", "compression",
            "d=1", "e=1", "link", "a=1", "compression", "f=1"
        ])
        self.assert_setup_called_with(
            [_node(node)],
            transport_type="knet",
            link_list=[
                dict(c="3", a="2"),
                dict(a="1"),
            ],
            compression_options=dict(d="1", e="1", f="1"),
        )

    def test_transport_not_repeatable(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node", "transport", "knet", "a=1", "transport", "knet"]
            )
        self.assertEqual(
            "'transport' cannot be used more than once", cm.exception.message
        )

    def test_totem_not_repeatable(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node", "totem", "a=1", "b=1", "totem", "c=2"])
        self.assertEqual(
            "'totem' cannot be used more than once", cm.exception.message
        )

    def test_quorum_not_repeatable(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node", "quorum", "a=1", "b=1", "quorum", "c=2"])
        self.assertEqual(
            "'quorum' cannot be used more than once", cm.exception.message
        )

    def test_full_knet(self):
        self.call_cmd([
            "node0", "node2", "addr=addr0", "node1", "addr=addr1", "addr=addr2",
            "totem", "a=1", "b=1", "quorum", "c=1", "d=1", "transport", "knet",
            "a=a", "b=b", "compression", "a=1", "b=2", "c=3", "crypto", "d=4",
            "e=5", "link", "aa=1", "link", "ba=1", "bb=2", "link", "ca=1",
            "cb=2", "cc=3"
        ])
        self.assert_setup_called_with(
            [
                _node("node0"),
                _node("node2", addrs=["addr0"]),
                _node("node1", addrs=["addr1", "addr2"]),
            ],
            totem_options=dict(a="1", b="1"),
            quorum_options=dict(c="1", d="1"),
            transport_type="knet",
            transport_options=dict(a="a", b="b"),
            compression_options=dict(a="1", b="2", c="3"),
            crypto_options=dict(d="4", e="5"),
            link_list=[
                dict(aa="1"),
                dict(ba="1", bb="2"),
                dict(ca="1", cb="2", cc="3"),
            ],
        )

    def assert_with_all_options(self, transport_type):
        self.call_cmd([
            "node0", "node2", "addr=addr0", "node1", "addr=addr1", "addr=addr2",
            "totem", "a=1", "b=1", "quorum", "c=1", "d=1", "transport",
            transport_type, "a=a", "b=b", "link", "aa=1", "link", "ba=1",
            "bb=2",
        ])
        self.assert_setup_called_with(
            [
                _node("node0"),
                _node("node2", addrs=["addr0"]),
                _node("node1", addrs=["addr1", "addr2"]),
            ],
            totem_options=dict(a="1", b="1"),
            quorum_options=dict(c="1", d="1"),
            transport_type=transport_type,
            transport_options=dict(a="a", b="b"),
            link_list=[
                dict(aa="1"),
                dict(ba="1", bb="2"),
            ],
        )

    def test_full_udp(self):
        self.assert_with_all_options("udp")

    def test_full_udpu(self):
        self.assert_with_all_options("udpu")

    def test_enable(self):
        node_name = "node"
        self.call_cmd([node_name], {"enable": True})
        self.assert_setup_called_with(
            [_node(node_name)],
            enable=True
        )

    def test_start(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True})
        self.assert_setup_called_with(
            [_node(node_name)],
            start=True
        )

    def test_enable_start(self):
        node_name = "node"
        self.call_cmd([node_name], {"enable": True, "start": True})
        self.assert_setup_called_with(
            [_node(node_name)],
            enable=True,
            start=True
        )

    def test_wait(self):
        node_name = "node"
        self.call_cmd([node_name], {"wait": "10"})
        self.assert_setup_called_with(
            [_node(node_name)],
            wait="10"
        )

    def test_start_wait(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True, "wait": None})
        self.assert_setup_called_with(
            [_node(node_name)],
            start=True,
            wait=None
        )

    def test_start_wait_timeout(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True, "wait": "10"})
        self.assert_setup_called_with(
            [_node(node_name)],
            start=True,
            wait="10"
        )

    def test_force(self):
        node_name = "node"
        self.call_cmd([node_name], {"force": True})
        self.assert_setup_called_with(
            [_node(node_name)],
            force_flags=[report_codes.FORCE],
        )

    def test_all_modifiers(self):
        node_name = "node"
        self.call_cmd(
            [node_name],
            {
                "force": True,
                "enable": True,
                "start": True,
                "wait": "15",
                "no-keys-sync": True,
            }
        )
        self.assert_setup_called_with(
            [_node(node_name)],
            enable=True,
            start=True,
            wait="15",
            no_keys_sync=True,
            force_flags=[report_codes.FORCE],
        )


class NodeAdd(unittest.TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.cluster = mock.Mock(spec_set=["add_nodes"])
        self.lib.cluster = self.cluster
        self.hostname = "hostname"
        self._default_kwargs = dict(
            wait=False,
            start=False,
            enable=False,
            no_watchdog_validation=False,
            force_flags=[],
        )

    def assert_called_with(self, node_list, **kwargs):
        default_kwargs = dict(self._default_kwargs)
        default_kwargs.update(kwargs)
        self.cluster.add_nodes.assert_called_once_with(
            nodes=node_list, **default_kwargs
        )

    def call_cmd(self, argv, modifiers=None):
        cluster.node_add(self.lib, argv, _dict_to_modifiers(modifiers or {}))

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([])
        self.assertIsNone(cm.exception.message)

    def test_minimal(self):
        self.call_cmd([self.hostname])
        self.assert_called_with([_node(self.hostname)])

    def test_with_addr(self):
        addr = "addr1"
        self.call_cmd([self.hostname, f"addr={addr}"])
        self.assert_called_with([_node(self.hostname, addrs=[addr])])

    def test_with_empty_addr(self):
        self.call_cmd([self.hostname, "addr="])
        self.assert_called_with([_node(self.hostname, addrs=[""])])

    def test_with_multiple_addrs(self):
        addr_list = [f"addr{i}" for i in range(5)]
        self.call_cmd([self.hostname] + [f"addr={addr}" for addr in addr_list])
        self.assert_called_with([_node(self.hostname, addrs=addr_list)])

    def test_with_watchdog(self):
        watchdog = "watchdog_path"
        self.call_cmd([self.hostname, f"watchdog={watchdog}"])
        self.assert_called_with([_node(self.hostname, watchdog=watchdog)])

    def test_with_empty_watchdog(self):
        self.call_cmd([self.hostname, "watchdog="])
        self.assert_called_with([_node(self.hostname, watchdog="")])

    def test_with_multiple_watchdogs(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([
                self.hostname, "watchdog=watchdog1", "watchdog=watchdog2"
            ])
        self.assertEqual(
            (
                "duplicate option 'watchdog' with different values 'watchdog1' "
                "and 'watchdog2'"
            ),
            cm.exception.message
        )

    def test_with_device(self):
        device = "device"
        self.call_cmd([self.hostname, f"device={device}"])
        self.assert_called_with([_node(self.hostname, devices=[device])])

    def test_with_empty_device(self):
        self.call_cmd([self.hostname, "device="])
        self.assert_called_with([_node(self.hostname, devices=[""])])

    def test_with_multiple_devices(self):
        device_list = [f"device{i}" for i in range(5)]
        self.call_cmd(
            [self.hostname] + [f"device={device}" for device in device_list]
        )
        self.assert_called_with([_node(self.hostname, devices=device_list)])

    def test_with_all_options(self):
        self.call_cmd([
            self.hostname, "device=d1", "watchdog=w", "device=d2", "addr=a1",
            "addr=a3", "device=d0", "addr=a2", "addr=a0",
        ])
        self.assert_called_with([
            _node(
                self.hostname,
                addrs=["a1", "a3", "a2", "a0"],
                watchdog="w",
                devices=["d1", "d2", "d0"],
            )
        ])

    def test_with_unknown_options(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([
                self.hostname, "unknown=opt", "watchdog=w", "not_supported=opt"
            ])
        self.assertEqual(
            "Unknown options 'not_supported', 'unknown' for node '{}'".format(
                self.hostname
            ),
            cm.exception.message
        )

    def assert_modifiers(self, modifiers, cmd_params=None):
        if cmd_params is None:
            cmd_params = modifiers
        self.call_cmd([self.hostname], modifiers)
        self.assert_called_with([_node(self.hostname)], **cmd_params)

    def test_enable(self):
        self.assert_modifiers(dict(enable=True))

    def test_start(self):
        self.assert_modifiers(dict(start=True))

    def test_enable_start(self):
        self.assert_modifiers(dict(enable=True, start=True))

    def test_wait(self):
        self.assert_modifiers(dict(wait="10"))

    def test_start_wait(self):
        self.assert_modifiers(dict(start=True, wait=None))

    def test_start_wait_timeout(self):
        self.assert_modifiers(dict(start=True, wait="10"))

    def test_force(self):
        self.assert_modifiers(
            dict(force=True), dict(force_flags=[report_codes.FORCE])
        )

    def test_skip_offline(self):
        self.assert_modifiers(
            {"skip-offline": True},
            dict(force_flags=[report_codes.SKIP_OFFLINE_NODES]),
        )

    def test_no_watchdog_validation(self):
        self.assert_modifiers(
            {"no-watchdog-validation": True}, dict(no_watchdog_validation=True)
        )

    def test_all_modifiers(self):
        self.assert_modifiers(
            {
                "enable": True,
                "start": True,
                "wait": "15",
                "force": True,
                "skip-offline": True,
                "no-watchdog-validation": True,
            },
            dict(
                enable=True,
                start=True,
                wait="15",
                no_watchdog_validation=True,
                force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
            )
        )
