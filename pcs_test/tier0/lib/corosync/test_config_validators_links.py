# pylint: disable=too-many-lines
from unittest import TestCase

from pcs.common.corosync_conf import CorosyncNodeAddressType
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.node import PacemakerNode
from pcs.lib.corosync import (
    config_validators,
    constants,
    node,
)

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal
from pcs_test.tools.custom_mock import patch_getaddrinfo

forbidden_characters_kwargs = dict(
    allowed_values=None,
    cannot_be_empty=False,
    forbidden_characters=r"{}\n\r",
)


_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED = (
    "an integer greater than or equal to 200"
)


class AddLink(TestCase):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.new_addrs = {
            "node1": "addr1-new",
            "node2": "addr2-new",
            "node3": "addr3-new",
        }
        self.transport = constants.TRANSPORTS_KNET[0]
        self.existing_link_list = ["0", "1", "3"]
        self.coro_nodes = [
            node.CorosyncNode(
                f"node{i}",
                [
                    node.CorosyncNodeAddress(f"addr{i}-{j}", f"{j}")
                    for j in self.existing_link_list
                ],
                i,
            )
            for i in [1, 2, 3]
        ]
        self.pcmk_nodes = []
        patch_getaddrinfo(self, self.new_addrs.values())

    def test_success(self):
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {
                    "linknumber": "2",
                    "link_priority": "2",
                    "mcastport": "5405",
                    "ping_interval": "300",
                    "ping_precision": "10",
                    "ping_timeout": "250",
                    "pong_count": "5",
                    "transport": "udp",
                },
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [],
        )

    def test_success_no_options(self):
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [],
        )

    def _assert_bad_transport(self, transport):
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_BAD_TRANSPORT,
                    add_or_not_remove=True,
                    actual_transport=transport,
                    required_transports=["knet"],
                )
            ],
        )

    def test_transport_udp(self):
        self._assert_bad_transport("udp")

    def test_transport_udpu(self):
        self._assert_bad_transport("udpu")

    def test_ping_interval_without_ping_timeout(self):
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {
                    "linknumber": "2",
                    "ping_interval": "300",
                },
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="ping_interval",
                    option_type="link",
                    prerequisite_name="ping_timeout",
                    prerequisite_type="link",
                ),
            ],
        )

    def test_ping_timeout_without_ping_interval(self):
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {
                    "linknumber": "2",
                    "ping_timeout": "250",
                },
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="ping_timeout",
                    option_type="link",
                    prerequisite_name="ping_interval",
                    prerequisite_type="link",
                ),
            ],
        )

    def test_too_many_links(self):
        existing_link_list = [str(x) for x in range(constants.LINKS_KNET_MAX)]
        coro_nodes = [
            node.CorosyncNode(
                f"node{i}",
                [
                    node.CorosyncNodeAddress(f"addr{i}-{j}", f"{j}")
                    for j in existing_link_list
                ],
                i,
            )
            for i in [1, 2, 3]
        ]
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                coro_nodes,
                self.pcmk_nodes,
                existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS,
                    links_change_count=1,
                    links_new_count=(constants.LINKS_KNET_MAX + 1),
                    links_limit_count=constants.LINKS_KNET_MAX,
                    add_or_not_remove=True,
                )
            ],
        )

    def test_add_last_allowed_link(self):
        existing_link_list = [
            str(x) for x in range(constants.LINKS_KNET_MAX - 1)
        ]
        coro_nodes = [
            node.CorosyncNode(
                f"node{i}",
                [
                    node.CorosyncNodeAddress(f"addr{i}-{j}", f"{j}")
                    for j in existing_link_list
                ],
                i,
            )
            for i in [1, 2, 3]
        ]
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                coro_nodes,
                self.pcmk_nodes,
                existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [],
        )

    def test_link_already_exists(self):
        linknumber = self.existing_link_list[1]
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {"linknumber": linknumber},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_ALREADY_EXISTS_CANNOT_ADD,
                    link_number=linknumber,
                )
            ],
        )

    def test_missing_node_addrs(self):
        broken_nodes = sorted(self.new_addrs.keys())[1:2]
        for node_name in broken_nodes:
            del self.new_addrs[node_name]
        pcmk_nodes = [PacemakerNode("node-remote", "addr-remote")]
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=1,
                    node_name=node_name,
                    node_index=None,
                )
                for node_name in broken_nodes
            ],
        )

    def test_empty_node_addr(self):
        broken_nodes = sorted(self.new_addrs.keys())[1:]
        for node_name in broken_nodes:
            self.new_addrs[node_name] = ""
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_CANNOT_BE_EMPTY,
                    node_name_list=broken_nodes,
                ),
            ],
        )

    def test_used_addrs(self):
        pcmk_nodes = [PacemakerNode("node-remote", "addr-remote")]
        already_existing_addrs = [
            pcmk_nodes[0].addr,
            self.coro_nodes[0].addrs_plain()[0],
        ]
        (
            self.new_addrs["node2"],
            self.new_addrs["node3"],
        ) = already_existing_addrs
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=already_existing_addrs,
                ),
            ],
        )

    def test_unknown_node(self):
        unknown_nodes = ["node4", "node5"]
        for node_name in unknown_nodes:
            self.new_addrs[node_name] = f"{node_name}-addr"
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node=node_name,
                    searched_types=[],
                )
                for node_name in unknown_nodes
            ],
        )

    def test_duplicate_addrs(self):
        self.new_addrs["node1"] = self.new_addrs["node2"]
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=[self.new_addrs["node1"]],
                )
            ],
        )

    def test_unresolvable_addrs(self):
        patch_getaddrinfo(self, list(self.new_addrs.values())[2:])
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=list(self.new_addrs.values())[:2],
                )
            ],
        )

    def test_unresolvable_addrs_forced(self):
        patch_getaddrinfo(self, list(self.new_addrs.values())[2:])
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
                force_unresolvable=True,
            ),
            [
                fixture.warn(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=list(self.new_addrs.values())[:2],
                )
            ],
        )

    def test_mixing_ip_families(self):
        new_addrs = {
            "node1": "addr1-new",
            "node2": "10.0.2.2",
            "node3": "::ffff:10:0:2:3",
        }
        assert_report_item_list_equal(
            config_validators.add_link(
                new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[],
                ),
            ],
        )

    def test_wrong_ip_family_4(self):
        self.new_addrs["node2"] = "::ffff:10:0:2:2"
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_4,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
                    address=self.new_addrs["node2"],
                    expected_address_type=CorosyncNodeAddressType.IPV4.value,
                    link_number=None,
                ),
            ],
        )

    def test_wrong_ip_family_6(self):
        self.new_addrs["node2"] = "10.0.2.2"
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {},
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_6,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
                    address=self.new_addrs["node2"],
                    expected_address_type=CorosyncNodeAddressType.IPV6.value,
                    link_number=None,
                ),
            ],
        )

    def test_link_options(self):
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {
                    "linknumber": "ln",
                    "link_priority": "lp",
                    "mcastport": "mp",
                    "ping_interval": "pi",
                    "ping_precision": "pp",
                    "wrong": "option",
                    "ping_timeout": "pt",
                    "pong_count": "pc",
                    "bad": "option",
                    "transport": "t",
                },
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="linknumber",
                    option_value="ln",
                    allowed_values="0..7",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="link_priority",
                    option_value="lp",
                    allowed_values="0..255",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mcastport",
                    option_value="mp",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="ping_interval",
                    option_value="pi",
                    allowed_values=_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="ping_precision",
                    option_value="pp",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="ping_timeout",
                    option_value="pt",
                    allowed_values=_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="pong_count",
                    option_value="pc",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="transport",
                    option_value="t",
                    allowed_values=("sctp", "udp"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["bad", "wrong"],
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
            ],
        )

    def test_forbidden_characters(self):
        assert_report_item_list_equal(
            config_validators.add_link(
                {
                    "node1": "addr1-new\n",
                    "node2": "addr2{-}new",
                    "node3": "addr3-new",
                },
                {
                    "linknumber": "\n2",
                    "link_priority": "2\r",
                    "mcastport": "}5405",
                    "ping_interval": "300{",
                    "ping_precision": "\r10\n",
                    "ping_timeout": "{250}",
                    "pong_count": "5\n",
                    "transport": "udp}",
                    "op:.tion": "va}l{ue",
                },
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="addr1-new\n",
                    option_name="node address",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="addr2{-}new",
                    option_name="node address",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=["addr1-new\n", "addr2{-}new"],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tion"],
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
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="link",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\n2",
                    option_name="linknumber",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="2\r",
                    option_name="link_priority",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}5405",
                    option_name="mcastport",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="300{",
                    option_name="ping_interval",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\r10\n",
                    option_name="ping_precision",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="{250}",
                    option_name="ping_timeout",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="5\n",
                    option_name="pong_count",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="udp}",
                    option_name="transport",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ue",
                    option_name="op:.tion",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="2\r",
                    option_name="link_priority",
                    allowed_values="0..255",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}5405",
                    option_name="mcastport",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="300{",
                    option_name="ping_interval",
                    allowed_values=_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\r10\n",
                    option_name="ping_precision",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="{250}",
                    option_name="ping_timeout",
                    allowed_values=_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="5\n",
                    option_name="pong_count",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="udp}",
                    option_name="transport",
                    allowed_values=("sctp", "udp"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\n2",
                    option_name="linknumber",
                    allowed_values="0..7",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_deprecated_sctp_knet_transport(self):
        assert_report_item_list_equal(
            config_validators.add_link(
                self.new_addrs,
                {
                    "transport": "sctp",
                },
                self.coro_nodes,
                self.pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="transport",
                    deprecated_value="sctp",
                    replaced_by=None,
                )
            ],
        )


class RemoveLinks(TestCase):
    def setUp(self):
        self.existing = ["0", "3", "10", "1", "11"]

    def test_no_link_specified(self):
        assert_report_item_list_equal(
            config_validators.remove_links([], self.existing, "knet"),
            [
                fixture.error(
                    report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_NO_LINKS_SPECIFIED,
                    add_or_not_remove=False,
                )
            ],
        )

    def _assert_bad_transport(self, transport):
        assert_report_item_list_equal(
            config_validators.remove_links(["3"], self.existing, transport),
            [
                fixture.error(
                    report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_BAD_TRANSPORT,
                    add_or_not_remove=False,
                    actual_transport=transport,
                    required_transports=["knet"],
                )
            ],
        )

    def test_transport_udp(self):
        self._assert_bad_transport("udp")

    def test_transport_udpu(self):
        self._assert_bad_transport("udpu")

    def test_nonexistent_links(self):
        to_remove = ["15", "0", "4", "abc", "1"]
        assert len(to_remove) >= len(self.existing)

        assert_report_item_list_equal(
            config_validators.remove_links(to_remove, self.existing, "knet"),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE,
                    link_list=sorted(["abc", "4", "15"]),
                    existing_link_list=sorted(["0", "1", "3", "10", "11"]),
                )
            ],
        )

    def test_zero_links_left(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                self.existing, self.existing, "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS,
                    links_change_count=len(self.existing),
                    links_new_count=0,
                    links_limit_count=1,
                    add_or_not_remove=False,
                )
            ],
        )

    def test_remove_more_than_defined(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                self.existing + ["2"], self.existing, "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS,
                    # We try to remove more links than defined yet only defined
                    # links are counted here - nonexistent links cannot be
                    # defined so they are not included in the count
                    links_change_count=len(self.existing),
                    # the point of the test is to not get negative number here
                    links_new_count=0,
                    links_limit_count=1,
                    add_or_not_remove=False,
                ),
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE,
                    link_list=["2"],
                    existing_link_list=sorted(["0", "1", "3", "10", "11"]),
                ),
            ],
        )

    def test_duplicate_links(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                ["abc", "abc", "11", "11", "1", "1", "3"], self.existing, "knet"
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_NUMBER_DUPLICATION,
                    link_number_list=sorted(["abc", "1", "11"]),
                ),
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE,
                    link_list=["abc"],
                    existing_link_list=sorted(["0", "1", "3", "10", "11"]),
                ),
            ],
        )

    def test_success(self):
        assert_report_item_list_equal(
            config_validators.remove_links(
                ["0", "3", "11"], self.existing, "knet"
            ),
            [],
        )


class UpdateLinkCommon(TestCase):
    # Link update validator is complex, this class tests common cases. For more
    # specific tests see other UpdateLink* classes.
    def test_no_addrs_no_options(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "0",
                {},
                {},
                {},
                [],
                [],
                ["0"],
                constants.TRANSPORTS_UDP[0],
                constants.IP_VERSION_64,
            ),
            [],
        )

    def test_nonexistent_link(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "1",
                {},
                {},
                {},
                [],
                [],
                ["0"],
                constants.TRANSPORTS_UDP[0],
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_UPDATE,
                    link_number="1",
                    existing_link_list=["0"],
                ),
            ],
        )


class UpdateLinkAddressesMixin:
    def test_swap_addresses(self):
        new_addrs = {
            self.coro_nodes[0].name: (
                self.coro_nodes[1].addr_plain_for_link(self.linknumber)
            ),
            self.coro_nodes[1].name: (
                self.coro_nodes[0].addr_plain_for_link(self.linknumber)
            ),
        }
        patch_getaddrinfo(self, list(new_addrs.values()) + self.existing_addrs)

        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                new_addrs,
                {},
                {},
                self.coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [],
        )

    def test_duplicate_new_addresses(self):
        new_addrs = {
            self.coro_nodes[0].name: "addr-new1",
            self.coro_nodes[1].name: "addr-new2",
            self.coro_nodes[2].name: "addr-new1",
        }
        patch_getaddrinfo(self, list(new_addrs.values()) + self.existing_addrs)

        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                new_addrs,
                {},
                {},
                self.coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_DUPLICATION,
                    address_list=["addr-new1"],
                ),
            ],
        )

    def test_remove_address(self):
        patch_getaddrinfo(self, self.existing_addrs)
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    self.coro_nodes[0].name: "",
                },
                {},
                {},
                self.coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_CANNOT_BE_EMPTY,
                    node_name_list=[self.coro_nodes[0].name],
                ),
            ],
        )

    def test_address_vs_ip_version(self):
        report_4 = fixture.error(
            report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
            address="10.0.0.1",
            expected_address_type=CorosyncNodeAddressType.IPV6.value,
            link_number=self.linknumber,
        )
        report_6 = fixture.error(
            report_codes.COROSYNC_ADDRESS_IP_VERSION_WRONG_FOR_LINK,
            address="::ffff:10:0:2:3",
            expected_address_type=CorosyncNodeAddressType.IPV4.value,
            link_number=self.linknumber,
        )
        test_matrix = (
            (constants.IP_VERSION_4, "10.0.0.1", []),
            (constants.IP_VERSION_4, "::ffff:10:0:2:3", [report_6]),
            (constants.IP_VERSION_6, "10.0.0.1", [report_4]),
            (constants.IP_VERSION_6, "::ffff:10:0:2:3", []),
            (constants.IP_VERSION_46, "10.0.0.1", []),
            (constants.IP_VERSION_46, "::ffff:10:0:2:3", []),
            (constants.IP_VERSION_64, "10.0.0.1", []),
            (constants.IP_VERSION_64, "::ffff:10:0:2:3", []),
            (constants.IP_VERSION_4, "new-addr", []),
            (constants.IP_VERSION_6, "new-addr", []),
            (constants.IP_VERSION_46, "new-addr", []),
            (constants.IP_VERSION_64, "new-addr", []),
        )
        patch_getaddrinfo(self, self.existing_addrs + ["new-addr"])
        for ip_version, new_ip, reports in test_matrix:
            with self.subTest(ip_version=ip_version, new_ip=new_ip):
                assert_report_item_list_equal(
                    config_validators.update_link(
                        self.linknumber,
                        {
                            self.coro_nodes[0].name: new_ip,
                        },
                        {},
                        {},
                        self.coro_nodes,
                        [],
                        self.existing_link_list,
                        self.transport,
                        ip_version,
                    ),
                    reports,
                )

    def test_mixing_ip_families_new_vs_new(self):
        patch_getaddrinfo(self, self.existing_addrs)
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    self.coro_nodes[0].name: "10.0.0.1",
                    self.coro_nodes[1].name: "::ffff:10:0:2:3",
                },
                {},
                {},
                self.coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[],
                ),
            ],
        )

    def test_unresolvable(self):
        patch_getaddrinfo(self, self.existing_addrs)
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    self.coro_nodes[0].name: "addr-new",
                },
                {},
                {},
                self.coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE,
                    address_list=["addr-new"],
                ),
            ],
        )

    def test_unresolvable_forced(self):
        patch_getaddrinfo(self, self.existing_addrs)
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    self.coro_nodes[0].name: "addr-new",
                },
                {},
                {},
                self.coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
                force_unresolvable=True,
            ),
            [
                fixture.warn(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addr-new"],
                ),
            ],
        )

    def test_unknown_nodes(self):
        patch_getaddrinfo(self, self.existing_addrs)
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    "nodeX": "10.0.0.1",
                },
                {},
                {},
                self.coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_NOT_FOUND,
                    node="nodeX",
                    searched_types=[],
                )
            ],
        )

    def test_forbidden_characters(self):
        new_addrs = {
            self.coro_nodes[0].name: "addr-new1\n",
            self.coro_nodes[1].name: "}addr-new2{",
            self.coro_nodes[2].name: "addr-new3",
        }
        patch_getaddrinfo(self, list(new_addrs.values()) + self.existing_addrs)

        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                new_addrs,
                {},
                {},
                self.coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="addr-new1\n",
                    option_name="node address",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}addr-new2{",
                    option_name="node address",
                    **forbidden_characters_kwargs,
                ),
            ],
        )


