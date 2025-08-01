# pylint: disable=too-many-lines
import json
from textwrap import dedent
from unittest import TestCase, mock

from pcs import cluster
from pcs.cli.common.errors import CmdLineInputError
from pcs.common.corosync_conf import (
    CorosyncConfDto,
    CorosyncNodeAddressDto,
    CorosyncNodeDto,
    CorosyncQuorumDeviceSettingsDto,
)
from pcs.common.interface import dto
from pcs.common.reports import codes as report_codes
from pcs.common.types import CorosyncTransportType

from pcs_test.tools.misc import dict_to_modifiers, get_tmp_file


def _node(name, **kwargs):
    """node dictionary fixture"""
    return dict(name=name, **kwargs)


DEFAULT_TRANSPORT_TYPE = "knet"


class ClusterSetup(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.cluster = mock.Mock(spec_set=["setup", "setup_local"])
        self.lib.cluster = self.cluster
        self.cluster_name = "cluster_name"

    @staticmethod
    def _get_default_kwargs():
        return dict(
            transport_type=None,
            transport_options={},
            link_list=[],
            compression_options={},
            crypto_options={},
            totem_options={},
            quorum_options={},
            force_flags=[],
            no_cluster_uuid=False,
        )

    def assert_setup_called_with(self, node_list, **kwargs):
        default_kwargs = self._get_default_kwargs()
        default_kwargs.update(
            dict(wait=False, start=False, enable=False, no_keys_sync=False)
        )
        default_kwargs.update(kwargs)
        self.cluster.setup.assert_called_once_with(
            self.cluster_name, node_list, **default_kwargs
        )

    def assert_setup_local_called_with(self, node_list, **kwargs):
        default_kwargs = self._get_default_kwargs()
        default_kwargs.update(kwargs)
        self.cluster.setup_local.assert_called_once_with(
            self.cluster_name, node_list, **default_kwargs
        )

    def call_cmd_without_cluster_name(self, argv, modifiers=None):
        cluster.cluster_setup(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def call_cmd(self, argv, modifiers=None):
        self.call_cmd_without_cluster_name(
            [self.cluster_name] + argv, modifiers
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
        self.assert_setup_called_with([_node(node_name, addrs=[""])])

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
        self.assert_setup_called_with([_node(node) for node in node_list])

    def test_transport_type_missing(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node", "transport"])
        self.assertEqual("Transport type not defined", cm.exception.message)

    def test_transport_type_unknown(self):
        node = "node"
        self.call_cmd(
            [
                node,
                "transport",
                "unknown",
                "a=1",
                "link",
                "b=2",
                "c=3",
            ]
        )
        self.assert_setup_called_with(
            [_node(node)],
            transport_type="unknown",
            transport_options=dict(a="1"),
            link_list=[
                dict(b="2", c="3"),
            ],
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
            totem_options=dict(c="3", a="2"),
        )

    def test_knet_links(self):
        node = "node"
        self.call_cmd(
            [
                node,
                "transport",
                "knet",
                "link",
                "c=3",
                "a=2",
                "link",
                "a=1",
            ]
        )
        self.assert_setup_called_with(
            [_node(node)],
            transport_type="knet",
            link_list=[
                dict(c="3", a="2"),
                dict(a="1"),
            ],
        )

    def test_knet_links_repeatable_correctly(self):
        node = "node"
        self.call_cmd(
            [
                node,
                "transport",
                "knet",
                "link",
                "c=3",
                "a=2",
                "compression",
                "d=1",
                "e=1",
                "link",
                "a=1",
                "compression",
                "f=1",
            ]
        )
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
        self.call_cmd(
            [
                "node0",
                "node2",
                "addr=addr0",
                "node1",
                "addr=addr1",
                "addr=addr2",
                "totem",
                "a=1",
                "b=1",
                "quorum",
                "c=1",
                "d=1",
                "transport",
                "knet",
                "a=a",
                "b=b",
                "compression",
                "a=1",
                "b=2",
                "c=3",
                "crypto",
                "d=4",
                "e=5",
                "link",
                "aa=1",
                "link",
                "ba=1",
                "bb=2",
                "link",
                "ca=1",
                "cb=2",
                "cc=3",
            ]
        )
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
        self.call_cmd(
            [
                "node0",
                "node2",
                "addr=addr0",
                "node1",
                "addr=addr1",
                "addr=addr2",
                "totem",
                "a=1",
                "b=1",
                "quorum",
                "c=1",
                "d=1",
                "transport",
                transport_type,
                "a=a",
                "b=b",
                "link",
                "aa=1",
                "link",
                "ba=1",
                "bb=2",
            ]
        )
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
        self.assert_setup_called_with([_node(node_name)], enable=True)

    def test_start(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True})
        self.assert_setup_called_with([_node(node_name)], start=True)

    def test_enable_start(self):
        node_name = "node"
        self.call_cmd([node_name], {"enable": True, "start": True})
        self.assert_setup_called_with(
            [_node(node_name)], enable=True, start=True
        )

    def test_wait(self):
        node_name = "node"
        self.call_cmd([node_name], {"wait": "10"})
        self.assert_setup_called_with([_node(node_name)], wait="10")

    def test_start_wait(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True, "wait": None})
        self.assert_setup_called_with([_node(node_name)], start=True, wait=None)

    def test_start_wait_timeout(self):
        node_name = "node"
        self.call_cmd([node_name], {"start": True, "wait": "10"})
        self.assert_setup_called_with([_node(node_name)], start=True, wait="10")

    def test_no_cluster_uuid(self):
        node_name = "node"
        self.call_cmd([node_name], {"no-cluster-uuid": True})
        self.assert_setup_called_with([_node(node_name)], no_cluster_uuid=True)

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
                "no-cluster-uuid": True,
            },
        )
        self.assert_setup_called_with(
            [_node(node_name)],
            enable=True,
            start=True,
            wait="15",
            no_keys_sync=True,
            no_cluster_uuid=True,
            force_flags=[report_codes.FORCE],
        )

    def test_live_with_local_modifiers(self):
        node_name = "node"
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([node_name], {"overwrite": True})
        self.assertEqual(
            "Cannot specify '--overwrite' when '--corosync_conf' is not "
            "specified",
            cm.exception.message,
        )

    def test_corosync_conf_not_supported_modifiers(self):
        node_name = "node"
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                [node_name],
                {
                    "enable": True,
                    "start": True,
                    "wait": "15",
                    "no-keys-sync": True,
                    "corosync_conf": "file_path",
                    "force": True,
                },
            )
        self.assertEqual(
            "Cannot specify any of '--enable', '--no-keys-sync', '--start', "
            "'--wait' when '--corosync_conf' is specified",
            cm.exception.message,
        )

    def test_corosync_conf(self):
        node_name = "node"
        corosync_conf_data = b"new corosync.conf"
        self.cluster.setup_local.return_value = corosync_conf_data
        with get_tmp_file("test_cluster_corosync.conf", "rb") as output_file:
            self.call_cmd(
                [node_name],
                {"corosync_conf": output_file.name, "overwrite": True},
            )
            self.assertEqual(output_file.read(), corosync_conf_data)

        self.assert_setup_local_called_with([_node(node_name)])

    def test_corosync_conf_full_knet(self):
        corosync_conf_data = b"new corosync.conf"
        self.cluster.setup_local.return_value = corosync_conf_data
        with get_tmp_file("test_cluster_corosync.conf", "rb") as output_file:
            self.call_cmd(
                [
                    "node0",
                    "node2",
                    "addr=addr0",
                    "node1",
                    "addr=addr1",
                    "addr=addr2",
                    "totem",
                    "a=1",
                    "b=1",
                    "quorum",
                    "c=1",
                    "d=1",
                    "transport",
                    "knet",
                    "a=a",
                    "b=b",
                    "compression",
                    "a=1",
                    "b=2",
                    "c=3",
                    "crypto",
                    "d=4",
                    "e=5",
                    "link",
                    "aa=1",
                    "link",
                    "ba=1",
                    "bb=2",
                    "link",
                    "ca=1",
                    "cb=2",
                    "cc=3",
                ],
                {"corosync_conf": output_file.name, "overwrite": True},
            )
            self.assertEqual(output_file.read(), corosync_conf_data)
        self.assert_setup_local_called_with(
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


class NodeAdd(TestCase):
    # pylint: disable=too-many-public-methods
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
        cluster.node_add(self.lib, argv, dict_to_modifiers(modifiers or {}))

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
            self.call_cmd(
                [self.hostname, "watchdog=watchdog1", "watchdog=watchdog2"]
            )
        self.assertEqual(
            (
                "duplicate option 'watchdog' with different values 'watchdog1' "
                "and 'watchdog2'"
            ),
            cm.exception.message,
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
        self.call_cmd(
            [
                self.hostname,
                "device=d1",
                "watchdog=w",
                "device=d2",
                "addr=a1",
                "addr=a3",
                "device=d0",
                "addr=a2",
                "addr=a0",
            ]
        )
        self.assert_called_with(
            [
                _node(
                    self.hostname,
                    addrs=["a1", "a3", "a2", "a0"],
                    watchdog="w",
                    devices=["d1", "d2", "d0"],
                )
            ]
        )

    def test_with_unknown_options(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                [
                    self.hostname,
                    "unknown=opt",
                    "watchdog=w",
                    "not_supported=opt",
                ]
            )
        self.assertEqual(
            "Unknown options 'not_supported', 'unknown' for node '{}'".format(
                self.hostname
            ),
            cm.exception.message,
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
                force_flags=[
                    report_codes.FORCE,
                    report_codes.SKIP_OFFLINE_NODES,
                ],
            ),
        )


class AddLink(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.cluster = mock.Mock(spec_set=["add_link"])
        self.lib.cluster = self.cluster
        self._default_kwargs = dict(
            force_flags=[],
        )

    def assert_called_with(self, link_list, options, **kwargs):
        default_kwargs = dict(self._default_kwargs)
        default_kwargs.update(kwargs)
        self.cluster.add_link.assert_called_once_with(
            link_list, options, **default_kwargs
        )

    def call_cmd(self, argv, modifiers=None):
        cluster.link_add(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([])
        self.assertIsNone(cm.exception.message)

    def test_addrs(self):
        self.call_cmd(
            ["node1=addr1", "node2=addr2"],
        )
        self.assert_called_with(
            {"node1": "addr1", "node2": "addr2"},
            {},
        )

    def test_options(self):
        self.call_cmd(
            ["options", "a=b", "c=d"],
        )
        self.assert_called_with(
            {},
            {"a": "b", "c": "d"},
        )

    def test_addrs_and_options(self):
        self.call_cmd(
            ["node1=addr1", "node2=addr2", "options", "a=b", "c=d"],
        )
        self.assert_called_with(
            {"node1": "addr1", "node2": "addr2"},
            {"a": "b", "c": "d"},
        )

    def test_missing_node_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["=addr1", "node2=addr2"],
            )
        self.assertEqual("missing key in '=addr1' option", cm.exception.message)

    def test_missing_node_addr1(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node1=addr1", "node2"],
            )
        self.assertEqual(
            "missing value of 'node2' option", cm.exception.message
        )

    def test_missing_node_addr2(self):
        self.call_cmd(
            ["node1=addr1", "node2="],
        )
        self.assert_called_with(
            {"node1": "addr1", "node2": ""},
            {},
        )

    def test_duplicate_node_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node1=a1", "node1=a2"],
            )
        self.assertEqual(
            "duplicate option 'node1' with different values 'a1' and 'a2'",
            cm.exception.message,
        )

    def test_missing_option_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node1=addr1", "node2=addr2", "options", "=b", "c=d"],
            )
        self.assertEqual("missing key in '=b' option", cm.exception.message)

    def test_missing_option_value1(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node1=addr1", "node2=addr2", "options", "a=b", "c"],
            )
        self.assertEqual("missing value of 'c' option", cm.exception.message)

    def test_missing_option_value2(self):
        self.call_cmd(
            ["node1=addr1", "node2=addr2", "options", "a=b", "c="],
        )
        self.assert_called_with(
            {"node1": "addr1", "node2": "addr2"},
            {"a": "b", "c": ""},
        )

    def test_duplicate_options(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node1=addr1", "node2=addr2", "options", "a=b", "a=d"],
            )
        self.assertEqual(
            "duplicate option 'a' with different values 'b' and 'd'",
            cm.exception.message,
        )

    def test_keyword_twice(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node1=addr1", "options", "a=b", "options", "c=d"],
            )
        self.assertEqual(
            "'options' cannot be used more than once", cm.exception.message
        )

    def test_force(self):
        self.call_cmd(["node1=addr1", "node2=addr2"], {"force": True})
        self.assert_called_with(
            {"node1": "addr1", "node2": "addr2"},
            {},
            force_flags=[report_codes.FORCE],
        )

    def test_skip_offline(self):
        self.call_cmd(["node1=addr1", "node2=addr2"], {"skip-offline": True})
        self.assert_called_with(
            {"node1": "addr1", "node2": "addr2"},
            {},
            force_flags=[report_codes.SKIP_OFFLINE_NODES],
        )

    def test_request_timeout(self):
        self.call_cmd(["node1=addr1", "node2=addr2"], {"request-timeout": "10"})
        self.assert_called_with(
            {"node1": "addr1", "node2": "addr2"}, {}, force_flags=[]
        )

    def test_corosync_conf(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["node1=addr1", "node2=addr2"],
                {"corosync_conf": "/tmp/corosync.conf"},
            )
        self.assertEqual(
            (
                "Specified option '--corosync_conf' is not supported "
                "in this command"
            ),
            cm.exception.message,
        )

    def test_all_modifiers(self):
        self.call_cmd(
            ["node1=addr1", "node2=addr2"],
            {
                "force": True,
                "request-timeout": "10",
                "skip-offline": True,
            },
        )
        self.assert_called_with(
            {"node1": "addr1", "node2": "addr2"},
            {},
            force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
        )

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["node1=addr1", "node2=addr2"], {"start": True})
        self.assertEqual(
            "Specified option '--start' is not supported in this command",
            cm.exception.message,
        )


