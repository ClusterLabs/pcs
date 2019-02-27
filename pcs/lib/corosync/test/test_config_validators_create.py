# pylint: disable=too-many-lines
from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.corosync import config_validators
from pcs.test.tools import fixture
from pcs.test.tools.assertions import assert_report_item_list_equal
from pcs.test.tools.custom_mock import patch_getaddrinfo

# pylint: disable=no-self-use

class Create(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.known_addrs = patch_getaddrinfo(
            self,
            [f"addr{i:02d}" for i in range(1, 20)]
            +
            [f"10.0.0.{i}" for i in range(1, 20)]
            +
            [f"::ffff:10:0:0:{i}" for i in range(1, 20)]
        )

    def test_all_valid_one_node(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01"]},
                ],
                "udp"
            ),
            []
        )

    def test_all_valid_udp(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01"]},
                    {"name": "node2", "addrs": ["addr02"]},
                ],
                "udp"
            ),
            []
        )

    def test_all_valid_knet(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {
                        "name": "node1",
                        "addrs": ["addr01", "10.0.0.1", "::ffff:10:0:0:1"]
                    },
                    {
                        "name": "node2",
                        "addrs": ["addr02", "10.0.0.2", "::ffff:10:0:0:2"]
                    },
                ],
                "knet"
            ),
            []
        )

    def test_clustername_transport_invalid(self):
        assert_report_item_list_equal(
            config_validators.create(
                "",
                [
                    {"name": "node1", "addrs": ["addr01"]},
                    {"name": "node2", "addrs": ["addr02"]},
                ],
                "tcp"
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="cluster name",
                    allowed_values="a non-empty string"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="tcp",
                    option_name="transport",
                    allowed_values=("knet", "udp", "udpu")
                ),
            ]
        )

    def test_nodelist_empty(self):
        assert_report_item_list_equal(
            config_validators.create("test-cluster", [], "udp"),
            [
                fixture.error(
                    report_codes.COROSYNC_NODES_MISSING
                )
            ]
        )

    def test_empty_node(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01"]},
                    {},
                ],
                "udp"
            ),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["name"],
                    option_type="node 2"
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=1,
                    node_name=None,
                    node_index=2
                ),
            ]
        )

    def test_node_options_invalid(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01"]},
                    {"name": "node2", "addrs": ["addr02"], "nonsense": "abc"},
                ],
                "udp"
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense"],
                    option_type="node",
                    allowed=["addrs", "name"],
                    allowed_patterns=[],
                ),
            ]
        )

    def test_nodename_invalid(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "", "addrs": ["addr01"]},
                    {"addrs": ["addr02"]},
                ],
                "udp"
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="node 1 name",
                    allowed_values="a non-empty string"
                ),
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["name"],
                    option_type="node 2"
                ),
            ]
        )

    def test_nodename_not_unique(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01"]},
                    {"name": "node2", "addrs": ["addr02"]},
                    {"name": "node2", "addrs": ["addr03"]},
                    {"name": "node3", "addrs": ["addr04"]},
                    {"name": "node1", "addrs": ["addr05"]},
                    # invalid nodes are not reported as duplicate
                    {"name": "", "addrs": ["addr06"]},
                    {"name": "", "addrs": ["addr07"]},
                ],
                "udp"
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="node 6 name",
                    allowed_values="a non-empty string"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="node 7 name",
                    allowed_values="a non-empty string"
                ),
                fixture.error(
                    report_codes.NODE_NAMES_DUPLICATION,
                    name_list=["node1", "node2"]
                )
            ]
        )

    def test_node_addrs_missing_udp(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1"},
                    {"name": "node2", "addrs": []},
                    {"name": "node3", "addrs": None},
                ],
                "udp"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=1,
                    node_name=name,
                    node_index=id
                )
                for id, name in enumerate(["node1", "node2", "node3"], 1)
            ]
        )

    def test_node_addrs_missing_knet(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1"},
                    {"name": "node2", "addrs": []},
                    {"name": "node3", "addrs": None},
                ],
                "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=8,
                    node_name=name,
                    node_index=id
                )
                for id, name in enumerate(["node1", "node2", "node3"], 1)
            ]
        )

    def test_node_addrs_to_many_udp(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01", "addr03"]},
                    {"name": "node2", "addrs": ["addr02", "addr04"]},
                ],
                "udp"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=2,
                    min_count=1,
                    max_count=1,
                    node_name="node1",
                    node_index=1
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=2,
                    min_count=1,
                    max_count=1,
                    node_name="node2",
                    node_index=2
                ),
            ]
        )

    def test_node_addrs_to_many_knet(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {
                        "name": "node1",
                        "addrs": [f"addr{i:02d}" for i in range(1, 10)]
                    },
                    {
                        "name": "node2",
                        "addrs": [f"addr{i:02d}" for i in range(11, 20)]
                    },
                ],
                "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=9,
                    min_count=1,
                    max_count=8,
                    node_name="node1",
                    node_index=1
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=9,
                    min_count=1,
                    max_count=8,
                    node_name="node2",
                    node_index=2
                ),
            ]
        )

    def test_node_addrs_unresolvable(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    # Duplicated addresses reported only once but they trigger
                    # a duplicate addresses report.
                    {"name": "node1", "addrs": ["addr01", "addrX2"]},
                    {"name": "node2", "addrs": ["addrX2", "addr05"]},
                    {"name": "node3", "addrs": ["addr03", "addrX1"]},
                ],
                "knet"
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addrX1", "addrX2"]
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=["addrX2"]
                ),
            ]
        )

    def test_node_addrs_unresolvable_forced(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    # Duplicated addresses reported only once but they trigger
                    # a duplicate addresses report.
                    {"name": "node1", "addrs": ["addr01", "addrX2"]},
                    {"name": "node2", "addrs": ["addrX2", "addr05"]},
                    {"name": "node3", "addrs": ["addr03", "addrX1"]},
                ],
                "knet",
                force_unresolvable=True
            ),
            [
                fixture.warn(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addrX1", "addrX2"]
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=["addrX2"]
                ),
            ]
        )

    def test_node_addrs_not_unique(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {
                        "name": "node1",
                        "addrs": ["addr01", "10.0.0.1", "::ffff:10:0:0:1"]
                    },
                    {
                        "name": "node2",
                        "addrs": ["addr02", "10.0.0.2", "::ffff:10:0:0:2"]
                    },
                    {
                        "name": "node3",
                        "addrs": ["addr02", "10.0.0.1", "::ffff:10:0:0:4"]
                    },
                    {
                        "name": "node4",
                        "addrs": ["addr04", "10.0.0.1", "::ffff:10:0:0:4"]
                    },
                ],
                "knet"
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=["10.0.0.1", "::ffff:10:0:0:4", "addr02"]
                )
            ]
        )

    def test_node_addrs_count_mismatch_udp(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01", "addr11"]},
                    {"name": "node2", "addrs": ["addr02"]},
                    {"name": "node3", "addrs": ["addr03", "addr13"]},
                    {"name": "node4", "addrs": ["addr04"]},
                    {"name": "node5", "addrs": ["addr05", "addr15", "addr16"]},
                ],
                "udp"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=2,
                    min_count=1,
                    max_count=1,
                    node_name="node1",
                    node_index=1
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=2,
                    min_count=1,
                    max_count=1,
                    node_name="node3",
                    node_index=3
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=3,
                    min_count=1,
                    max_count=1,
                    node_name="node5",
                    node_index=5
                ),
            ]
        )

    def test_node_addrs_count_mismatch_knet(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01", "addr11"]},
                    {"name": "node2", "addrs": ["addr02"]},
                    {"name": "node3", "addrs": ["addr03", "addr13"]},
                    {"name": "node4", "addrs": ["addr04"]},
                    {"name": "node5", "addrs": ["addr05", "addr15", "addr16"]},
                ],
                "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_NODE_ADDRESS_COUNT_MISMATCH,
                    node_addr_count={
                        "node1": 2,
                        "node2": 1,
                        "node3": 2,
                        "node4": 1,
                        "node5": 3,
                    }
                )
            ]
        )

    def test_node_addrs_count_mismatch_knet_invalid_names(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01", "addr11"]},
                    {"name": "", "addrs": ["addr02"]},
                ],
                "knet"
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="node 2 name",
                    allowed_values="a non-empty string"
                ),
            ]
        )

    def test_node_addrs_count_mismatch_knet_duplicate_names(self):
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {"name": "node1", "addrs": ["addr01", "addr11"]},
                    {"name": "node1", "addrs": ["addr02"]},
                ],
                "knet"
            ),
            [
                fixture.error(
                    report_codes.NODE_NAMES_DUPLICATION,
                    name_list=["node1"]
                )
            ]
        )

    def test_node_addrs_ip_version_mismatch(self):
        # test setup:
        # * links 0..2: match
        # * link 3, 5: one node has names, other nodes have IPs, match
        # * link 4: one node has names, other nodes have IPs, mismatch
        # * link 6: all nodes have IPs, mismatch
        # * link 7: one node missing, two nodes have IPs, mismatch
        assert_report_item_list_equal(
            config_validators.create(
                "test-cluster",
                [
                    {
                        "name": "node1",
                        "addrs": [
                            "addr01",
                            "10.0.0.1",
                            "::ffff:10:0:0:1",
                            "addr03",
                            "addr04",
                            "addr05",
                            "10.0.0.4",
                            "::ffff:10:0:0:5",
                        ]
                    },
                    {
                        "name": "node2",
                        "addrs": [
                            "addr02",
                            "10.0.0.2",
                            "::ffff:10:0:0:2",
                            "10.0.0.3",
                            "10.0.0.9",
                            "::ffff:10:0:0:3",
                            "::ffff:10:0:0:4",
                            "10.0.0.5",
                        ]
                    },
                    {
                        "name": "node3",
                        "addrs": [
                            "addr10",
                            "10.0.0.12",
                            "::ffff:10:0:0:12",
                            "10.0.0.13",
                            "::ffff:10:0:0:11",
                            "::ffff:10:0:0:13",
                            "::ffff:10:0:0:14",
                        ]
                    },
                ],
                "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_NODE_ADDRESS_COUNT_MISMATCH,
                    node_addr_count={
                        "node1": 8,
                        "node2": 8,
                        "node3": 7,
                    }
                ),
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[4, 6, 7]
                )
            ]
        )


