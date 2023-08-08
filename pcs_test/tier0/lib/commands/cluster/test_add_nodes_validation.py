# pylint: disable=too-many-lines,no-member
import json
import re
from functools import partial
from unittest import TestCase

from pcs import settings
from pcs.common import reports
from pcs.lib.commands import cluster

from pcs_test.tier0.lib.commands.cluster.test_add_nodes import (
    QDEVICE_HOST,
    LocalConfig,
    corosync_conf_fixture,
    corosync_node_fixture,
    generate_nodes,
    node_fixture,
)
from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.command_env.config_http_corosync import (
    corosync_running_check_response,
)
from pcs_test.tools.custom_mock import patch_getaddrinfo

get_env_tools = partial(get_env_tools, local_extensions={"local": LocalConfig})


class GetTargets(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.expected_reports = []
        self.existing_nodes_num = 3
        self.existing_nodes, self.new_nodes = generate_nodes(
            self.existing_nodes_num, 3
        )
        patch_getaddrinfo(self, self.new_nodes)
        self.existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        (
            self.config.local.set_expected_reports_list(self.expected_reports)
            .services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.cib.load()
        )

    def _add_nodes(self, skip_offline=False):
        force_flags = []
        if skip_offline:
            force_flags.append(reports.codes.SKIP_OFFLINE_NODES)
        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node, "addrs": [node]} for node in self.new_nodes],
            force_flags=force_flags,
        )

    def _add_nodes_with_lib_error(self, skip_offline=False):
        self.env_assist.assert_raise_library_error(
            lambda: self._add_nodes(skip_offline=skip_offline)
        )

    def test_some_existing_nodes_unknown(self):
        (
            self.config.env.set_known_nodes(
                self.existing_nodes[1:] + self.new_nodes
            )
            .http.host.check_auth(node_labels=self.existing_nodes[1:])
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    host_list=self.existing_nodes[:1],
                )
            ]
        )

    def test_some_existing_nodes_unknown_skipped(self):
        (
            self.config.env.set_known_nodes(
                self.existing_nodes[1:] + self.new_nodes
            )
            .http.host.check_auth(node_labels=self.existing_nodes[1:])
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes[1:] + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .local.no_file_sync()
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes
                    + [
                        node_fixture(node, i)
                        for i, node in enumerate(
                            self.new_nodes, self.existing_nodes_num + 1
                        )
                    ]
                ),
                self.existing_nodes[1:],
                self.new_nodes,
            )
        )

        self._add_nodes(skip_offline=True)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.HOST_NOT_FOUND,
                    host_list=self.existing_nodes[:1],
                )
            ]
        )

    def test_all_existing_nodes_unknown(self):
        (
            self.config.env.set_known_nodes(self.new_nodes)
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    host_list=self.existing_nodes,
                ),
                fixture.error(reports.codes.NONE_HOST_FOUND),
            ]
        )

    def test_all_existing_nodes_unknown_skipped(self):
        (
            self.config.env.set_known_nodes(self.new_nodes)
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self._add_nodes_with_lib_error(skip_offline=True)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.warn(
                    reports.codes.HOST_NOT_FOUND, host_list=self.existing_nodes
                ),
                fixture.error(reports.codes.NONE_HOST_FOUND),
            ]
        )

    def _assert_qnetd_unknown(self, skip_offline):
        (
            self.config.env.set_known_nodes(
                self.existing_nodes + self.new_nodes
            )
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    self.existing_corosync_nodes, qdevice_net=True
                ),
                instead="corosync_conf.load_content",
            )
            .http.host.check_auth(node_labels=self.existing_nodes)
            .local.get_host_info(self.new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self._add_nodes_with_lib_error(skip_offline=skip_offline)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=[QDEVICE_HOST]
                ),
            ]
        )

    def test_qnetd_unknown(self):
        self._assert_qnetd_unknown(False)

    def test_qnetd_unknown_skipped(self):
        self._assert_qnetd_unknown(True)

    def _assert_new_nodes_unknown(self, skip_offline):
        (
            self.config.env.set_known_nodes(
                self.existing_nodes + self.new_nodes[1:]
            )
            .http.host.check_auth(node_labels=self.existing_nodes)
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(self.new_nodes[1:])
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self._add_nodes_with_lib_error(skip_offline=skip_offline)

        self.env_assist.assert_reports(
            self.expected_reports
            + [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=self.new_nodes[:1]
                )
            ]
        )

    def test_new_nodes_unknown(self):
        self._assert_new_nodes_unknown(False)

    def test_new_nodes_unknown_skipped(self):
        self._assert_new_nodes_unknown(True)


class NoneNamesMissing(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        existing_nodes_num = 3
        self.existing_nodes, self.new_nodes = generate_nodes(
            existing_nodes_num, 3
        )
        patch_getaddrinfo(self, self.new_nodes)
        existing_corosync_nodes = [
            node_fixture(node, i)
            for i, node in enumerate(self.existing_nodes, 1)
        ]
        self.corosync_conf = corosync_conf_fixture(existing_corosync_nodes)
        self.existing_nodes_with_name = self.existing_nodes

    def _add_nodes_with_lib_error(self, corosync_conf):
        (
            self.config.env.set_known_nodes(
                self.existing_nodes + self.new_nodes
            )
            .services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(corosync_conf)
            .runner.cib.load()
        )
        if self.existing_nodes_with_name:
            self.config.http.host.check_auth(
                node_labels=self.existing_nodes_with_name
            )

        self.config.services.is_installed("sbd", return_value=False)
        self.config.local.get_host_info(self.new_nodes)
        self.config.local.pcsd_ssl_cert_sync_disabled()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node, "addrs": [node]} for node in self.new_nodes],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
            ]
        )

    def test_some_node_names_missing(self):
        corosync_conf = re.sub(r"\s+name: node1\n", "\n", self.corosync_conf)
        # make sure the name was removed
        self.assertNotEqual(corosync_conf, self.corosync_conf)
        self.existing_nodes_with_name = self.existing_nodes[1:]
        self._add_nodes_with_lib_error(corosync_conf)

    def test_all_node_names_missing(self):
        corosync_conf = re.sub(r"\s+name: .*\n", "\n", self.corosync_conf)
        # make sure the names were removed
        self.assertNotEqual(corosync_conf, self.corosync_conf)
        self.existing_nodes_with_name = []
        self._add_nodes_with_lib_error(corosync_conf)