class RemoveLink(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.cluster = mock.Mock(spec_set=["remove_links"])
        self.lib.cluster = self.cluster
        self._default_kwargs = dict(
            force_flags=[],
        )

    def assert_called_with(self, link_list, **kwargs):
        default_kwargs = dict(self._default_kwargs)
        default_kwargs.update(kwargs)
        self.cluster.remove_links.assert_called_once_with(
            link_list, **default_kwargs
        )

    def call_cmd(self, argv, modifiers=None):
        cluster.link_remove(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([])
        self.assertIsNone(cm.exception.message)

    def test_one_link(self):
        self.call_cmd(["1"])
        self.assert_called_with(["1"])

    def test_more_links(self):
        self.call_cmd(["1", "2"])
        self.assert_called_with(["1", "2"])

    def test_skip_offline(self):
        self.call_cmd(["1"], {"skip-offline": True})
        self.assert_called_with(
            ["1"], force_flags=[report_codes.SKIP_OFFLINE_NODES]
        )

    def test_request_timeout(self):
        self.call_cmd(["1"], {"request-timeout": "10"})
        self.assert_called_with(["1"], force_flags=[])

    def test_corosync_conf(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["1"], {"corosync_conf": "/tmp/corosync.conf"})
        self.assertEqual(
            (
                "Specified option '--corosync_conf' is not supported "
                "in this command"
            ),
            cm.exception.message,
        )

    def test_all_modifiers(self):
        self.call_cmd(
            ["1"],
            {
                "skip-offline": True,
                "request-timeout": "10",
            },
        )
        self.assert_called_with(
            ["1"], force_flags=[report_codes.SKIP_OFFLINE_NODES]
        )

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["1"], {"start": True})
        self.assertEqual(
            "Specified option '--start' is not supported in this command",
            cm.exception.message,
        )


class UpdateLink(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.cluster = mock.Mock(spec_set=["update_link"])
        self.lib.cluster = self.cluster
        self._default_kwargs = dict(
            force_flags=[],
        )

    def assert_called_with(self, linknumber, addrs, options, **kwargs):
        default_kwargs = dict(self._default_kwargs)
        default_kwargs.update(kwargs)
        self.cluster.update_link.assert_called_once_with(
            linknumber, addrs, options, **default_kwargs
        )

    def call_cmd(self, argv, modifiers=None):
        cluster.link_update(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def test_no_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([])
        self.assertIsNone(cm.exception.message)

    def test_one_arg(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["0"])
        self.assertIsNone(cm.exception.message)

    def test_addrs(self):
        self.call_cmd(
            ["0", "node1=addr1", "node2=addr2"],
        )
        self.assert_called_with(
            "0",
            {"node1": "addr1", "node2": "addr2"},
            {},
        )

    def test_options(self):
        self.call_cmd(
            ["0", "options", "a=b", "c=d"],
        )
        self.assert_called_with(
            "0",
            {},
            {"a": "b", "c": "d"},
        )

    def test_addrs_and_options(self):
        self.call_cmd(
            ["1", "node1=addr1", "node2=addr2", "options", "a=b", "c=d"],
        )
        self.assert_called_with(
            "1",
            {"node1": "addr1", "node2": "addr2"},
            {"a": "b", "c": "d"},
        )

    def test_missing_node_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["0", "=addr1", "node2=addr2"],
            )
        self.assertEqual("missing key in '=addr1' option", cm.exception.message)

    def test_missing_node_addr1(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["0", "node1=addr1", "node2"],
            )
        self.assertEqual(
            "missing value of 'node2' option", cm.exception.message
        )

    def test_missing_node_addr2(self):
        self.call_cmd(
            ["0", "node1=addr1", "node2="],
        )
        self.assert_called_with(
            "0",
            {"node1": "addr1", "node2": ""},
            {},
        )

    def test_duplicate_node_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["0", "node1=a1", "node1=a2"],
            )
        self.assertEqual(
            "duplicate option 'node1' with different values 'a1' and 'a2'",
            cm.exception.message,
        )

    def test_missing_option_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["0", "node1=addr1", "node2=addr2", "options", "=b", "c=d"],
            )
        self.assertEqual("missing key in '=b' option", cm.exception.message)

    def test_missing_option_value1(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["0", "node1=addr1", "node2=addr2", "options", "a=b", "c"],
            )
        self.assertEqual("missing value of 'c' option", cm.exception.message)

    def test_missing_option_value2(self):
        self.call_cmd(
            ["0", "node1=addr1", "node2=addr2", "options", "a=b", "c="],
        )
        self.assert_called_with(
            "0",
            {"node1": "addr1", "node2": "addr2"},
            {"a": "b", "c": ""},
        )

    def test_duplicate_options(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["0", "node1=addr1", "node2=addr2", "options", "a=b", "a=d"],
            )
        self.assertEqual(
            "duplicate option 'a' with different values 'b' and 'd'",
            cm.exception.message,
        )

    def test_keyword_twice(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["0", "node1=addr1", "options", "a=b", "options", "c=d"],
            )
        self.assertEqual(
            "'options' cannot be used more than once", cm.exception.message
        )

    def test_force(self):
        self.call_cmd(["1", "node1=addr1", "node2=addr2"], {"force": True})
        self.assert_called_with(
            "1",
            {"node1": "addr1", "node2": "addr2"},
            {},
            force_flags=[report_codes.FORCE],
        )

    def test_skip_offline(self):
        self.call_cmd(
            ["1", "node1=addr1", "node2=addr2"], {"skip-offline": True}
        )
        self.assert_called_with(
            "1",
            {"node1": "addr1", "node2": "addr2"},
            {},
            force_flags=[report_codes.SKIP_OFFLINE_NODES],
        )

    def test_request_timeout(self):
        self.call_cmd(
            ["2", "node1=addr1", "node2=addr2"], {"request-timeout": "10"}
        )
        self.assert_called_with(
            "2", {"node1": "addr1", "node2": "addr2"}, {}, force_flags=[]
        )

    def test_corosync_conf(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["1", "node1=addr1", "node2=addr2"],
                {"corosync_conf": "/tmp/corosync.conf"},
            )
        self.assertEqual(
            (
                "Specified option '--corosync_conf' is not supported "
                "in this command"
            ),
            cm.exception.message,
        )

    def test_all_modifiers(self):
        self.call_cmd(
            ["0", "node1=addr1", "node2=addr2"],
            {
                "force": True,
                "request-timeout": "10",
                "skip-offline": True,
            },
        )
        self.assert_called_with(
            "0",
            {"node1": "addr1", "node2": "addr2"},
            {},
            force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
        )

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["0", "node1=addr1", "node2=addr2"], {"start": True})
        self.assertEqual(
            "Specified option '--start' is not supported in this command",
            cm.exception.message,
        )


