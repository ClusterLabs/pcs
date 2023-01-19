from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.cib.node import PacemakerNode as PNode
from pcs.lib.corosync import config_validators
from pcs.lib.corosync.node import CorosyncNode as CNode
from pcs.lib.corosync.node import CorosyncNodeAddress as CAddr

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal
from pcs_test.tools.custom_mock import patch_getaddrinfo

# pylint: disable=no-self-use

forbidden_characters_kwargs = dict(
    allowed_values=None,
    cannot_be_empty=False,
    forbidden_characters=r"{}\n\r",
)


class AddNodes(TestCase):
    # pylint: disable=too-many-public-methods
    fixture_coronodes_1_link = [
        CNode("node1", [CAddr("addr01", 1)], 1),
        CNode("node2", [CAddr("addr02", 1)], 2),
    ]

    fixture_coronodes_2_links = [
        CNode("node1", [CAddr("addr01", 1), CAddr("addr11", 2)], 1),
        CNode("node2", [CAddr("addr02", 1), CAddr("addr12", 2)], 2),
    ]

    def setUp(self):
        self.known_addrs = patch_getaddrinfo(
            self,
            [f"addr{i:02d}" for i in range(1, 20)]
            + [f"10.0.0.{i}" for i in range(1, 20)]
            + [f"::ffff:10:0:0:{i}" for i in range(1, 20)],
        )

    def test_all_valid_one_node_one_link(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["addr03"]},
                ],
                self.fixture_coronodes_1_link,
                [],
            ),
            [],
        )

    def test_all_more_nodes_more_links(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["addr03", "addr13"]},
                    {"name": "node4", "addrs": ["addr04", "addr14"]},
                ],
                self.fixture_coronodes_2_links,
                [PNode("node-remote", "addr19")],
            ),
            [],
        )

    def test_nodelist_empty(self):
        assert_report_item_list_equal(
            config_validators.add_nodes([], self.fixture_coronodes_1_link, []),
            [fixture.error(report_codes.COROSYNC_NODES_MISSING)],
        )

    def test_empty_node(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["addr03"]},
                    {},
                    {"name": "node4", "addrs": ["addr04"]},
                ],
                self.fixture_coronodes_1_link,
                [],
            ),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["name"],
                    option_type="node 2",
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=1,
                    node_name=None,
                    node_index=2,
                ),
            ],
        )

    def test_node_options_invalid(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["addr03"], "nonsense": "abc"},
                ],
                self.fixture_coronodes_1_link,
                [],
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense"],
                    option_type="node",
                    allowed=["addrs", "name"],
                    allowed_patterns=[],
                ),
            ],
        )

    def test_nodename_invalid(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "", "addrs": ["addr03"]},
                    {"addrs": ["addr04"]},
                ],
                self.fixture_coronodes_1_link,
                [],
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="node 1 name",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.REQUIRED_OPTIONS_ARE_MISSING,
                    option_names=["name"],
                    option_type="node 2",
                ),
            ],
        )

    def test_nodename_not_unique(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["addr03"]},
                    {"name": "node3", "addrs": ["addr04"]},
                    # invalid nodes are not reported as duplicate
                    {"name": "", "addrs": ["addr05"]},
                    {"name": "", "addrs": ["addr06"]},
                ],
                self.fixture_coronodes_1_link,
                [],
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="node 3 name",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="node 4 name",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.NODE_NAMES_DUPLICATION, name_list=["node3"]
                ),
            ],
        )

    def test_nodename_already_used(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["addr03"]},
                    {"name": "node2", "addrs": ["addr04"]},
                    {"name": "node-remote", "addrs": ["addr05"]},
                ],
                [
                    CNode("node1", [CAddr("addr01", 1)], 1),
                    CNode("node2", [CAddr("addr02", 1)], 2),
                ],
                [PNode("node-remote", "addr19")],
            ),
            [
                fixture.error(
                    report_codes.NODE_NAMES_ALREADY_EXIST,
                    name_list=["node-remote", "node2"],
                )
            ],
        )

    def test_node_addrs_missing(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3"},
                    {"name": "node4", "addrs": []},
                    {"name": "node5", "addrs": None},
                ],
                self.fixture_coronodes_1_link,
                [],
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=1,
                    node_name=name,
                    node_index=id,
                )
                for id, name in enumerate(["node3", "node4", "node5"], 1)
            ],
        )

    def test_node_addrs_count_mismatch(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["addr03"]},
                    {"name": "node4", "addrs": ["addr04", "addr14"]},
                    {"name": "node5", "addrs": ["addr05", "addr15", "addr16"]},
                ],
                self.fixture_coronodes_2_links,
                [],
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=1,
                    min_count=2,
                    max_count=2,
                    node_name="node3",
                    node_index=1,
                ),
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=3,
                    min_count=2,
                    max_count=2,
                    node_name="node5",
                    node_index=3,
                ),
            ],
        )

    def test_node_addr_empty(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["", "addr13"]},
                    {"name": "node4", "addrs": ["addr04", "addr14"]},
                    {"name": "node5", "addrs": ["addr05", ""]},
                    {"name": "node6", "addrs": ["", ""]},
                    {"name": None, "addrs": ["", ""]},
                ],
                self.fixture_coronodes_2_links,
                [],
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_CANNOT_BE_EMPTY,
                    node_name_list=["node3", "node5", "node6"],
                ),
            ],
        )

    def test_node_addrs_unresolvable(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    # Duplicated addresses reported only once but they trigger
                    # a duplicate addresses report.
                    {"name": "node3", "addrs": ["addr03", "addrX2"]},
                    {"name": "node4", "addrs": ["addrX2", "addr14"]},
                    # Extra address reported as well, it triggres its own report
                    # about being an extra address.
                    {"name": "node5", "addrs": ["addr05", "addrX1", "addrX3"]},
                ],
                self.fixture_coronodes_2_links,
                [],
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=3,
                    min_count=2,
                    max_count=2,
                    node_name="node5",
                    node_index=3,
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=["addrX1", "addrX2", "addrX3"],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=["addrX2"],
                ),
            ],
        )

    def test_node_addrs_unresolvable_forced(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    # Duplicated addresses reported only once but they trigger
                    # a duplicate addresses report.
                    {"name": "node3", "addrs": ["addr03", "addrX2"]},
                    {"name": "node4", "addrs": ["addrX2", "addr14"]},
                    # Extra address reported as well, it triggres its own report
                    # about being an extra address.
                    {"name": "node5", "addrs": ["addr05", "addrX1", "addrX3"]},
                ],
                self.fixture_coronodes_2_links,
                [],
                force_unresolvable=True,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=3,
                    min_count=2,
                    max_count=2,
                    node_name="node5",
                    node_index=3,
                ),
                fixture.warn(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addrX1", "addrX2", "addrX3"],
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=["addrX2"],
                ),
            ],
        )

    def test_node_addrs_not_unique(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {
                        "name": "node3",
                        "addrs": ["addr03", "10.0.0.3", "::ffff:10:0:0:3"],
                    },
                    {
                        "name": "node4",
                        "addrs": ["addr04", "10.0.0.4", "::ffff:10:0:0:4"],
                    },
                    {
                        "name": "node5",
                        "addrs": ["addr04", "10.0.0.3", "::ffff:10:0:0:6"],
                    },
                    {
                        "name": "node6",
                        "addrs": ["addr06", "10.0.0.3", "::ffff:10:0:0:6"],
                    },
                ],
                [
                    CNode(
                        "node1",
                        [
                            CAddr("addr01", 1),
                            CAddr("10.0.0.1", 2),
                            CAddr("::ffff:10:0:0:1", 3),
                        ],
                        1,
                    ),
                    CNode(
                        "node2",
                        [
                            CAddr("addr02", 1),
                            CAddr("10.0.0.2", 2),
                            CAddr("::ffff:10:0:0:2", 3),
                        ],
                        2,
                    ),
                ],
                [],
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=["10.0.0.3", "::ffff:10:0:0:6", "addr04"],
                )
            ],
        )

    def test_node_addrs_already_used(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["addr03"]},
                    {"name": "node4", "addrs": ["addr02"]},
                    {"name": "node5", "addrs": ["addr19"]},
                ],
                [
                    CNode("node1", [CAddr("addr01", 1)], 1),
                    CNode("node2", [CAddr("addr02", 1)], 2),
                ],
                [PNode("node-remote", "addr19")],
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["addr02", "addr19"],
                )
            ],
        )

    def test_node_addrs_ip_version_ok(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {
                        "name": "node3",
                        "addrs": [
                            "addr03",
                            "::ffff:10:0:0:3",
                            "10.0.0.3",
                            "addr13",
                        ],
                    },
                    {
                        "name": "node4",
                        "addrs": [
                            "10.0.0.4",
                            "addr04",
                            "addr14",
                            "::ffff:10:0:0:4",
                        ],
                    },
                ],
                [
                    CNode(
                        "node1",
                        [
                            CAddr("addr01", 1),
                            CAddr("addr11", 2),
                            CAddr("10.0.0.1", 5),
                            CAddr("::ffff:10:0:0:1", 6),
                        ],
                        1,
                    ),
                    CNode(
                        "node2",
                        [
                            CAddr("addr02", 1),
                            CAddr("addr12", 2),
                            CAddr("10.0.0.2", 5),
                            CAddr("::ffff:10:0:0:2", 6),
                        ],
                        2,
                    ),
                ],
                [],
            ),
            [],
        )

    def test_node_addrs_ip_version_mismatch(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["::ffff:10:0:0:3"]},
                    {"name": "node4", "addrs": ["10.0.0.14"]},
                ],
                [
                    CNode("node1", [CAddr("addr01", 1)], 1),
                    CNode("node2", [CAddr("addr02", 1)], 2),
                ],
                [],
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[1],
                )
            ],
        )

    def test_node_addrs_mismatch_existing_links(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node3", "addrs": ["::ffff:10:0:0:3", "addr13"]},
                    {"name": "node4", "addrs": ["addr04", "10.0.0.14"]},
                ],
                [
                    CNode(
                        "node1", [CAddr("10.0.0.1", 1), CAddr("addr11", 2)], 1
                    ),
                    CNode(
                        "node2",
                        [CAddr("addr02", 1), CAddr("::ffff:10:0:0:2", 2)],
                        2,
                    ),
                ],
                [],
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
                    address="::ffff:10:0:0:3",
                    expected_address_type="IPv4",
                    link_number=1,
                ),
                fixture.error(
                    report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
                    address="10.0.0.14",
                    expected_address_type="IPv6",
                    link_number=2,
                ),
            ],
        )

    def test_node_addrs_ip_version_mismatch_complex(self):
        # several cases tested:
        # * not all links are defined - testing link indexes in reports
        # * link 1 - unresolvable addresses do not trigger ip mismatch reports
        # * link 3 - mismatch between new nodes only
        # * link 5 - mismatch between a new node and existing nodes,
        #   existing nodes mix FQDNs and IPs
        # * link 7 - mismatch between new nodes and new and existing node, only
        #   one report produced, existing nodes mix FQDNs and IPs
        # * node1 has an extra address which dosn't cause a crash trying to
        #   match it to a nonexisting link
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {
                        "name": "node3",
                        "addrs": [
                            "addrX1",
                            "::ffff:10:0:0:13",
                            "::ffff:10:0:0:3",
                            "10.0.0.3",
                            "10.0.0.13",
                        ],
                    },
                    {
                        "name": "node4",
                        "addrs": [
                            "addr04",
                            "10.0.0.4",
                            "addr14",
                            "::ffff:10:0:0:4",
                        ],
                    },
                ],
                [
                    CNode(
                        "node1",
                        [
                            CAddr("10.0.0.1", 1),
                            CAddr("addr11", 3),
                            CAddr("addr19", 5),
                            CAddr("addr18", 7),
                        ],
                        1,
                    ),
                    CNode(
                        "node2",
                        [
                            CAddr("addr02", 1),
                            CAddr("addr12", 3),
                            CAddr("10.0.0.2", 5),
                            CAddr("::ffff:10:0:0:2", 7),
                        ],
                        2,
                    ),
                ],
                [],
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=5,
                    min_count=4,
                    max_count=4,
                    node_name="node3",
                    node_index=1,
                ),
                fixture.error(
                    report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
                    address="::ffff:10:0:0:3",
                    expected_address_type="IPv4",
                    link_number=5,
                ),
                fixture.error(
                    report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
                    address="10.0.0.3",
                    expected_address_type="IPv6",
                    link_number=7,
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=["addrX1"],
                ),
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[3],
                ),
            ],
        )

    def test_forbidden_characters(self):
        assert_report_item_list_equal(
            config_validators.add_nodes(
                [
                    {"name": "node{3}", "addrs": ["\raddr03\n"]},
                ],
                self.fixture_coronodes_1_link,
                [],
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="node{3}",
                    option_name="node 1 name",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\raddr03\n",
                    option_name="node address",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=["\raddr03\n"],
                ),
            ],
        )


class RemoveNodes(TestCase):
    fixture_nodes = [
        CNode("node1", [CAddr("addr01", 1)], 1),
        CNode("node2", [CAddr("addr02", 1)], 2),
        CNode("node3", [CAddr("addr03", 1)], 3),
        CNode("node4", [CAddr("addr04", 1)], 4),
    ]

    def test_nonexisting_nodes(self):
        assert_report_item_list_equal(
            config_validators.remove_nodes(
                ["node3", "nodeX", "nodeY", "node4"],
                self.fixture_nodes,
                None,
                ({}, {}, {}),
            ),
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND, node=node, searched_types=[]
                )
                for node in ["nodeX", "nodeY"]
            ],
        )

    def test_all_nodes(self):
        assert_report_item_list_equal(
            config_validators.remove_nodes(
                ["node3", "node1", "node2", "node4"],
                self.fixture_nodes,
                None,
                ({}, {}, {}),
            ),
            [fixture.error(report_codes.CANNOT_REMOVE_ALL_CLUSTER_NODES)],
        )

    def test_qdevice_tie_breaker_none(self):
        assert_report_item_list_equal(
            config_validators.remove_nodes(
                ["node4"], self.fixture_nodes, "net", ({}, {}, {})
            ),
            [],
        )

    def test_qdevice_tie_breaker_generic(self):
        assert_report_item_list_equal(
            config_validators.remove_nodes(
                ["node4"],
                self.fixture_nodes,
                "net",
                ({"tie_breaker": "highest"}, {}, {}),
            ),
            [],
        )

    def test_qdevice_tie_breaker_kept(self):
        assert_report_item_list_equal(
            config_validators.remove_nodes(
                ["node4"],
                self.fixture_nodes,
                "net",
                ({"tie_breaker": "3"}, {}, {}),
            ),
            [],
        )

    def test_qdevice_tie_breaker_removed(self):
        assert_report_item_list_equal(
            config_validators.remove_nodes(
                ["node4"],
                self.fixture_nodes,
                "net",
                ({"tie_breaker": "4"}, {}, {}),
            ),
            [
                fixture.error(
                    report_codes.NODE_USED_AS_TIE_BREAKER,
                    node="node4",
                    node_id=4,
                ),
            ],
        )

    def test_more_errors(self):
        assert_report_item_list_equal(
            config_validators.remove_nodes(
                ["node3", "node1", "node2", "node4", "nodeX"],
                self.fixture_nodes,
                "net",
                ({"tie_breaker": "4"}, {}, {}),
            ),
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND, node="nodeX", searched_types=[]
                ),
                fixture.error(report_codes.CANNOT_REMOVE_ALL_CLUSTER_NODES),
                fixture.error(
                    report_codes.NODE_USED_AS_TIE_BREAKER,
                    node="node4",
                    node_id=4,
                ),
            ],
        )