class Inputs(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_conflict_existing_nodes(self):
        existing_nodes = ["node1", "node2", "node3"]
        new_nodes = ["new1", "remote-name", "node3", "guest-name"]
        node1_addrs = ["new-addr1", "addr1-2", "guest-host", "remote-host"]
        patch_getaddrinfo(self, new_nodes + node1_addrs)

        self.config.env.set_known_nodes(existing_nodes + new_nodes)
        self.config.services.is_enabled("sbd", return_value=False)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                [
                    corosync_node_fixture(1, "node1", ["addr1-1", "addr1-2"]),
                    corosync_node_fixture(2, "node2", ["addr2-1", "addr2-2"]),
                    corosync_node_fixture(3, "node3", ["addr3-1", "addr3-2"]),
                ]
            )
        )
        self.config.runner.cib.load(
            resources="""
                    <resources>
                        <primitive id="guest" class="ocf" provider="heartbeat"
                            type="VirtualDomain"
                        >
                            <meta_attributes id="guest-meta_attributes">
                                <nvpair id="guest-remote-addr"
                                    name="remote-addr" value="guest-host"
                                />
                                <nvpair id="guest-remote-node"
                                    name="remote-node" value="guest-name"
                                />
                             </meta_attributes>
                        </primitive>
                        <primitive id="remote-name" class="ocf"
                            provider="pacemaker" type="remote"
                        >
                            <instance_attributes id="remote-instance_attrs">
                                <nvpair id="remote-server"
                                    name="server" value="remote-host"
                                />
                            </instance_attributes>
                        </primitive>
                    </resources>
                """
        )
        self.config.http.host.check_auth(node_labels=existing_nodes)
        self.config.local.get_host_info(new_nodes)
        self.config.local.pcsd_ssl_cert_sync_disabled()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    # no change, addrs defined
                    {"name": new_nodes[0], "addrs": node1_addrs},
                    # no change, addrs defined even though empty
                    {"name": new_nodes[1], "addrs": []},
                    # use a default address
                    {"name": new_nodes[2], "addrs": None},
                    # use a default address
                    {"name": new_nodes[3]},
                ],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name="node3",
                    address="node3",
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                ),
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name="guest-name",
                    address="guest-name",
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                ),
                fixture.error(
                    reports.codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=4,
                    min_count=2,
                    max_count=2,
                    node_name="new1",
                    node_index=1,
                ),
                fixture.error(
                    reports.codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=2,
                    max_count=2,
                    node_name="remote-name",
                    node_index=2,
                ),
                fixture.error(
                    reports.codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=1,
                    min_count=2,
                    max_count=2,
                    node_name="node3",
                    node_index=3,
                ),
                fixture.error(
                    reports.codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=1,
                    min_count=2,
                    max_count=2,
                    node_name="guest-name",
                    node_index=4,
                ),
                fixture.error(
                    reports.codes.NODE_NAMES_ALREADY_EXIST,
                    name_list=["guest-name", "node3", "remote-name"],
                ),
                fixture.error(
                    reports.codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["addr1-2", "guest-host", "remote-host"],
                ),
            ]
        )

    def conflict_existing_nodes_cib_load_error(self):
        existing_nodes = ["node1", "node2", "node3", "node4"]
        new_nodes = ["new1"]

        self.config.env.set_known_nodes(existing_nodes + new_nodes)
        self.config.services.is_enabled("sbd", return_value=False)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                [
                    corosync_node_fixture(1, "node1", ["addr1-1"]),
                    corosync_node_fixture(2, "node2", ["addr2-1"]),
                    corosync_node_fixture(3, "node3", ["addr3-1"]),
                    corosync_node_fixture(4, "node4", ["addr4-1"]),
                ]
            )
        )
        self.config.runner.cib.load(returncode=1, stderr="an error")
        self.config.http.host.check_auth(node_labels=existing_nodes)
        self.config.local.get_host_info(new_nodes)
        self.config.local.pcsd_ssl_cert_sync_disabled()

    def test_conflict_existing_nodes_cib_load_error(self):
        node_name = "new1"
        patch_getaddrinfo(self, [node_name])
        self.conflict_existing_nodes_cib_load_error()
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": node_name}],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node_name,
                    address=node_name,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                ),
                fixture.error(
                    reports.codes.CIB_LOAD_ERROR_GET_NODES_FOR_VALIDATION,
                    force_code=reports.codes.FORCE,
                ),
            ]
        )

    def test_conflict_existing_nodes_cib_load_error_forced(self):
        node_addrs = ["addr1-1"]
        patch_getaddrinfo(self, node_addrs)
        self.conflict_existing_nodes_cib_load_error()
        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": "new1", "addrs": node_addrs}],
                force_flags=[reports.codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.CIB_LOAD_ERROR_GET_NODES_FOR_VALIDATION
                ),
                fixture.error(
                    reports.codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=node_addrs,
                ),
            ]
        )

    def test_force_unresolvable(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        patch_getaddrinfo(self, [])
        self.config.env.set_known_nodes(existing_nodes + new_nodes)
        self.config.services.is_enabled("sbd", return_value=False)
        self.config.corosync_conf.load_content(
            corosync_conf_fixture(
                [
                    node_fixture(node, i)
                    for i, node in enumerate(existing_nodes, 1)
                ]
            )
        )
        self.config.runner.cib.load()
        self.config.http.host.check_auth(node_labels=existing_nodes)
        self.config.local.get_host_info(new_nodes)
        self.config.local.pcsd_ssl_cert_sync_disabled()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    # Use an existing address so the command stops after the
                    # validation and the test does not have to cover the whole
                    # node add process.
                    {"name": "new1", "addrs": ["node1"]},
                ],
                force_flags=[reports.codes.FORCE],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["node1"],
                ),
                fixture.error(
                    reports.codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["node1"],
                ),
            ]
        )

    def test_sbd_disabled(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1", "new2", "new3", "new4"]
        patch_getaddrinfo(self, new_nodes)
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
            .http.host.check_auth(node_labels=existing_nodes)
            .services.is_installed("sbd", return_value=False)
            .local.get_host_info(new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {
                        "name": "new1",
                        "watchdog": "/dev/wd",
                        "devices": ["/dev/sxa", "/dev/sxb"],
                    },
                    {"name": "new2", "devices": ["/dev/sxc"]},
                    {"name": "new3", "watchdog": "/dev/wd"},
                    {"name": "new4", "nonsense": "option"},
                ],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["nonsense"],
                    option_type="node",
                    allowed=["addrs", "devices", "name", "watchdog"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS,
                    node="new1",
                    options=["devices", "watchdog"],
                ),
                fixture.error(
                    reports.codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS,
                    node="new2",
                    options=["devices"],
                ),
                fixture.error(
                    reports.codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS,
                    node="new3",
                    options=["watchdog"],
                ),
            ]
        )

    def test_sbd_enabled_without_device(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1", "new2", "new3"]
        patch_getaddrinfo(self, new_nodes)
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled("sbd", return_value=True)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
            .local.read_sbd_config()
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
            .http.sbd.check_sbd(
                # This is where the values validation happens. This test only
                # deals with input params validation happening on the local
                # node, so we pretend here the remote nodes say everything is
                # valid
                communication_list=[
                    fixture.check_sbd_comm_success_fixture(
                        "new1", "/dev/wd", ["/dev/sxa", "/dev/sxb"]
                    ),
                    fixture.check_sbd_comm_success_fixture(
                        "new2", "/dev/watchdog", ["/dev/sxc"]
                    ),
                    fixture.check_sbd_comm_success_fixture(
                        "new3", "/dev/wdog", []
                    ),
                ]
            )
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {
                        "name": "new1",
                        "watchdog": "/dev/wd",
                        "devices": ["/dev/sxa", "/dev/sxb"],
                        "nonsense": "option",
                    },
                    {"name": "new2", "devices": ["/dev/sxc"]},
                    {"name": "new3", "watchdog": "/dev/wdog"},
                ],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.info(
                    reports.codes.USING_DEFAULT_WATCHDOG,
                    node="new2",
                    watchdog="/dev/watchdog",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["nonsense"],
                    option_type="node",
                    allowed=["addrs", "devices", "name", "watchdog"],
                    allowed_patterns=[],
                ),
            ]
            + [
                fixture.error(
                    reports.codes.SBD_WITH_DEVICES_NOT_USED_CANNOT_SET_DEVICE,
                    node=node,
                )
                for node in ["new1", "new2"]
            ]
            + [fixture.info(reports.codes.SBD_CHECK_STARTED)]
            + [
                fixture.info(reports.codes.SBD_CHECK_SUCCESS, node=node)
                for node in new_nodes
            ]
        )

    def test_sbd_enabled_with_device(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1", "new2", "new3"]
        patch_getaddrinfo(self, new_nodes)
        devices1 = ["/dev/sxa", "/dev/sxb", "/dev/sxc", "/dev/sxd"]
        devices2 = ["/dev/sxe", "dev/sxf"]
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled("sbd", return_value=True)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
            .local.read_sbd_config("SBD_DEVICE=/device\n")
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
            .http.sbd.check_sbd(
                # This is where the values validation happens. This test only
                # deals with input params validation happening on the local
                # node, so we pretend here the remote nodes say everything is
                # valid
                communication_list=[
                    fixture.check_sbd_comm_success_fixture(
                        "new1", "/dev/wd", devices1
                    ),
                    fixture.check_sbd_comm_success_fixture(
                        "new2", "/dev/watchdog", devices2
                    ),
                    fixture.check_sbd_comm_success_fixture(
                        "new3", "/dev/wdog", []
                    ),
                ]
            )
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {
                        "name": "new1",
                        "watchdog": "/dev/wd",
                        "devices": devices1,
                        "nonsense": "option",
                    },
                    {"name": "new2", "devices": devices2},
                    {"name": "new3", "watchdog": "/dev/wdog"},
                ],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.info(
                    reports.codes.USING_DEFAULT_WATCHDOG,
                    node="new2",
                    watchdog="/dev/watchdog",
                ),
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["nonsense"],
                    option_type="node",
                    allowed=["addrs", "devices", "name", "watchdog"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.SBD_TOO_MANY_DEVICES_FOR_NODE,
                    node="new1",
                    device_list=devices1,
                    max_devices=3,
                ),
                fixture.error(
                    reports.codes.SBD_DEVICE_PATH_NOT_ABSOLUTE,
                    node="new2",
                    device="dev/sxf",
                ),
                fixture.error(
                    reports.codes.SBD_NO_DEVICE_FOR_NODE,
                    node="new3",
                    sbd_enabled_in_cluster=True,
                ),
                fixture.info(reports.codes.SBD_CHECK_STARTED),
            ]
            + [
                fixture.info(reports.codes.SBD_CHECK_SUCCESS, node=node)
                for node in new_nodes
            ]
        )

    def test_wait_without_start(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        patch_getaddrinfo(self, new_nodes)
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(), [{"name": "new1"}], wait=10
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [fixture.error(reports.codes.WAIT_FOR_NODE_STARTUP_WITHOUT_START)]
        )

    def test_wait(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        patch_getaddrinfo(self, new_nodes)
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": "new1"}],
                start=True,
                wait="nonsense",
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.error(
                    reports.codes.INVALID_TIMEOUT_VALUE, timeout="nonsense"
                )
            ]
        )


class ClusterStatus(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def setup_config(
        self,
        existing_nodes,
        new_nodes,
        check_auth_communication_list=None,
        with_get_host_info=True,
    ):
        patch_getaddrinfo(self, new_nodes)
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled("sbd", return_value=False)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
        )
        if check_auth_communication_list:
            self.config.http.host.check_auth(
                communication_list=check_auth_communication_list
            )
        else:
            self.config.http.host.check_auth(node_labels=existing_nodes)
        if with_get_host_info:
            self.config.local.get_host_info(new_nodes)
            self.config.local.pcsd_ssl_cert_sync_disabled()

    def test_all_nodes_offline_skipped(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        self.setup_config(
            existing_nodes,
            new_nodes,
            [
                {
                    "label": "node1",
                    "was_connected": False,
                    "errno": 7,
                    "error_msg": "an error",
                },
                {
                    "label": "node2",
                    "response_code": 400,
                    "output": "not authorized",
                },
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": "new1"}],
                force_flags=[reports.codes.SKIP_OFFLINE_NODES],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.warn(
                    reports.codes.OMITTING_NODE,
                    node="node1",
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="node2",
                    command="remote/check_auth",
                    reason="not authorized",
                ),
                fixture.error(
                    reports.codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE
                ),
            ]
        )

    def test_some_nodes_offline(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        self.setup_config(
            existing_nodes,
            new_nodes,
            [
                {
                    "label": "node1",
                    "was_connected": False,
                    "errno": 7,
                    "error_msg": "an error",
                },
                {
                    "label": "node2",
                    "response_code": 200,
                    "output": '{"success":true}',
                },
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": "new1"}],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node="node1",
                    command="remote/check_auth",
                    reason="an error",
                ),
            ]
        )

    def test_some_nodes_offline_skipped(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        self.setup_config(
            existing_nodes,
            new_nodes,
            [
                {
                    "label": "node1",
                    "was_connected": False,
                    "errno": 7,
                    "error_msg": "an error",
                },
                {
                    "label": "node2",
                    "response_code": 200,
                    "output": '{"success":true}',
                },
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": "new1"}],
                # Use 'wait' without 'start' so the command stops after the
                # validation and the test does not have to cover the whole
                # node add process.
                wait=10,
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.error(
                    reports.codes.WAIT_FOR_NODE_STARTUP_WITHOUT_START
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    force_code=reports.codes.SKIP_OFFLINE_NODES,
                    node="node1",
                    command="remote/check_auth",
                    reason="an error",
                ),
            ]
        )

    def test_atb_will_be_enable_cluster_not_offline(self):
        existing_nodes = ["node1", "node2", "node3", "node4", "node5"]
        new_nodes = ["new1"]
        patch_getaddrinfo(self, new_nodes)
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled(
                "sbd", return_value=True, name="is_enabled_sbd_1"
            )
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
            .local.read_sbd_config(name_sufix="_1")
            .http.host.check_auth(node_labels=existing_nodes)
            .services.is_installed("sbd", return_value=True)
            .services.is_enabled(
                "sbd", return_value=True, name="is_enabled_sbd_2"
            )
            .local.read_sbd_config(name_sufix="_2")
            .http.corosync.check_corosync_offline(
                communication_list=[
                    {
                        "label": "node1",
                        "output": corosync_running_check_response(True),
                    },
                    {"label": "node2", "output": "an error"},
                    {
                        "label": "node3",
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                    },
                    {
                        "label": "node4",
                        "output": corosync_running_check_response(True),
                    },
                    {
                        "label": "node5",
                        "output": corosync_running_check_response(False),
                    },
                ]
            )
            .local.get_host_info(new_nodes)
            .http.sbd.check_sbd(
                # This is where the SBD values validation happens. This test
                # only deals with enabling ATB check, so we pretend here the
                # remote nodes say everything is valid
                communication_list=[
                    fixture.check_sbd_comm_success_fixture(
                        "new1", "/dev/watchdog", []
                    ),
                ]
            )
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": "new1"}],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.info(
                    reports.codes.USING_DEFAULT_WATCHDOG,
                    node="new1",
                    watchdog="/dev/watchdog",
                ),
                fixture.info(reports.codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
                fixture.error(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING,
                    node="node1",
                ),
                fixture.error(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node="node2",
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="node3",
                    command="remote/status",
                    reason="an error",
                ),
                fixture.error(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node="node3",
                ),
                fixture.error(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING,
                    node="node4",
                ),
                fixture.info(
                    reports.codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node="node5",
                ),
                fixture.error(
                    reports.codes.COROSYNC_QUORUM_ATB_WILL_BE_ENABLED_DUE_TO_SBD_CLUSTER_IS_RUNNING
                ),
                fixture.info(reports.codes.SBD_CHECK_STARTED),
                fixture.info(reports.codes.SBD_CHECK_SUCCESS, node="new1"),
            ]
        )

    @staticmethod
    def fixture_get_host_info_communication():
        return [
            dict(
                label="new1",
                output=json.dumps(
                    dict(
                        services=dict(
                            corosync=dict(
                                installed=True, enabled=True, running=True
                            ),
                            pacemaker=dict(
                                installed=True, enabled=True, running=True
                            ),
                            pcsd=dict(
                                installed=True, enabled=True, running=True
                            ),
                        ),
                        cluster_configuration_exists=False,
                    )
                ),
            ),
            dict(
                label="new2",
                output=json.dumps(
                    dict(
                        services=dict(
                            corosync=dict(
                                installed=False, enabled=False, running=False
                            ),
                            pacemaker=dict(
                                installed=False, enabled=False, running=False
                            ),
                            pcsd=dict(
                                installed=True, enabled=True, running=True
                            ),
                        ),
                        cluster_configuration_exists=False,
                    )
                ),
            ),
            dict(
                label="new3",
                output=json.dumps(
                    dict(
                        services=dict(
                            corosync=dict(
                                installed=True, enabled=True, running=False
                            ),
                            pacemaker=dict(
                                installed=True, enabled=True, running=False
                            ),
                            pcsd=dict(
                                installed=True, enabled=True, running=True
                            ),
                        ),
                        cluster_configuration_exists=True,
                    )
                ),
            ),
            dict(label="new4", output=json.dumps({})),
            dict(
                label="new5", was_connected=False, errno=7, error_msg="an error"
            ),
            dict(label="new6", response_code=400, output="an error"),
        ]

    def test_new_nodes_not_ready(self):
        existing_nodes = ["node1", "node2", "node3"]
        new_nodes = ["new1", "new2", "new3", "new4", "new5", "new6"]
        self.setup_config(existing_nodes, new_nodes, with_get_host_info=False)
        self.config.http.host.get_host_info(
            communication_list=self.fixture_get_host_info_communication()
        )
        self.config.local.pcsd_ssl_cert_sync_disabled()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": name} for name in new_nodes],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="new5",
                    command="remote/check_host",
                    reason="an error",
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="new6",
                    command="remote/check_host",
                    reason="an error",
                ),
                fixture.error(
                    reports.codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
                    host_name="new1",
                    service_list=["corosync", "pacemaker"],
                    force_code=reports.codes.FORCE,
                ),
                fixture.error(
                    reports.codes.SERVICE_NOT_INSTALLED,
                    node="new2",
                    service_list=["corosync", "pacemaker"],
                ),
                fixture.error(
                    reports.codes.HOST_ALREADY_IN_CLUSTER_CONFIG,
                    host_name="new3",
                    force_code=reports.codes.FORCE,
                ),
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node="new4",
                ),
                fixture.error(
                    reports.codes.CLUSTER_WILL_BE_DESTROYED,
                    force_code=reports.codes.FORCE,
                ),
            ]
        )

    def test_new_nodes_not_ready_forced(self):
        existing_nodes = ["node1", "node2", "node3"]
        new_nodes = ["new1", "new2", "new3", "new4", "new5", "new6"]
        self.setup_config(existing_nodes, new_nodes, with_get_host_info=False)
        self.config.http.host.get_host_info(
            communication_list=self.fixture_get_host_info_communication()
        )
        self.config.local.pcsd_ssl_cert_sync_disabled()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [{"name": name} for name in new_nodes],
                force_flags=[reports.codes.FORCE],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="new5",
                    command="remote/check_host",
                    reason="an error",
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="new6",
                    command="remote/check_host",
                    reason="an error",
                ),
                fixture.warn(
                    reports.codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
                    host_name="new1",
                    service_list=["corosync", "pacemaker"],
                ),
                fixture.error(
                    reports.codes.SERVICE_NOT_INSTALLED,
                    node="new2",
                    service_list=["corosync", "pacemaker"],
                ),
                fixture.warn(
                    reports.codes.HOST_ALREADY_IN_CLUSTER_CONFIG,
                    host_name="new3",
                ),
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node="new4",
                ),
            ]
        )

    @staticmethod
    def fixture_sbd_check_input(suffix, has_wd=True):
        return [
            ("watchdog", f"/dev/watchdog{suffix}" if has_wd else ""),
            ("device_list", json.dumps([f"/dev/sda{suffix}"])),
        ]

    @staticmethod
    def fixture_sbd_check_output(
        suffix,
        sbd_installed=True,
        wd_exists=True,
        wd_is_supported=True,
        device_exists=True,
        device_block=True,
        has_wd=True,
    ):
        result = {
            "sbd": {
                "installed": sbd_installed,
            },
            "watchdog": {
                "exist": wd_exists,
                "path": f"/dev/watchdog{suffix}",
                "is_supported": wd_is_supported,
            },
            "device_list": [
                {
                    "path": f"/dev/sda{suffix}",
                    "exist": device_exists,
                    "block_device": device_block,
                },
            ],
        }
        if has_wd:
            result["watchdog"] = {
                "exist": wd_exists,
                "path": f"/dev/watchdog{suffix}",
                "is_supported": wd_is_supported,
            }
        return json.dumps(result)

    def test_sbd_check(self):
        existing_nodes = ["node1", "node2", "node3", "node4"]
        new_nodes = [f"new{i}" for i in range(1, 10)]
        patch_getaddrinfo(self, new_nodes)
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled("sbd", return_value=True)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
            .local.read_sbd_config("SBD_DEVICE=/device\n")
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
            .http.sbd.check_sbd(
                communication_list=[
                    {
                        "label": "new1",
                        "output": self.fixture_sbd_check_output(
                            1, sbd_installed=False
                        ),
                        "param_list": self.fixture_sbd_check_input(1),
                    },
                    {
                        "label": "new2",
                        "output": self.fixture_sbd_check_output(
                            2,
                            wd_exists=False,
                            wd_is_supported=False,
                        ),
                        "param_list": self.fixture_sbd_check_input(2),
                    },
                    {
                        "label": "new3",
                        "output": self.fixture_sbd_check_output(
                            3, device_exists=False, device_block=False
                        ),
                        "param_list": self.fixture_sbd_check_input(3),
                    },
                    {
                        "label": "new4",
                        "output": self.fixture_sbd_check_output(
                            4, device_block=False
                        ),
                        "param_list": self.fixture_sbd_check_input(4),
                    },
                    {
                        "label": "new5",
                        "output": "bad json",
                        "param_list": self.fixture_sbd_check_input(5),
                    },
                    {
                        "label": "new6",
                        "response_code": 400,
                        "output": "an error",
                        "param_list": self.fixture_sbd_check_input(6),
                    },
                    {
                        "label": "new7",
                        "was_connected": False,
                        "errno": 7,
                        "error_msg": "an error",
                        "param_list": self.fixture_sbd_check_input(7),
                    },
                    {
                        "label": "new8",
                        "output": self.fixture_sbd_check_output(8),
                        "param_list": self.fixture_sbd_check_input(8),
                    },
                    {
                        "label": "new9",
                        "output": self.fixture_sbd_check_output(
                            9,
                            wd_is_supported=False,
                        ),
                        "param_list": self.fixture_sbd_check_input(9),
                    },
                ]
            )
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {
                        "name": f"new{i}",
                        "watchdog": f"/dev/watchdog{i}",
                        "devices": [f"/dev/sda{i}"],
                    }
                    for i in range(1, 10)
                ],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.info(reports.codes.SBD_CHECK_STARTED),
                fixture.error(
                    reports.codes.SERVICE_NOT_INSTALLED,
                    node="new1",
                    service_list=["sbd"],
                ),
                fixture.error(
                    reports.codes.WATCHDOG_NOT_FOUND,
                    node="new2",
                    watchdog="/dev/watchdog2",
                ),
                fixture.error(
                    reports.codes.SBD_DEVICE_DOES_NOT_EXIST,
                    node="new3",
                    device="/dev/sda3",
                ),
                fixture.error(
                    reports.codes.SBD_DEVICE_IS_NOT_BLOCK_DEVICE,
                    node="new4",
                    device="/dev/sda4",
                ),
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT,
                    node="new5",
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="new6",
                    command="remote/check_sbd",
                    reason="an error",
                ),
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="new7",
                    command="remote/check_sbd",
                    reason="an error",
                ),
                fixture.info(reports.codes.SBD_CHECK_SUCCESS, node="new8"),
                fixture.error(
                    reports.codes.SBD_WATCHDOG_NOT_SUPPORTED,
                    node="new9",
                    watchdog="/dev/watchdog9",
                ),
            ]
        )

    def test_sbd_check_forced(self):
        existing_nodes = ["node1", "node2", "node3", "node4"]
        new_nodes = [f"new{i}" for i in range(1, 4)]
        patch_getaddrinfo(self, new_nodes)
        (
            self.config.env.set_known_nodes(existing_nodes + new_nodes)
            .services.is_enabled("sbd", return_value=True)
            .corosync_conf.load_content(
                corosync_conf_fixture(
                    [
                        node_fixture(node, i)
                        for i, node in enumerate(existing_nodes, 1)
                    ]
                )
            )
            .runner.cib.load()
            .local.read_sbd_config("SBD_DEVICE=/device\n")
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
            .http.sbd.check_sbd(
                communication_list=[
                    {
                        "label": "new1",
                        "output": self.fixture_sbd_check_output(
                            1,
                            sbd_installed=False,
                            has_wd=False,
                        ),
                        "param_list": self.fixture_sbd_check_input(
                            1,
                            has_wd=False,
                        ),
                    },
                    {
                        "label": "new2",
                        "output": self.fixture_sbd_check_output(
                            2,
                            has_wd=False,
                        ),
                        "param_list": self.fixture_sbd_check_input(
                            2,
                            has_wd=False,
                        ),
                    },
                    {
                        "label": "new3",
                        "output": self.fixture_sbd_check_output(
                            3,
                            has_wd=False,
                        ),
                        "param_list": self.fixture_sbd_check_input(
                            3,
                            has_wd=False,
                        ),
                    },
                ]
            )
            .local.pcsd_ssl_cert_sync_disabled()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {
                        "name": f"new{i}",
                        "watchdog": f"/dev/watchdog{i}",
                        "devices": [f"/dev/sda{i}"],
                    }
                    for i in range(1, 4)
                ],
                no_watchdog_validation=True,
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.USING_DEFAULT_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                    address_source=(
                        reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                    ),
                )
                for node in new_nodes
            ]
            + [
                fixture.info(reports.codes.SBD_CHECK_STARTED),
                fixture.error(
                    reports.codes.SERVICE_NOT_INSTALLED,
                    node="new1",
                    service_list=["sbd"],
                ),
                fixture.info(reports.codes.SBD_CHECK_SUCCESS, node="new2"),
                fixture.info(reports.codes.SBD_CHECK_SUCCESS, node="new3"),
                fixture.warn(reports.codes.SBD_WATCHDOG_VALIDATION_INACTIVE),
            ]
        )