class ConfigUpdate(TestCase):
    def setUp(self):
        self.lib = mock.Mock(spec_set=["cluster"])
        self.lib.cluster = mock.Mock(
            spec_set=["config_update", "config_update_local"],
        )

    def assert_update_called_with(self, transport, compression, crypto, totem):
        self.lib.cluster.config_update.assert_called_once_with(
            transport, compression, crypto, totem
        )
        self.lib.cluster.config_update_local.assert_not_called()

    def assert_config_update_local_called_with(
        self, transport, compression, crypto, totem
    ):
        self.lib.cluster.config_update_local.assert_called_once_with(
            b"", transport, compression, crypto, totem
        )
        self.lib.cluster.config_update.assert_not_called()

    def call_cmd(self, argv, modifiers=None):
        cluster.config_update(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_no_args(self):
        self.call_cmd([])
        self.assert_update_called_with({}, {}, {}, {})

    def test_unknown_keyword(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["unknown_keyword"])
        self.assertIsNone(cm.exception.message)

    def test_unknown_keyword_with_options(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["unknown_keyword", "a=b", "c=d", "compression", "e=f", "g=h"],
            )
        self.assertIsNone(cm.exception.message)

    def test_supported_keywords_without_options(self):
        self.call_cmd(["transport", "compression", "crypto", "totem"])
        self.assert_update_called_with({}, {}, {}, {})

    def test_supported_keywords_with_options(self):
        self.call_cmd(
            [
                "transport",
                "a=b",
                "c=d",
                "compression",
                "e=f",
                "g=h",
                "crypto",
                "i=j",
                "k=l",
                "totem",
                "m=n",
                "o=p",
            ],
        )
        self.assert_update_called_with(
            {"a": "b", "c": "d"},
            {"e": "f", "g": "h"},
            {"i": "j", "k": "l"},
            {"m": "n", "o": "p"},
        )

    def test_repeated_keywords_with_options(self):
        self.call_cmd(
            [
                "crypto",
                "a=b",
                "c=d",
                "totem",
                "i=j",
                "k=l",
                "crypto",
                "e=f",
                "g=h",
                "totem",
                "m=n",
                "o=p",
            ],
        )
        self.assert_update_called_with(
            {},
            {},
            {"a": "b", "c": "d", "e": "f", "g": "h"},
            {"i": "j", "k": "l", "m": "n", "o": "p"},
        )

    def test_missing_option_name(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["transport", "=b", "c=d", "compression", "e=f", "=h"],
            )
        self.assertEqual("missing key in '=b' option", cm.exception.message)

    def test_missing_option_value(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(
                ["transport", "a=b", "c=d", "compression", "e", "g=h"],
            )
        self.assertEqual("missing value of 'e' option", cm.exception.message)

    def test_empty_option_values_allowed(self):
        self.call_cmd(
            ["transport", "a=", "c=d", "crypto", "e=f", "g="],
        )
        self.assert_update_called_with(
            {"a": "", "c": "d"}, {}, {"e": "f", "g": ""}, {}
        )

    def test_duplicate_options(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["transport", "a=b", "a=c", "crypto", "b=c", "b=d"])
        self.assertEqual(
            "duplicate option 'a' with different values 'b' and 'c'",
            cm.exception.message,
        )

    def test_duplicate_options_same_value(self):
        self.call_cmd(["transport", "a=b", "a=b", "crypto", "b=c", "b=c"])
        self.assert_update_called_with({"a": "b"}, {}, {"b": "c"}, {})

    def test_unsupported_modifier(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["transport", "a=b", "c=d"], {"skip-offline": True})
        self.assertEqual(
            (
                "Specified option '--skip-offline' is not supported in this "
                "command"
            ),
            cm.exception.message,
        )

    def test_corosync_conf_modifier(self):
        corosync_conf_data = b"new corosync.conf"
        self.lib.cluster.config_update_local.return_value = corosync_conf_data
        with get_tmp_file("test_cluster_corosync.conf", "rb") as output_file:
            self.call_cmd(
                [
                    "transport",
                    "a=b",
                    "c=d",
                    "compression",
                    "e=f",
                    "g=h",
                    "crypto",
                    "i=j",
                    "k=l",
                    "totem",
                    "m=n",
                    "o=p",
                ],
                {"corosync_conf": output_file.name},
            )
            self.assertEqual(output_file.read(), corosync_conf_data)
        self.assert_config_update_local_called_with(
            {"a": "b", "c": "d"},
            {"e": "f", "g": "h"},
            {"i": "j", "k": "l"},
            {"m": "n", "o": "p"},
        )


@mock.patch("pcs.cluster.print")
class ConfigShow(TestCase):
    @staticmethod
    def fixture_corosync_dto(with_qdevice=True):
        qdevice = None
        if with_qdevice:
            qdevice = CorosyncQuorumDeviceSettingsDto(
                model="net",
                model_options={"algorithm": "ffsplit", "host": "node-qdevice"},
                generic_options={"sync_timeout": "5000", "timeout": "5000"},
                heuristics_options={
                    "mode": "on",
                    "exec_ping": "/usr/bin/ping -c 1 127.0.0.1",
                },
            )

        return CorosyncConfDto(
            cluster_name="HACluster",
            cluster_uuid="uuid",
            transport=CorosyncTransportType.KNET,
            totem_options={"census": "3600", "join": "50", "token": "3000"},
            transport_options={"ip_version": "ipv4-6", "link_mode": "passive"},
            compression_options={
                "level": "5",
                "model": "zlib",
                "threshold": "100",
            },
            crypto_options={"cipher": "aes256", "hash": "sha256"},
            nodes=[
                CorosyncNodeDto(
                    name="node2",
                    nodeid="2",
                    addrs=[
                        CorosyncNodeAddressDto(
                            addr="10.0.0.2",
                            link="2",
                            type="IPv4",
                        ),
                        CorosyncNodeAddressDto(
                            addr="node2",
                            link="0",
                            type="FQDN",
                        ),
                    ],
                ),
                CorosyncNodeDto(
                    name="node1",
                    nodeid="1",
                    addrs=[
                        CorosyncNodeAddressDto(
                            addr="node1",
                            link="0",
                            type="FQDN",
                        ),
                        CorosyncNodeAddressDto(
                            addr="10.0.0.1",
                            link="2",
                            type="IPv4",
                        ),
                    ],
                ),
            ],
            links_options={
                "0": {
                    "linknumber": "0",
                    "link_priority": "100",
                    "ping_interval": "750",
                    "ping_timeout": "1500",
                    "transport": "udp",
                },
                "1": {
                    "linknumber": "1",
                    "link_priority": "200",
                    "ping_interval": "750",
                    "ping_timeout": "1500",
                    "transport": "udp",
                },
            },
            quorum_options={
                "last_man_standing": "1",
                "last_man_standing_window": "1000",
            },
            quorum_device=qdevice,
        )

    def setUp(self):
        self.lib_call = mock.Mock()
        self.lib = mock.Mock(spec_set=["cluster"])
        self.lib.cluster = mock.Mock(spec_set=["get_corosync_conf_struct"])
        self.lib.cluster.get_corosync_conf_struct = self.lib_call

        self.lib_call.return_value = self.fixture_corosync_dto()
        self.output_text = dedent(
            """\
            Cluster Name: HACluster
            Cluster UUID: uuid
            Transport: knet
            Nodes:
              node1:
                Link 0 address: node1
                Link 2 address: 10.0.0.1
                nodeid: 1
              node2:
                Link 0 address: node2
                Link 2 address: 10.0.0.2
                nodeid: 2
            Links:
              Link 0:
                link_priority: 100
                linknumber: 0
                ping_interval: 750
                ping_timeout: 1500
                transport: udp
              Link 1:
                link_priority: 200
                linknumber: 1
                ping_interval: 750
                ping_timeout: 1500
                transport: udp
            Transport Options:
              ip_version: ipv4-6
              link_mode: passive
            Compression Options:
              level: 5
              model: zlib
              threshold: 100
            Crypto Options:
              cipher: aes256
              hash: sha256
            Totem Options:
              census: 3600
              join: 50
              token: 3000
            Quorum Options:
              last_man_standing: 1
              last_man_standing_window: 1000
            Quorum Device: net
              Options:
                sync_timeout: 5000
                timeout: 5000
              Model Options:
                algorithm: ffsplit
                host: node-qdevice
              Heuristics:
                exec_ping: /usr/bin/ping -c 1 127.0.0.1
                mode: on"""
        )

    def call_cmd(self, argv, modifiers=None):
        cluster.config_show(self.lib, argv, dict_to_modifiers(modifiers or {}))

    def test_args_not_allowed(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["arg"])
        self.assertIsNone(cm.exception.message)
        self.lib_call.assert_not_called()
        mock_print.assert_not_called()

    def test_unsupported_option(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([], {"unsupported-option": True})
        self.assertEqual(
            (
                "Specified option '--unsupported-option' is not supported in "
                "this command"
            ),
            cm.exception.message,
        )
        self.lib_call.assert_not_called()
        mock_print.assert_not_called()

    def test_output_format_unknown(self, mock_print):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([], {"output-format": "unknown"})
        self.assertEqual(
            (
                "Unknown value 'unknown' for '--output-format' option. "
                "Supported values are: 'cmd', 'json', 'text'"
            ),
            cm.exception.message,
        )
        self.lib_call.assert_not_called()
        mock_print.assert_not_called()

    def test_output_format_default(self, mock_print):
        self.call_cmd([], {"corosync_conf": "some_file_name"})
        self.lib_call.assert_called_once_with()
        mock_print.assert_called_once_with(self.output_text)

    def test_output_format_text(self, mock_print):
        self.call_cmd([], {"output-format": "text"})
        self.lib_call.assert_called_once_with()
        mock_print.assert_called_once_with(self.output_text)

    def test_output_format_json(self, mock_print):
        self.call_cmd([], {"output-format": "json"})
        self.lib_call.assert_called_once_with()
        mock_print.assert_called_once_with(
            json.dumps(dto.to_dict(self.lib_call.return_value))
        )

    cmd_output = dedent(
        """\
        pcs cluster setup HACluster \\
          node1 addr=node1 addr=10.0.0.1 \\
          node2 addr=node2 addr=10.0.0.2 \\
          transport \\
          knet \\
              ip_version=ipv4-6 \\
              link_mode=passive \\
            link \\
              link_priority=100 \\
              linknumber=0 \\
              ping_interval=750 \\
              ping_timeout=1500 \\
              transport=udp \\
            link \\
              link_priority=200 \\
              linknumber=1 \\
              ping_interval=750 \\
              ping_timeout=1500 \\
              transport=udp \\
            compression \\
              level=5 \\
              model=zlib \\
              threshold=100 \\
            crypto \\
              cipher=aes256 \\
              hash=sha256 \\
          totem \\
            census=3600 \\
            join=50 \\
            token=3000 \\
          quorum \\
            last_man_standing=1 \\
            last_man_standing_window=1000"""
    )

    @mock.patch("pcs.cluster.warn")
    def test_output_format_cmd_with_qdevice(self, mock_warn, mock_print):
        self.call_cmd([], {"output-format": "cmd"})
        self.lib_call.assert_called_once_with()
        mock_print.assert_called_once_with(self.cmd_output)
        mock_warn.assert_called_once_with(
            "Quorum device configuration detected but not yet supported by "
            "this command."
        )

    @mock.patch("pcs.cluster.warn")
    def test_output_format_cmd(self, mock_warn, mock_print):
        self.lib_call.return_value = self.fixture_corosync_dto(
            with_qdevice=False
        )
        self.call_cmd([], {"output-format": "cmd"})
        self.lib_call.assert_called_once_with()
        mock_print.assert_called_once_with(self.cmd_output)
        mock_warn.assert_not_called()


class ClusterAuthkeyCorosync(TestCase):
    def setUp(self):
        self.lib_call = mock.Mock()
        self.lib = mock.Mock(spec_set=["cluster"])
        self.lib.cluster = mock.Mock(spec_set=["corosync_authkey_change"])
        self.lib.cluster.corosync_authkey_change = self.lib_call

    def call_cmd(self, argv, modifiers=None):
        cluster.authkey_corosync(
            self.lib, argv, dict_to_modifiers(modifiers or {})
        )

    def test_noargs(self):
        self.call_cmd([])
        self.lib_call.assert_called_once_with(
            corosync_authkey=None, force_flags=[]
        )

    @mock.patch(
        "pcs.cluster.open", new_callable=mock.mock_open, read_data=b"authkey"
    )
    def test_key_path(self, mock_open):
        self.call_cmd(["/tmp/authkey"])
        self.lib_call.assert_called_once_with(
            corosync_authkey=b"authkey", force_flags=[]
        )
        mock_open.assert_called_once_with("/tmp/authkey", "rb")

    @mock.patch(
        "pcs.cluster.open", new_callable=mock.mock_open, read_data=b"authkey"
    )
    @mock.patch("pcs.utils.err")
    def test_key_path_nonexistent_file(self, mock_err, mock_open):
        filepath = "/tmp/nonexistent"
        mock_open.side_effect = OSError(1, "an error", filepath)
        self.call_cmd([filepath])
        mock_err.assert_called_once_with(
            f"Unable to read file '{filepath}': an error: '{filepath}'"
        )
        mock_open.assert_called_once_with(filepath, "rb")

    def test_more_args(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd(["arg1", "arg2"])
        self.assertIsNone(cm.exception.message)
        self.lib_call.assert_not_called()

    def test_force(self):
        self.call_cmd([], {"force": True})
        self.lib_call.assert_called_once_with(
            corosync_authkey=None, force_flags=[report_codes.FORCE]
        )

    @mock.patch(
        "pcs.cluster.open", new_callable=mock.mock_open, read_data=b"authkey"
    )
    def test_key_path_force(self, mock_open):
        self.call_cmd(["path"], {"force": True})
        self.lib_call.assert_called_once_with(
            corosync_authkey=b"authkey", force_flags=[report_codes.FORCE]
        )
        mock_open.assert_called_once_with("path", "rb")

    @mock.patch(
        "pcs.cluster.open", new_callable=mock.mock_open, read_data=b"authkey"
    )
    def test_all_options(self, mock_open):
        self.call_cmd(
            ["path"],
            {"force": True, "skip-offline": True, "request-timeout": "10"},
        )
        self.lib_call.assert_called_once_with(
            corosync_authkey=b"authkey",
            force_flags=[report_codes.FORCE, report_codes.SKIP_OFFLINE_NODES],
        )
        mock_open.assert_called_once_with("path", "rb")

    def test_unsupported_option(self):
        with self.assertRaises(CmdLineInputError) as cm:
            self.call_cmd([], {"wait": 10})
        self.assertEqual(
            "Specified option '--wait' is not supported in this command",
            cm.exception.message,
        )
        self.lib_call.assert_not_called()