class CreateLinkListCommonMixin():
    def test_no_links(self):
        assert_report_item_list_equal(
            self._validate([], self.default_addr_count),
            []
        )

    def test_no_options(self):
        assert_report_item_list_equal(
            self._validate([{}], self.default_addr_count),
            []
        )

    def test_less_link_options_than_links(self):
        # If number of links options <= number of addresses, then everything is
        # ok. Number of addresses is checked in another validator.
        assert_report_item_list_equal(
            self._validate(
                [
                    {"mcastport": "5405"},
                    {"mcastport": "5405"},
                ],
                3
            ),
            [
            ]
        )

    def test_link_options_count_equals_links_count(self):
        assert_report_item_list_equal(
            self._validate(
                [
                    {"mcastport": "5405"},
                ],
                1
            ),
            [
            ]
        )

    def test_more_link_options_than_links(self):
        assert_report_item_list_equal(
            self._validate(
                [
                    {"mcastport": "5405"},
                    {"mcastport": "5405"},
                ],
                1
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_TOO_MANY_LINKS_OPTIONS,
                    links_options_count=2,
                    links_count=1,
                )
            ]
        )

    def test_max_links_count_too_low(self):
        assert_report_item_list_equal(
            self._validate(
                [
                    {"mcastport": "5405"},
                ],
                -1
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_TOO_MANY_LINKS_OPTIONS,
                    links_options_count=1,
                    links_count=0,
                )
            ]
        )

    def test_max_links_count_too_high(self):
        # If number of links options <= number of addresses, then everything is
        # ok. Number of addresses is checked in another validator.
        assert_report_item_list_equal(
            self._validate(
                [
                    {"mcastport": "5405"} for _ in range(10)
                ],
                10
            ),
            [
            ]
        )


class CreateLinkListUdp(CreateLinkListCommonMixin, TestCase):
    default_addr_count = 1

    def _validate(self, *args, **kwargs):
        return config_validators.create_link_list_udp(*args, **kwargs)

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "bindnetaddr": "10.0.0.1",
                        "broadcast": "0",
                        "mcastaddr": "225.0.0.1",
                        "mcastport": "5405",
                        "ttl": "12",
                    }
                ],
                1
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "bindnetaddr": "my-network",
                        "broadcast": "yes",
                        "mcastaddr": "my-group",
                        "mcastport": "0",
                        "ttl": "256",
                    }
                ],
                1
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="my-network",
                    option_name="bindnetaddr",
                    allowed_values="an IP address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="yes",
                    option_name="broadcast",
                    allowed_values=("0", "1")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="my-group",
                    option_name="mcastaddr",
                    allowed_values="an IP address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="0",
                    option_name="mcastport",
                    allowed_values="a port number (1-65535)"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="256",
                    option_name="ttl",
                    allowed_values="0..255"
                ),
            ]
        )

    def test_invalid_options(self):
        allowed_options = [
            "bindnetaddr",
            "broadcast",
            "mcastaddr",
            "mcastport",
            "ttl",
        ]
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "linknumber": "0",
                        "nonsense": "doesnt matter",
                    }
                ],
                1
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["linknumber", "nonsense"],
                    option_type="link",
                    allowed=allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_broadcast_default_mcastaddr_set(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "mcastaddr": "225.0.0.1"
                    }
                ],
                1
            ),
            [
            ]
        )

    def test_broadcast_disabled_mcastaddr_set(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "broadcast": "0",
                        "mcastaddr": "225.0.0.1"
                    }
                ],
                1
            ),
            [
            ]
        )

    def test_broadcast_enabled_mcastaddr_set(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "broadcast": "1",
                        "mcastaddr": "225.0.0.1"
                    }
                ],
                1
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_DISABLED,
                    option_name="mcastaddr",
                    option_type="link",
                    prerequisite_name="broadcast",
                    prerequisite_type="link"
                ),
            ]
        )


class CreateLinkListKnet(CreateLinkListCommonMixin, TestCase):
    default_addr_count = 8

    def _validate(self, *args, **kwargs):
        return config_validators.create_link_list_knet(*args, **kwargs)

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "linknumber": "0",
                        "link_priority": "20",
                        "mcastport": "5405",
                        "ping_interval": "250",
                        "ping_precision": "15",
                        "ping_timeout": "750",
                        "pong_count": "10",
                        "transport": "sctp",
                    },
                    {
                        "linknumber": "1",
                        "link_priority": "10",
                        "mcastport": "5415",
                        "ping_interval": "2500",
                        "ping_precision": "150",
                        "ping_timeout": "7500",
                        "pong_count": "100",
                        "transport": "udp",
                    }
                ],
                2
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "linknumber": "-1",
                        "link_priority": "256",
                        "mcastport": "65536",
                        "transport": "tcp",
                    },
                    {
                        "ping_interval": "-250",
                        "ping_precision": "-15",
                        "ping_timeout": "-750",
                        "pong_count": "-10",
                        "transport": "udpu",
                    }
                ],
                3
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-1",
                    option_name="linknumber",
                    allowed_values="0..7"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="256",
                    option_name="link_priority",
                    allowed_values="0..255"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="65536",
                    option_name="mcastport",
                    allowed_values="a port number (1-65535)"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="tcp",
                    option_name="transport",
                    allowed_values=("sctp", "udp")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-250",
                    option_name="ping_interval",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-15",
                    option_name="ping_precision",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-750",
                    option_name="ping_timeout",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-10",
                    option_name="pong_count",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="udpu",
                    option_name="transport",
                    allowed_values=("sctp", "udp")
                ),
            ]
        )

    def test_invalid_options(self):
        allowed_options = [
            "link_priority",
            "linknumber",
            "mcastport",
            "ping_interval",
            "ping_precision",
            "ping_timeout",
            "pong_count",
            "transport",
        ]
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "nonsense1": "0",
                        "nonsense2": "doesnt matter",
                    },
                    {
                        "nonsense3": "who cares",
                    }
                ],
                3
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense1", "nonsense2"],
                    option_type="link",
                    allowed=allowed_options,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense3"],
                    option_type="link",
                    allowed=allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_invalid_option_ip_version(self):
        allowed_options = [
            "link_priority",
            "linknumber",
            "mcastport",
            "ping_interval",
            "ping_precision",
            "ping_timeout",
            "pong_count",
            "transport",
        ]
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "ip_version": "ipv4",
                    },
                ],
                2
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["ip_version"],
                    option_type="link",
                    allowed=allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_ping_dependencies(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "ping_interval": "250",
                        "ping_timeout": "750",
                    },
                    {
                        "ping_interval": "250",
                    },
                    {
                        "ping_timeout": "750",
                    },
                    {
                        "ping_interval": "",
                        "ping_timeout": "750",
                    },
                    {
                        "ping_interval": "250",
                        "ping_timeout": "",
                    },
                ],
                5
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="ping_interval",
                    option_type="link",
                    prerequisite_name="ping_timeout",
                    prerequisite_type="link"
                ),
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="ping_timeout",
                    option_type="link",
                    prerequisite_name="ping_interval",
                    prerequisite_type="link"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="ping_interval",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="ping_timeout",
                    allowed_values="a non-negative integer"
                ),
            ]
        )

    def test_linknumber_higher_than_link_count(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [{"linknumber": "3"}],
                2
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_UPDATE,
                    link_number="3",
                    link_count=2,
                ),
            ]
        )

    def test_linknumber_equals_link_count(self):
        # This must report because link numbers start with 0.
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [{"linknumber": "2"}],
                2
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_UPDATE,
                    link_number="2",
                    link_count=2,
                ),
            ]
        )

    def test_linknumber_lower_than_link_count(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [{"linknumber": "1"}],
                2
            ),
            [
            ]
        )

    def test_linknumber_not_unique(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {"linknumber": "2"},
                    {"linknumber": "0"},
                    {"linknumber": "0"},
                    {"linknumber": "1"},
                    {"linknumber": "2"},
                ],
                5
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_NUMBER_DUPLICATION,
                    link_number_list=["0", "2"]
                )
            ]
        )


class CreateTransportUdp(TestCase):
    def test_no_options(self):
        assert_report_item_list_equal(
            config_validators.create_transport_udp({}, {}, {}),
            []
        )

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_transport_udp(
                {
                    "ip_version": "ipv4",
                    "netmtu": "1234",
                },
                {},
                {}
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_transport_udp(
                {
                    "ip_version": "ipv5",
                    "netmtu": "-5",
                },
                {},
                {}
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv5",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6", "ipv4-6", "ipv6-4")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-5",
                    option_name="netmtu",
                    allowed_values="a positive integer"
                ),
            ]
        )

    def test_invalid_option(self):
        assert_report_item_list_equal(
            config_validators.create_transport_udp(
                {
                    "knet_pmtud_interval": "1234",
                    "link_mode": "active",
                },
                {
                    "level": "5",
                    "model": "zlib",
                    "threshold": "1234",
                },
                {
                    "cipher": "aes256",
                    "hash": "sha256",
                    "model": "nss",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["knet_pmtud_interval", "link_mode"],
                    option_type="udp/udpu transport",
                    allowed=["ip_version", "netmtu"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
                    option_type="compression",
                    actual_transport="udp/udpu",
                    required_transport_list=("knet", )
                ),
                fixture.error(
                    report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
                    option_type="crypto",
                    actual_transport="udp/udpu",
                    required_transport_list=("knet", )
                ),
            ]
        )



class CreateTransportKnet(TestCase):
    def test_no_options(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet({}, {}, {}),
            []
        )

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {
                    "ip_version": "ipv4",
                    "knet_pmtud_interval": "1234",
                    "link_mode": "active",
                },
                {
                    "level": "5",
                    "model": "zlib",
                    "threshold": "1234",
                },
                {
                    "cipher": "aes256",
                    "hash": "sha256",
                    "model": "nss",
                }
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {
                    "ip_version": "ipv5",
                    "knet_pmtud_interval": "a minute",
                    "link_mode": "random",
                },
                {
                    "level": "maximum",
                    "model": "",
                    "threshold": "reasonable",
                },
                {
                    "cipher": "strongest",
                    "hash": "fastest",
                    "model": "best",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv5",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6", "ipv4-6", "ipv6-4")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="a minute",
                    option_name="knet_pmtud_interval",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="random",
                    option_name="link_mode",
                    allowed_values=("active", "passive", "rr")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="maximum",
                    option_name="level",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="model",
                    allowed_values="a compression model e.g. zlib, lz4 or bzip2"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="reasonable",
                    option_name="threshold",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="strongest",
                    option_name="cipher",
                    allowed_values=(
                        "none", "aes256", "aes192", "aes128", "3des"
                    )
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="fastest",
                    option_name="hash",
                    allowed_values=(
                        "none", "md5", "sha1", "sha256", "sha384", "sha512"
                    )
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="best",
                    option_name="model",
                    allowed_values=("nss", "openssl")
                ),
            ]
        )

    def test_invalid_options(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {
                    "level": "5",
                    "netmtu": "1500",
                },
                {
                    "cipher": "aes256",
                    "hash": "sha256",
                },
                {
                    "ip_version": "ipv4",
                    "link_mode": "active",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["level", "netmtu"],
                    option_type="knet transport",
                    allowed=["ip_version", "knet_pmtud_interval", "link_mode"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["cipher", "hash"],
                    option_type="compression",
                    allowed=["level", "model", "threshold"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["ip_version", "link_mode"],
                    option_type="crypto",
                    allowed=["cipher", "hash", "model"],
                    allowed_patterns=[],
                ),
            ]
        )

    def test_crypto_disabled(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "none",
                    "hash": "none",
                }
            ),
            []
        )

    def test_crypto_enabled_cipher_disabled_hash(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "aes256",
                    "hash": "none",
                }
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="cipher",
                    option_type="crypto",
                    prerequisite_name="hash",
                    prerequisite_type="crypto"
                )
            ]
        )

    def test_crypto_enabled_cipher_default_hash(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "aes256",
                }
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="cipher",
                    option_type="crypto",
                    prerequisite_name="hash",
                    prerequisite_type="crypto"
                )
            ]
        )

    def test_crypto_disabled_cipher_default_hash(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "none",
                }
            ),
            []
        )

    def test_crypto_enabled_hash_disabled_cipher(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "none",
                    "hash": "sha256",
                }
            ),
            []
        )

    def test_crypto_enabled_hash_default_cipher(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "hash": "sha256",
                }
            ),
            []
        )

    def test_crypto_disabled_hash_default_cipher(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "hash": "none",
                }
            ),
            []
        )


class CreateTotem(TestCase):
    allowed_options = [
        "consensus",
        "downcheck",
        "fail_recv_const",
        "heartbeat_failures_allowed",
        "hold",
        "join",
        "max_messages",
        "max_network_delay",
        "merge",
        "miss_count_const",
        "send_join",
        "seqno_unchanged_const",
        "token",
        "token_coefficient",
        "token_retransmit",
        "token_retransmits_before_loss_const",
        "window_size",
    ]
    def test_no_options(self):
        assert_report_item_list_equal(
            config_validators.create_totem({}),
            []
        )

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_totem(
                {
                    name: value
                    for value, name in enumerate(self.allowed_options)
                }
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_totem(
                {
                    name: "x"
                    for name in self.allowed_options
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="x",
                    option_name=name,
                    allowed_values="a non-negative integer"
                )
                for name in self.allowed_options
            ]
        )

    def test_invalid_options(self):
        assert_report_item_list_equal(
            config_validators.create_totem(
                {
                    "nonsense1": "0",
                    "nonsense2": "doesnt matter",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense1", "nonsense2"],
                    option_type="totem",
                    allowed=self.allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )
