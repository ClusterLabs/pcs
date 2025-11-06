from textwrap import dedent
from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import patch_getaddrinfo


class AddLink(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2"])
        self.node_addr_map = {
            "node1": "node1-addr1",
            "node2": "node2-addr1",
        }
        patch_getaddrinfo(self, self.node_addr_map.values())
        self.link_options = {
            "linknumber": "1",
            "transport": "udp",
        }
        self.before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 2
                    mcastport: 1234
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring2_addr: node1-addr2
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring2_addr: node2-addr2
                    name: node2
                    nodeid: 2
                }
            }
            """
        )
        self.after = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 2
                    mcastport: 1234
                }

                interface {
                    knet_transport: udp
                    linknumber: 1
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring2_addr: node1-addr2
                    name: node1
                    nodeid: 1
                    ring1_addr: node1-addr1
                }

                node {
                    ring0_addr: node2-addr0
                    ring2_addr: node2-addr2
                    name: node2
                    nodeid: 2
                    ring1_addr: node2-addr1
                }
            }
            """
        )

    def test_success(self):
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load()
        self.config.env.push_corosync_conf(corosync_conf_text=self.after)

        cluster.add_link(
            self.env_assist.get_env(),
            self.node_addr_map,
            self.link_options,
        )
        # Reports from pushing corosync.conf are produced in env. That code is
        # hidden in self.config.env.push_corosync_conf.
        self.env_assist.assert_reports([])

    def test_success_deprecated_sctp(self):
        after = self.after.replace(
            "knet_transport: udp", "knet_transport: sctp"
        )
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load()
        self.config.env.push_corosync_conf(corosync_conf_text=after)

        cluster.add_link(
            self.env_assist.get_env(),
            self.node_addr_map,
            {"transport": "sctp"},
        )
        # Reports from pushing corosync.conf are produced in env. That code is
        # hidden in self.config.env.push_corosync_conf.
        self.env_assist.assert_reports(
            [
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="transport",
                    deprecated_value="sctp",
                    replaced_by=None,
                )
            ]
        )

    def test_not_live(self):
        self.config.env.set_corosync_conf_data(self.before)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_link(
                self.env_assist.get_env(),
                self.node_addr_map,
                self.link_options,
            ),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=["COROSYNC_CONF"],
                ),
            ],
            expected_in_processor=False,
        )

    def test_validation(self):
        patch_getaddrinfo(self, ["node2-addr0"])
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_link(
                self.env_assist.get_env(),
                {
                    "node2": "node2-addr0",
                    "node3": "node2-addr0",
                },
                {
                    "wrong": "option",
                    "linknumber": "2",
                },
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=1,
                    node_name="node1",
                    node_index=None,
                ),
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node="node3",
                    searched_types=[],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["node2-addr0"],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=["node2-addr0"],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["wrong"],
                    option_type="link",
                    allowed=[
                        "link_priority",
                        "linknumber",
                        "mcastport",
                        "ping_interval",
                        "ping_precision",
                        "ping_timeout",
                        "pong_count",
                        "transport",
                    ],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.COROSYNC_LINK_ALREADY_EXISTS_CANNOT_ADD,
                    link_number="2",
                ),
            ]
        )

    def test_missing_input_data(self):
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_link(self.env_assist.get_env(), {}, {}), []
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=1,
                    node_name=node_name,
                    node_index=None,
                )
                for node_name in self.node_addr_map
            ]
        )

    def test_missing_node_names(self):
        before = dedent(
            """\
            totem {
                transport: knet
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring2_addr: node1-addr2
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring2_addr: node2-addr2
                    nodeid: 2
                }
            }
            """
        )
        self.config.corosync_conf.load_content(before)
        self.config.runner.cib.load()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_link(
                self.env_assist.get_env(),
                self.node_addr_map,
                self.link_options,
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COROSYNC_CONFIG_MISSING_NAMES_OF_NODES,
                    fatal=True,
                ),
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node="node2",
                    searched_types=[],
                ),
            ]
        )

    def test_cib_guest_node(self):
        resources = f"""
            <resources>
                <primitive id="R">
                    <meta_attributes>
                        <nvpair name="remote-node" value="node-remote" />
                        <nvpair name="remote-addr"
                            value="{self.node_addr_map["node1"]}"
                        />
                    </meta_attributes>
                </primitive>
            </resources>
        """

        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load(resources=resources)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_link(
                self.env_assist.get_env(),
                self.node_addr_map,
                self.link_options,
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=[self.node_addr_map["node1"]],
                ),
            ]
        )

    def test_cib_remote_node(self):
        resources = f"""
            <resources>
                <primitive class="ocf" provider="pacemaker" type="remote"
                    id="R"
                >
                    <instance_attributes>
                        <nvpair name="server"
                            value="{self.node_addr_map["node1"]}"
                        />
                    </instance_attributes>
                </primitive>
            </resources>
        """
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load(resources=resources)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_link(
                self.env_assist.get_env(),
                self.node_addr_map,
                self.link_options,
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=[self.node_addr_map["node1"]],
                ),
            ]
        )

    def test_cib_not_available(self):
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load(stderr="an error", returncode=1)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_link(
                self.env_assist.get_env(),
                self.node_addr_map,
                self.link_options,
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.CIB_LOAD_ERROR_GET_NODES_FOR_VALIDATION,
                    force_code=report_codes.FORCE,
                ),
            ]
        )

    def test_cib_not_available_forced(self):
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load(stderr="an error", returncode=1)
        self.config.env.push_corosync_conf(corosync_conf_text=self.after)

        cluster.add_link(
            self.env_assist.get_env(),
            self.node_addr_map,
            self.link_options,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.CIB_LOAD_ERROR_GET_NODES_FOR_VALIDATION,
                ),
            ]
        )

    def test_offline_nodes(self):
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load()
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.after,
            skip_offline_targets=True,
        )

        cluster.add_link(
            self.env_assist.get_env(),
            self.node_addr_map,
            self.link_options,
            force_flags=[report_codes.SKIP_OFFLINE_NODES],
        )

    def test_unresolvable_addresses(self):
        patch_getaddrinfo(self, [])
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load()

        self.env_assist.assert_raise_library_error(
            lambda: cluster.add_link(
                self.env_assist.get_env(),
                self.node_addr_map,
                self.link_options,
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=list(self.node_addr_map.values()),
                )
            ]
        )

    def test_unresolvable_addresses_forced(self):
        patch_getaddrinfo(self, [])
        self.config.corosync_conf.load_content(self.before)
        self.config.runner.cib.load()
        self.config.env.push_corosync_conf(corosync_conf_text=self.after)

        cluster.add_link(
            self.env_assist.get_env(),
            self.node_addr_map,
            self.link_options,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=list(self.node_addr_map.values()),
                )
            ]
        )
