from functools import partial
from unittest import TestCase

from pcs import settings
from pcs.common import report_codes
from pcs.lib.commands import cluster
from pcs.lib.commands.test.cluster.test_add_nodes import (
    corosync_conf_fixture,
    corosync_node_fixture,
    generate_nodes,
    LocalConfig,
    node_fixture,
    QDEVICE_HOST,
)
from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.custom_mock import patch_getaddrinfo

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
        (self.config
            .local.set_expected_reports_list(self.expected_reports)
            .env.set_corosync_conf_data(
                corosync_conf_fixture(self.existing_corosync_nodes)
            )
            .runner.systemctl.is_enabled("sbd", is_enabled=False)
            .runner.cib.load()
        )

    def _add_nodes(self, skip_offline=False):
        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": node, "addrs": [node]} for node in self.new_nodes],
            skip_offline_nodes=skip_offline
        )

    def _add_nodes_with_lib_error(self, skip_offline=False):
        self.env_assist.assert_raise_library_error(
            lambda: self._add_nodes(
                skip_offline=skip_offline
            )
        )

    def test_some_existing_nodes_unknown(self):
        (self.config
            .env.set_known_nodes(self.existing_nodes[1:] + self.new_nodes)
            .http.host.check_auth(node_labels=self.existing_nodes[1:])
            .runner.systemctl.list_unit_files({}) # SBD not installed
            .local.get_host_info(self.new_nodes)
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            +
            [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    host_list=self.existing_nodes[:1]
                )
            ]
        )

    def test_some_existing_nodes_unknown_skipped(self):
        (self.config
            .env.set_known_nodes(self.existing_nodes[1:] + self.new_nodes)
            .http.host.check_auth(node_labels=self.existing_nodes[1:])
            .runner.systemctl.list_unit_files({}) # SBD not installed
            .local.get_host_info(self.new_nodes)
            .http.host.update_known_hosts(
                node_labels=self.new_nodes,
                to_add_hosts=self.existing_nodes[1:] + self.new_nodes,
            )
            .local.disable_sbd(self.new_nodes)
            .fs.isdir(settings.booth_config_dir, return_value=False)
            .local.no_file_sync()
            .local.pcsd_ssl_cert_sync(self.new_nodes)
            .local.distribute_and_reload_corosync_conf(
                corosync_conf_fixture(
                    self.existing_corosync_nodes + [
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
            +
            [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND,
                    host_list=self.existing_nodes[:1]
                )
            ]
        )

    def test_all_existing_nodes_unknown(self):
        (self.config
            .env.set_known_nodes(self.new_nodes)
            .runner.systemctl.list_unit_files({}) # SBD not installed
            .local.get_host_info(self.new_nodes)
        )

        self._add_nodes_with_lib_error()

        self.env_assist.assert_reports(
            self.expected_reports
            +
            [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                    host_list=self.existing_nodes
                ),
                fixture.error(
                    report_codes.NONE_HOST_FOUND
                )
            ]
        )

    def test_all_existing_nodes_unknown_skipped(self):
        (self.config
            .env.set_known_nodes(self.new_nodes)
            .runner.systemctl.list_unit_files({}) # SBD not installed
            .local.get_host_info(self.new_nodes)
        )

        self._add_nodes_with_lib_error(skip_offline=True)

        self.env_assist.assert_reports(
            self.expected_reports
            +
            [
                fixture.warn(
                    report_codes.HOST_NOT_FOUND,
                    host_list=self.existing_nodes
                ),
                fixture.error(
                    report_codes.NONE_HOST_FOUND
                )
            ]
        )

    def _assert_qnetd_unknown(self, skip_offline):
        (self.config
            .env.set_corosync_conf_data(corosync_conf_fixture(
                self.existing_corosync_nodes, qdevice_net=True
            ))
            .env.set_known_nodes(self.existing_nodes + self.new_nodes)
            .http.host.check_auth(node_labels=self.existing_nodes)
            .local.get_host_info(self.new_nodes)
        )

        self._add_nodes_with_lib_error(skip_offline=skip_offline)

        self.env_assist.assert_reports(
            self.expected_reports
            +
            [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    host_list=[QDEVICE_HOST]
                ),
            ]
        )

    def test_qnetd_unknown(self):
        self._assert_qnetd_unknown(False)

    def test_qnetd_unknown_skipped(self):
        self._assert_qnetd_unknown(True)

    def _assert_new_nodes_unknown(self, skip_offline):
        (self.config
            .env.set_known_nodes(self.existing_nodes + self.new_nodes[1:])
            .http.host.check_auth(node_labels=self.existing_nodes)
            .runner.systemctl.list_unit_files({}) # SBD not installed
            .local.get_host_info(self.new_nodes[1:])
        )

        self._add_nodes_with_lib_error(skip_offline=skip_offline)

        self.env_assist.assert_reports(
            self.expected_reports
            +
            [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    host_list=self.new_nodes[:1]
                )
            ]
        )

    def test_new_nodes_unknown(self):
        self._assert_new_nodes_unknown(False)

    def test_new_nodes_unknown_skipped(self):
        self._assert_new_nodes_unknown(True)


class Inputs(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_addresses(self):
        existing_nodes = ["node1", "node2", "node3"]
        new_nodes = ["new1", "new2", "node3", "new4"]
        (self.config
            .env.set_known_nodes(existing_nodes + new_nodes)
            .env.set_corosync_conf_data(
                corosync_conf_fixture([
                    corosync_node_fixture(1, "node1", ["addr1-1", "addr1-2"]),
                    corosync_node_fixture(2, "node2", ["addr2-1", "addr2-2"]),
                    corosync_node_fixture(3, "node3", ["addr3-1", "addr3-2"]),
                ])
            )
            .runner.systemctl.is_enabled("sbd", is_enabled=False)
            .runner.cib.load()
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    # no change, addrs defined
                    {"name": "new1", "addrs": ["new-addr1", "addr1-2"]},
                    # no change, addrs defined even though empty
                    {"name": "new2", "addrs": []},
                    # use a default address
                    {"name": "node3", "addrs": None},
                    # use a default address
                    {"name": "new4"},
                ],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name="node3",
                    address="node3"
                ),
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name="new4",
                    address="new4"
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=2,
                    max_count=2,
                    node_name="new2",
                    node_index=2,
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=1,
                    min_count=2,
                    max_count=2,
                    node_name="node3",
                    node_index=3,
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=1,
                    min_count=2,
                    max_count=2,
                    node_name="new4",
                    node_index=4,
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addr1-2", "new-addr1", "new4", "node3"]
                ),
                fixture.error(
                    report_codes.NODE_NAMES_ALREADY_EXIST,
                    name_list=["node3"]
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["addr1-2"]
                ),
            ]
        )

    def test_force_unresolvable(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        (self.config
            .env.set_known_nodes(existing_nodes + new_nodes)
            .env.set_corosync_conf_data(
                corosync_conf_fixture([
                    node_fixture(node, i)
                    for i, node in enumerate(existing_nodes, 1)
                ])
            )
            .runner.systemctl.is_enabled("sbd", is_enabled=False)
            .runner.cib.load()
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    # Use an existing address so the command stops after the
                    # validation and the test does not have to cover the whole
                    # node add process.
                    {"name": "new1", "addrs": ["node1"]},
                ],
                force_unresolvable=True
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["node1"]
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["node1"]
                ),
            ]
        )

    def test_sbd_disabled(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1", "new2", "new3", "new4"]
        patch_getaddrinfo(self, new_nodes)
        (self.config
            .env.set_known_nodes(existing_nodes + new_nodes)
            .env.set_corosync_conf_data(
                corosync_conf_fixture([
                    node_fixture(node, i)
                    for i, node in enumerate(existing_nodes, 1)
                ])
            )
            .runner.systemctl.is_enabled("sbd", is_enabled=False)
            .runner.cib.load()
            .http.host.check_auth(node_labels=existing_nodes)
            .runner.systemctl.list_unit_files({}) # SBD not installed
            .local.get_host_info(new_nodes)
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {
                        "name": "new1",
                        "watchdog": "/dev/wd",
                        "devices": ["/dev/sxa", "/dev/sxb"]
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
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                ) for node in new_nodes
            ]
            +
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense"],
                    option_type="node",
                    allowed=["addrs", "devices", "name", "watchdog"],
                    allowed_patterns=[]
                ),
                fixture.error(
                    report_codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS,
                    node="new1",
                    options=["devices", "watchdog"]
                ),
                fixture.error(
                    report_codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS,
                    node="new2",
                    options=["devices"]
                ),
                fixture.error(
                    report_codes.SBD_NOT_USED_CANNOT_SET_SBD_OPTIONS,
                    node="new3",
                    options=["watchdog"]
                ),
            ]
        )

    def test_sbd_enabled_without_device(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1", "new2", "new3"]
        patch_getaddrinfo(self, new_nodes)
        (self.config
            .env.set_known_nodes(existing_nodes + new_nodes)
            .env.set_corosync_conf_data(
                corosync_conf_fixture([
                    node_fixture(node, i)
                    for i, node in enumerate(existing_nodes, 1)
                ])
            )
            .runner.systemctl.is_enabled("sbd", is_enabled=True)
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
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {
                        "name": "new1",
                        "watchdog": "/dev/wd",
                        "devices": ["/dev/sxa", "/dev/sxb"],
                        "nonsense": "option"
                    },
                    {"name": "new2", "devices": ["/dev/sxc"]},
                    {"name": "new3", "watchdog": "/dev/wdog"},
                ],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                ) for node in new_nodes
            ]
            +
            [
                fixture.info(
                    report_codes.USING_DEFAULT_WATCHDOG,
                    node="new2",
                    watchdog="/dev/watchdog",
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense"],
                    option_type="node",
                    allowed=["addrs", "devices", "name", "watchdog"],
                    allowed_patterns=[]
                ),
            ]
            +
            [
                fixture.error(
                    report_codes.SBD_WITH_DEVICES_NOT_USED_CANNOT_SET_DEVICE,
                    node=node
                ) for node in ["new1", "new2"]
            ]
            +
            [
                fixture.info(report_codes.SBD_CHECK_STARTED)
            ]
            +
            [
                fixture.info(report_codes.SBD_CHECK_SUCCESS, node=node)
                for node in new_nodes
            ]
        )

    def test_sbd_enabled_with_device(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1", "new2", "new3"]
        patch_getaddrinfo(self, new_nodes)
        devices1 = ["/dev/sxa", "/dev/sxb", "/dev/sxc", "/dev/sxd"]
        devices2 = ["/dev/sxe", "dev/sxf"]
        (self.config
            .env.set_known_nodes(existing_nodes + new_nodes)
            .env.set_corosync_conf_data(
                corosync_conf_fixture([
                    node_fixture(node, i)
                    for i, node in enumerate(existing_nodes, 1)
                ])
            )
            .runner.systemctl.is_enabled("sbd", is_enabled=True)
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
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {
                        "name": "new1",
                        "watchdog": "/dev/wd",
                        "devices": devices1,
                        "nonsense": "option"
                    },
                    {"name": "new2", "devices": devices2},
                    {"name": "new3", "watchdog": "/dev/wdog"},
                ],
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                ) for node in new_nodes
            ]
            +
            [
                fixture.info(
                    report_codes.USING_DEFAULT_WATCHDOG,
                    node="new2",
                    watchdog="/dev/watchdog",
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense"],
                    option_type="node",
                    allowed=["addrs", "devices", "name", "watchdog"],
                    allowed_patterns=[]
                ),
                fixture.error(
                    report_codes.SBD_TOO_MANY_DEVICES_FOR_NODE,
                    node="new1",
                    device_list=devices1,
                    max_devices=3
                ),
                fixture.error(
                    report_codes.SBD_DEVICE_PATH_NOT_ABSOLUTE,
                    node="new2",
                    device="dev/sxf"
                ),
                fixture.error(
                    report_codes.SBD_NO_DEVICE_FOR_NODE,
                    node="new3",
                    sbd_enabled_in_cluster=True
                ),
                fixture.info(report_codes.SBD_CHECK_STARTED),
            ]
            +
            [
                fixture.info(report_codes.SBD_CHECK_SUCCESS, node=node)
                for node in new_nodes
            ]
        )

    def test_wait_without_start(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        patch_getaddrinfo(self, new_nodes)
        (self.config
            .env.set_known_nodes(existing_nodes + new_nodes)
            .env.set_corosync_conf_data(
                corosync_conf_fixture([
                    node_fixture(node, i)
                    for i, node in enumerate(existing_nodes, 1)
                ])
            )
            .runner.systemctl.is_enabled("sbd", is_enabled=False)
            .runner.cib.load()
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {"name": "new1"},
                ],
                wait=10
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                ) for node in new_nodes
            ]
            +
            [
                fixture.error(report_codes.WAIT_FOR_NODE_STARTUP_WITHOUT_START)
            ]
        )

    def test_wait(self):
        existing_nodes = ["node1", "node2"]
        new_nodes = ["new1"]
        patch_getaddrinfo(self, new_nodes)
        (self.config
            .env.set_known_nodes(existing_nodes + new_nodes)
            .env.set_corosync_conf_data(
                corosync_conf_fixture([
                    node_fixture(node, i)
                    for i, node in enumerate(existing_nodes, 1)
                ])
            )
            .runner.systemctl.is_enabled("sbd", is_enabled=False)
            .runner.cib.load()
            .http.host.check_auth(node_labels=existing_nodes)
            .local.get_host_info(new_nodes)
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_nodes(
                self.env_assist.get_env(),
                [
                    {"name": "new1"},
                ],
                start=True,
                wait="nonsense"
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node,
                ) for node in new_nodes
            ]
            +
            [
                fixture.error(
                    report_codes.INVALID_TIMEOUT_VALUE,
                    timeout="nonsense"
                )
            ]
        )


class ClusterStatus(TestCase):
    pass