class UpdateLinkAddressesUdp(UpdateLinkAddressesMixin, TestCase):
    def setUp(self):
        self.linknumber = "0"
        self.transport = constants.TRANSPORTS_UDP[0]
        self.existing_link_list = ["0"]
        self.coro_nodes = [
            node.CorosyncNode(
                f"node{i}", [node.CorosyncNodeAddress(f"addr{i}", "0")], i
            )
            for i in range(1, 5)
        ]
        self.existing_addrs = []
        for a_node in self.coro_nodes:
            self.existing_addrs.extend(a_node.addrs_plain())

    def test_new_address_already_used(self):
        pcmk_nodes = [PacemakerNode("node-remote", "addr-remote")]
        new_addrs = {
            self.coro_nodes[1].name: self.coro_nodes[0].addr_plain_for_link(
                "0"
            ),
            self.coro_nodes[2].name: pcmk_nodes[0].addr,
            self.coro_nodes[3].name: "new-addr",
        }
        patch_getaddrinfo(self, list(new_addrs.values()) + self.existing_addrs)

        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                new_addrs,
                {},
                {},
                self.coro_nodes,
                pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=["addr-remote", "addr1"],
                ),
            ],
        )

    def test_mixing_ip_families_new_vs_ipv6(self):
        patch_getaddrinfo(self, self.existing_addrs)
        coro_nodes = [
            node.CorosyncNode(
                f"node{i}",
                [node.CorosyncNodeAddress(f"::ffff:10:0:2:{i}", "0")],
                i,
            )
            for i in range(1, 3)
        ]
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    self.coro_nodes[0].name: "10.0.1.1",
                },
                {},
                {},
                coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[],
                ),
            ],
        )

    def test_mixing_ip_families_new_vs_ipv4(self):
        patch_getaddrinfo(self, self.existing_addrs)
        coro_nodes = [
            node.CorosyncNode(
                f"node{i}", [node.CorosyncNodeAddress(f"10.0.0.{i}", "0")], i
            )
            for i in range(1, 3)
        ]
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    self.coro_nodes[0].name: "::ffff:10:0:3:1",
                },
                {},
                {},
                coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[],
                ),
            ],
        )


class UpdateLinkAddressesKnet(UpdateLinkAddressesMixin, TestCase):
    def setUp(self):
        self.linknumber = "1"
        self.transport = constants.TRANSPORTS_KNET[0]
        self.existing_link_list = ["0", "1", "3"]
        self.coro_nodes = [
            node.CorosyncNode(
                f"node{i}",
                [
                    node.CorosyncNodeAddress(f"addr{i}-{j}", f"{j}")
                    for j in self.existing_link_list
                ],
                i,
            )
            for i in range(1, 5)
        ]
        self.existing_addrs = []
        for a_node in self.coro_nodes:
            self.existing_addrs.extend(a_node.addrs_plain())

    def test_new_address_already_used(self):
        pcmk_nodes = [PacemakerNode("node-remote", "addr-remote")]
        new_addrs = {
            self.coro_nodes[0].name: self.coro_nodes[3].addr_plain_for_link(
                "1"
            ),
            self.coro_nodes[1].name: self.coro_nodes[1].addr_plain_for_link(
                "0"
            ),
            self.coro_nodes[2].name: pcmk_nodes[0].addr,
        }
        patch_getaddrinfo(self, list(new_addrs.values()) + self.existing_addrs)

        assert_report_item_list_equal(
            config_validators.update_link(
                "1",
                new_addrs,
                {},
                {},
                self.coro_nodes,
                pcmk_nodes,
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_ALREADY_EXIST,
                    address_list=sorted(new_addrs.values()),
                ),
            ],
        )

    def test_mixing_ip_families_new_vs_ipv6(self):
        patch_getaddrinfo(self, self.existing_addrs)
        coro_nodes = [
            node.CorosyncNode(
                f"node{i}",
                [
                    node.CorosyncNodeAddress(f"addr{i}", "0"),
                    node.CorosyncNodeAddress(f"::ffff:10:0:2:{i}", "1"),
                    node.CorosyncNodeAddress(f"10.0.0.{i}", "3"),
                ],
                i,
            )
            for i in range(1, 3)
        ]
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    self.coro_nodes[0].name: "10.0.1.1",
                },
                {},
                {},
                coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[],
                ),
            ],
        )

    def test_mixing_ip_families_new_vs_ipv4(self):
        patch_getaddrinfo(self, self.existing_addrs)
        coro_nodes = [
            node.CorosyncNode(
                f"node{i}",
                [
                    node.CorosyncNodeAddress(f"addr{i}", "0"),
                    node.CorosyncNodeAddress(f"10.0.0.{i}", "1"),
                    node.CorosyncNodeAddress(f"::ffff:10:0:2:{i}", "3"),
                ],
                i,
            )
            for i in range(1, 3)
        ]
        assert_report_item_list_equal(
            config_validators.update_link(
                self.linknumber,
                {
                    self.coro_nodes[0].name: "::ffff:10:0:3:1",
                },
                {},
                {},
                coro_nodes,
                [],
                self.existing_link_list,
                self.transport,
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_IP_VERSION_MISMATCH_IN_LINKS,
                    link_numbers=[],
                ),
            ],
        )


class UpdateLinkKnet(TestCase):
    def test_individual_options_set(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "2",
                {},
                {
                    "linknumber": "ln",
                    "link_priority": "lp",
                    "mcastport": "mp",
                    "ping_interval": "pi",
                    "ping_precision": "pp",
                    "wrong": "option",
                    "ping_timeout": "pt",
                    "pong_count": "pc",
                    "transport": "t",
                },
                {},
                [],
                [],
                [
                    "2",
                ],
                constants.TRANSPORTS_KNET[0],
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="link_priority",
                    option_value="lp",
                    allowed_values="0..255",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mcastport",
                    option_value="mp",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="ping_interval",
                    option_value="pi",
                    allowed_values=_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="ping_precision",
                    option_value="pp",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="ping_timeout",
                    option_value="pt",
                    allowed_values=_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="pong_count",
                    option_value="pc",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="transport",
                    option_value="t",
                    allowed_values=("sctp", "udp"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["linknumber", "wrong"],
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
            ],
        )

    def test_individual_options_unset(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "2",
                {},
                {
                    "linknumber": "",
                    "link_priority": "",
                    "mcastport": "",
                    "ping_interval": "",
                    "ping_precision": "",
                    "ping_timeout": "",
                    "pong_count": "",
                    "transport": "",
                    "not_valid": "",
                },
                {},
                [],
                [],
                [
                    "2",
                ],
                constants.TRANSPORTS_KNET[0],
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["linknumber", "not_valid"],
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
            ],
        )

    @staticmethod
    def _prepare_new_option(options, option_name, set_unset):
        if set_unset is False:
            options[option_name] = ""
        elif set_unset is True:
            options[option_name] = "200"

    def test_ping_interval_ping_timeout_dependencies(self):
        test_matrix = (
            # first tuple: a change to be made
            # - ping_interval, ping_timeout
            # - None: no change, False: unset, True: set
            # second tuple: errors expected?
            # - when both were unset, when both were set
            # - we do not consider broken initial status of only one of
            #   timeout, interval set
            ((None, None), (None, None)),
            ((None, False), (None, "interval")),
            ((None, True), ("timeout", None)),
            ((False, None), (None, "timeout")),
            ((False, False), (None, None)),
            ((False, True), ("timeout", "timeout")),
            ((True, None), ("interval", None)),
            ((True, False), ("interval", "interval")),
            ((True, True), (None, None)),
        )
        initial_both_unset = {
            "linknumber": "2",
        }
        initial_both_set = {
            "linknumber": "2",
            "ping_interval": "10",
            "ping_timeout": "10",
        }
        for update_definition, error_definition in test_matrix:
            for error_index, initial_options in enumerate(
                [initial_both_unset, initial_both_set]
            ):
                error_expected = error_definition[error_index]
                new_options = {}
                self._prepare_new_option(
                    new_options, "ping_interval", update_definition[0]
                )
                self._prepare_new_option(
                    new_options, "ping_timeout", update_definition[1]
                )
                with self.subTest(
                    initial_options=initial_options,
                    new_options=new_options,
                    error_expected=error_expected,
                ):
                    reports = []
                    if error_expected and "interval" in error_expected:
                        reports = [
                            fixture.error(
                                report_codes.PREREQUISITE_OPTION_IS_MISSING,
                                option_name="ping_interval",
                                option_type="link",
                                prerequisite_name="ping_timeout",
                                prerequisite_type="link",
                            ),
                        ]
                    if error_expected and "timeout" in error_expected:
                        reports = [
                            fixture.error(
                                report_codes.PREREQUISITE_OPTION_IS_MISSING,
                                option_name="ping_timeout",
                                option_type="link",
                                prerequisite_name="ping_interval",
                                prerequisite_type="link",
                            ),
                        ]
                    assert_report_item_list_equal(
                        config_validators.update_link(
                            "2",
                            {},
                            new_options,
                            initial_options,
                            [],
                            [],
                            [
                                "2",
                            ],
                            constants.TRANSPORTS_KNET[0],
                            constants.IP_VERSION_64,
                        ),
                        reports,
                    )

    def test_ping_interval_ping_timeout_initially_broken(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "2",
                {},
                {},
                {
                    "linknumber": "2",
                    "ping_timeout": "10",
                },
                [],
                [],
                [
                    "2",
                ],
                constants.TRANSPORTS_KNET[0],
                constants.IP_VERSION_64,
            ),
            [],
        )

    def test_forbidden_characters(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "2",
                {},
                {
                    "link_priority": "2\r",
                    "mcastport": "}5405",
                    "ping_interval": "300{",
                    "ping_precision": "\r10\n",
                    "ping_timeout": "{250}",
                    "pong_count": "5\n",
                    "transport": "udp}",
                    "op:.tion": "va}l{ue",
                },
                {},
                [],
                [],
                [
                    "2",
                ],
                constants.TRANSPORTS_KNET[0],
                constants.IP_VERSION_64,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tion"],
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
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="link",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="2\r",
                    option_name="link_priority",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}5405",
                    option_name="mcastport",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="300{",
                    option_name="ping_interval",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\r10\n",
                    option_name="ping_precision",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="{250}",
                    option_name="ping_timeout",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="5\n",
                    option_name="pong_count",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="udp}",
                    option_name="transport",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ue",
                    option_name="op:.tion",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="2\r",
                    option_name="link_priority",
                    allowed_values="0..255",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}5405",
                    option_name="mcastport",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="300{",
                    option_name="ping_interval",
                    allowed_values=_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\r10\n",
                    option_name="ping_precision",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="{250}",
                    option_name="ping_timeout",
                    allowed_values=_FIXTURE_KNET_PING_INTERVAL_TIMEOUT_EXPECTED,
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="5\n",
                    option_name="pong_count",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="udp}",
                    option_name="transport",
                    allowed_values=("sctp", "udp"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_deprecated_sctp_knet_transport(self):
        assert_report_item_list_equal(
            config_validators.update_link(
                "2",
                {},
                {
                    "transport": "sctp",
                },
                {},
                [],
                [],
                [
                    "2",
                ],
                constants.TRANSPORTS_KNET[0],
                constants.IP_VERSION_64,
            ),
            [
                fixture.deprecation(
                    report_codes.DEPRECATED_OPTION_VALUE,
                    option_name="transport",
                    deprecated_value="sctp",
                    replaced_by=None,
                ),
            ],
        )


class UpdateLinkUdp(TestCase):
    broadcast_values = (None, "", "0", "1")
    mcastaddr_values = (None, "", "225.1.2.3")
    mcast_error = fixture.error(
        report_codes.PREREQUISITE_OPTION_MUST_BE_DISABLED,
        option_name="mcastaddr",
        option_type="link",
        prerequisite_name="broadcast",
        prerequisite_type="link",
    )

    @staticmethod
    def _fixture_new_values(broadcast, mcastaddr):
        new_values = {}
        if broadcast is not None:
            new_values["broadcast"] = broadcast
        if mcastaddr is not None:
            new_values["mcastaddr"] = mcastaddr
        return new_values

    def test_individual_options_set(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "0",
                {},
                {
                    "bindnetaddr": "my-network",
                    "broadcast": "yes",
                    "mcastaddr": "my-group",
                    "mcastport": "0",
                    "ttl": "256",
                    "wrong": "value",
                },
                {},
                [],
                [],
                [
                    "0",
                ],
                constants.TRANSPORTS_UDP[0],
                constants.IP_VERSION_4,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="my-network",
                    option_name="bindnetaddr",
                    allowed_values="an IP address",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="yes",
                    option_name="broadcast",
                    allowed_values=("0", "1"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="my-group",
                    option_name="mcastaddr",
                    allowed_values="an IP address",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="0",
                    option_name="mcastport",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="256",
                    option_name="ttl",
                    allowed_values="0..255",
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
            ],
        )

    def test_individual_options_unset(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "0",
                {},
                {
                    "bindnetaddr": "",
                    "broadcast": "",
                    "mcastaddr": "",
                    "mcastport": "",
                    "ttl": "",
                    "wrong": "",
                },
                {},
                [],
                [],
                [
                    "0",
                ],
                constants.TRANSPORTS_UDP[0],
                constants.IP_VERSION_4,
            ),
            [
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
            ],
        )

    def _assert_broadcast_mcast_dependencies(
        self, initial_options, error_expected_for_input
    ):
        for broadcast in self.broadcast_values:
            for mcastaddr in self.mcastaddr_values:
                new_options = self._fixture_new_values(broadcast, mcastaddr)
                error_expected = new_options in error_expected_for_input
                with self.subTest(
                    initial_options=initial_options,
                    new_options=new_options,
                    error_expected=error_expected,
                ):
                    assert_report_item_list_equal(
                        config_validators.update_link(
                            "0",
                            {},
                            new_options,
                            initial_options,
                            [],
                            [],
                            [
                                "0",
                            ],
                            constants.TRANSPORTS_UDP[0],
                            constants.IP_VERSION_4,
                        ),
                        [self.mcast_error] if error_expected else [],
                    )

    def test_broadcast_mcastaddr_dependencies_both_unset(self):
        initial_options = {}
        error_expected_for_input = (
            {"broadcast": "1", "mcastaddr": "225.1.2.3"},
        )
        self._assert_broadcast_mcast_dependencies(
            initial_options, error_expected_for_input
        )

    def test_broadcast_mcastaddr_dependencies_both_disabled(self):
        initial_options = {"broadcast": "0"}
        error_expected_for_input = (
            {"broadcast": "1", "mcastaddr": "225.1.2.3"},
        )
        self._assert_broadcast_mcast_dependencies(
            initial_options, error_expected_for_input
        )

    def test_broadcast_mcastaddr_dependencies_broadcast_enabled(self):
        initial_options = {"broadcast": "1"}
        error_expected_for_input = (
            {"mcastaddr": "225.1.2.3"},
            {"broadcast": "1", "mcastaddr": "225.1.2.3"},
        )
        self._assert_broadcast_mcast_dependencies(
            initial_options, error_expected_for_input
        )

    def test_broadcast_mcastaddr_dependencies_mcastaddr_enabled(self):
        initial_options = {"mcastaddr": "255.2.4.5"}
        error_expected_for_input = (
            {"broadcast": "1"},
            {"broadcast": "1", "mcastaddr": "225.1.2.3"},
        )
        self._assert_broadcast_mcast_dependencies(
            initial_options, error_expected_for_input
        )

    def test_forbidden_characters(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(
            config_validators.update_link(
                "0",
                {},
                {
                    "bindnetaddr": "10.1.2.0\n",
                    "broadcast": "1\r",
                    "mcastaddr": "248.251.1.10{",
                    "mcastport": "5405}",
                    "ttl": "128{}",
                    "op:.tion": "va}l{ue",
                },
                {},
                [],
                [],
                [
                    "0",
                ],
                constants.TRANSPORTS_UDP[0],
                constants.IP_VERSION_4,
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tion"],
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
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="link",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="10.1.2.0\n",
                    option_name="bindnetaddr",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="1\r",
                    option_name="broadcast",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="248.251.1.10{",
                    option_name="mcastaddr",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="5405}",
                    option_name="mcastport",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="128{}",
                    option_name="ttl",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ue",
                    option_name="op:.tion",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="10.1.2.0\n",
                    option_name="bindnetaddr",
                    allowed_values="an IP address",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="1\r",
                    option_name="broadcast",
                    allowed_values=("0", "1"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="248.251.1.10{",
                    option_name="mcastaddr",
                    allowed_values="an IP address",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="5405}",
                    option_name="mcastport",
                    allowed_values="a port number (1..65535)",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="128{}",
                    option_name="ttl",
                    allowed_values="0..255",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )
