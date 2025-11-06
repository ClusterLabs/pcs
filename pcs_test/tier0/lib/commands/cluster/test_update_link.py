from textwrap import dedent
from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import patch_getaddrinfo


class UpdateLink(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2"])
        self.link_options = {"mcastport": "12345"}
        self.node_addr_map = {"node2": "node2-addr2a"}
        self.existing_addrs = [
            "node1-addr0",
            "node1-addr2",
            "node2-addr0",
            "node2-addr2",
        ]
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
                    mcastport: 12345
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
                    ring2_addr: node2-addr2a
                    name: node2
                    nodeid: 2
                }
            }
            """
        )

    def test_not_live(self):
        self.config.env.set_corosync_conf_data("")

        self.env_assist.assert_raise_library_error(
            lambda: cluster.update_link(self.env_assist.get_env(), "0", {}, {}),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=["COROSYNC_CONF"],
                ),
            ],
            expected_in_processor=False,
        )

    def test_missing_input_data(self):
        patch_getaddrinfo(self, self.existing_addrs)
        self.config.corosync_conf.load_content(self.before)
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.before, need_stopped_cluster=True
        )

        cluster.update_link(self.env_assist.get_env(), "0", {}, {})
        # Reports from pushing corosync.conf are produced in env. That code is
        # hidden in self.config.env.push_corosync_conf.
        self.env_assist.assert_reports([])

    def test_offline_nodes(self):
        patch_getaddrinfo(
            self, self.existing_addrs + list(self.node_addr_map.values())
        )
        self.config.corosync_conf.load_content(self.before)
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.after,
            skip_offline_targets=True,
            need_stopped_cluster=True,
        )

        cluster.update_link(
            self.env_assist.get_env(),
            "2",
            self.node_addr_map,
            self.link_options,
            force_flags=[report_codes.SKIP_OFFLINE_NODES],
        )

    def test_unresolvable_addresses(self):
        patch_getaddrinfo(self, self.existing_addrs)
        self.config.corosync_conf.load_content(self.before)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.update_link(
                self.env_assist.get_env(),
                "2",
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
        patch_getaddrinfo(self, self.existing_addrs)
        self.config.corosync_conf.load_content(self.before)
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.after, need_stopped_cluster=True
        )

        cluster.update_link(
            self.env_assist.get_env(),
            "2",
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


class UpdateLinkKnet(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2"])
        self.existing_addrs = [
            "node1-addr0",
            "node1-addr2",
            "node2-addr0",
            "node2-addr2",
        ]
        self.before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 2
                    mcastport: 1234
                    knet_transport: sctp
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

    def test_success(self):
        after = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 2
                    knet_transport: udp
                    knet_link_priority: 10
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
                    ring2_addr: node2-addr2a
                    name: node2
                    nodeid: 2
                }
            }
            """
        )
        patch_getaddrinfo(self, self.existing_addrs + ["node2-addr2a"])
        self.config.corosync_conf.load_content(self.before)
        self.config.env.push_corosync_conf(
            corosync_conf_text=after, need_stopped_cluster=True
        )

        cluster.update_link(
            self.env_assist.get_env(),
            "2",
            {"node2": "node2-addr2a"},
            {"mcastport": "", "transport": "udp", "link_priority": "10"},
        )
        # Reports from pushing corosync.conf are produced in env. That code is
        # hidden in self.config.env.push_corosync_conf.
        self.env_assist.assert_reports([])

    def test_success_deprecated_sctp(self):
        before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 2
                    knet_transport: udp
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
                    ring2_addr: node2-addr2a
                    name: node2
                    nodeid: 2
                }
            }
            """
        )
        after = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 2
                    knet_transport: sctp
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
                    ring2_addr: node2-addr2a
                    name: node2
                    nodeid: 2
                }
            }
            """
        )
        patch_getaddrinfo(self, self.existing_addrs + ["node2-addr2a"])
        self.config.corosync_conf.load_content(before)
        self.config.env.push_corosync_conf(
            corosync_conf_text=after, need_stopped_cluster=True
        )

        cluster.update_link(
            self.env_assist.get_env(),
            "2",
            {"node2": "node2-addr2a"},
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

    def test_validation(self):
        patch_getaddrinfo(self, self.existing_addrs + ["node2-addr0"])
        self.config.corosync_conf.load_content(self.before)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.update_link(
                self.env_assist.get_env(),
                "2",
                {
                    "nodeX": "addr-new",
                    "node2": "",
                    "node1": "node2-addr0",
                },
                {
                    "wrong": "option",
                    "transport": "unknown",
                    "link_priority": 10,
                },
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="unknown",
                    option_name="transport",
                    allowed_values=("sctp", "udp"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["wrong"],
                    option_type="link",
                    allowed=[
                        "link_priority",
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
                    report_codes.NODE_NOT_FOUND,
                    node="nodeX",
                    searched_types=[],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_CANNOT_BE_EMPTY,
                    node_name_list=["node2"],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=["addr-new"],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["node2-addr0"],
                ),
            ]
        )


class UpdateLinkUdp(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3"])
        self.existing_addrs = ["node1-addr0", "node2-addr0", "node3-addr0"]
        self.before = dedent(
            """\
            totem {
                transport: udp

                interface {
                    broadcast: yes
                    mcastport: 1234
                    ttl: 128
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }

                node {
                    ring0_addr: node3-addr0
                    name: node3
                    nodeid: 3
                }
            }
            """
        )

    def test_success(self):
        after = dedent(
            """\
            totem {
                transport: udp

                interface {
                    ttl: 128
                    mcastaddr: 225.0.0.1
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addrA
                    name: node2
                    nodeid: 2
                }

                node {
                    ring0_addr: node3-addr0
                    name: node3
                    nodeid: 3
                }
            }
            """
        )
        patch_getaddrinfo(self, self.existing_addrs + ["node2-addrA"])
        self.config.corosync_conf.load_content(self.before)
        self.config.env.push_corosync_conf(
            corosync_conf_text=after, need_stopped_cluster=True
        )

        cluster.update_link(
            self.env_assist.get_env(),
            "0",
            {"node2": "node2-addrA"},
            {"mcastport": "", "broadcast": "0", "mcastaddr": "225.0.0.1"},
        )
        # Reports from pushing corosync.conf are produced in env. That code is
        # hidden in self.config.env.push_corosync_conf.
        self.env_assist.assert_reports([])

    def test_validation(self):
        patch_getaddrinfo(self, self.existing_addrs + ["node3-addr0"])
        self.config.corosync_conf.load_content(self.before)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.update_link(
                self.env_assist.get_env(),
                "0",
                {
                    "nodeX": "addr-new",
                    "node2": "",
                    "node1": "node3-addr0",
                },
                {
                    "wrong": "option",
                    "broadcast": "1",
                    "mcastaddr": "address",
                },
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="address",
                    option_name="mcastaddr",
                    allowed_values="an IP address",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["wrong"],
                    option_type="link",
                    allowed=[
                        "bindnetaddr",
                        "broadcast",
                        "mcastaddr",
                        "mcastport",
                        "ttl",
                    ],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_DISABLED,
                    option_name="mcastaddr",
                    option_type="link",
                    prerequisite_name="broadcast",
                    prerequisite_type="link",
                ),
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node="nodeX",
                    searched_types=[],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_CANNOT_BE_EMPTY,
                    node_name_list=["node2"],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=["addr-new"],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["node3-addr0"],
                ),
            ]
        )
