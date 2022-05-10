# pylint: disable=too-many-lines
from textwrap import dedent
from unittest import TestCase

import pcs.lib.corosync.config_facade as lib
from pcs.lib.corosync.config_parser import Parser

from pcs_test.tools.assertions import ac


def _get_facade(config_text):
    return lib.ConfigFacade(Parser.parse(config_text.encode("utf-8")))


class GetLinkOptions(TestCase):
    def _assert_options(self, config, options):
        facade = _get_facade(config)
        self.assertEqual(options, facade.get_links_options())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_options(self):
        self._assert_options("", {})

        self._assert_options(
            dedent(
                """\
                totem {
                }
            """
            ),
            {},
        )

    def test_no_linknumber(self):
        self._assert_options(
            dedent(
                """\
                totem {
                    interface {
                    }
                }
            """
            ),
            {"0": {"linknumber": "0"}},
        )

    def test_no_linknumber_more_sections(self):
        self._assert_options(
            dedent(
                """\
                totem {
                    transport: knet
                    interface {
                        mcastport: 1234
                    }
                    interface {
                        linknumber: 1
                        mcastport: 2345
                    }
                    interface {
                        mcastport: 3456
                    }
                }
            """
            ),
            {
                "0": {"linknumber": "0", "mcastport": "3456"},
                "1": {"linknumber": "1", "mcastport": "2345"},
            },
        )

    def test_all_options_knet(self):
        self._assert_options(
            dedent(
                """\
                totem {
                    transport: knet
                    interface {
                        linknumber: 1
                        mcastport: 2345
                        knet_link_priority: 2
                        knet_ping_interval: 3
                        knet_ping_precision: 4
                        knet_ping_timeout: 5
                        knet_pong_count: 6
                        knet_transport: sctp
                        unknown: option
                    }
                }
            """
            ),
            {
                "1": {
                    "linknumber": "1",
                    "mcastport": "2345",
                    "link_priority": "2",
                    "ping_interval": "3",
                    "ping_precision": "4",
                    "ping_timeout": "5",
                    "pong_count": "6",
                    "transport": "sctp",
                },
            },
        )

    def test_all_options_udp(self):
        self._assert_options(
            dedent(
                """\
                totem {
                    transport: udp
                    interface {
                        bindnetaddr: 10.0.0.1
                        broadcast: yes
                        mcastaddr: 10.0.0.2
                        mcastport: 1234
                        ttl: 123
                    }
                }
            """
            ),
            {
                "0": {
                    "bindnetaddr": "10.0.0.1",
                    "broadcast": "1",
                    "mcastaddr": "10.0.0.2",
                    "mcastport": "1234",
                    "ttl": "123",
                },
            },
        )

    def test_translate_conflict(self):
        self._assert_options(
            dedent(
                """\
                totem {
                    transport: knet
                    interface {
                        linknumber: 1
                        link_priority: 0
                        knet_link_priority: 2
                        link_priority: 3
                    }
                    interface {
                        linknumber: 1
                        link_priority: 4
                    }
                }
            """
            ),
            {
                "1": {
                    "linknumber": "1",
                    "link_priority": "2",
                },
            },
        )

    def test_more_sections_and_conflicting_options(self):
        self._assert_options(
            dedent(
                """\
                totem {
                    transport: knet
                    interface {
                        linknumber: 0
                        knet_link_priority: 3
                        knet_transport: sctp
                    }
                    interface {
                        linknumber: 1
                        knet_transport: udp
                    }
                    interface {
                        linknumber: 0
                        knet_link_priority: 4
                        knet_ping_interval: 2
                    }
                }
                totem {
                    interface {
                        linknumber: 0
                        knet_transport: udp
                    }
                }
            """
            ),
            {
                "0": {
                    "linknumber": "0",
                    "link_priority": "4",
                    "ping_interval": "2",
                    "transport": "udp",
                },
                "1": {
                    "linknumber": "1",
                    "transport": "udp",
                },
            },
        )


class AddLink(TestCase):
    before = dedent(
        """\
        totem {
            transport: knet

            interface {
                linknumber: 1
                knet_transport: udp
            }
        }

        nodelist {
            node {
                ring0_addr: node1-addr0
                ring1_addr: node1-addr1
                name: node1
                nodeid: 1
            }

            node {
                ring1_addr: node2-addr1
                ring0_addr: node2-addr0
                name: node2
                nodeid: 2
            }
        }
    """
    )

    @staticmethod
    def _assert_add(node_addr_map, options, before, after):
        facade = _get_facade(before)
        facade.add_link(node_addr_map, options)
        ac(after, facade.config.export())

    def test_addrs_only(self):
        self._assert_add(
            {"node1": "node1-addr2", "node2": "node2-addr2"},
            {},
            self.before,
            dedent(
                """\
                totem {
                    transport: knet

                    interface {
                        linknumber: 1
                        knet_transport: udp
                    }
                }

                nodelist {
                    node {
                        ring0_addr: node1-addr0
                        ring1_addr: node1-addr1
                        name: node1
                        nodeid: 1
                        ring2_addr: node1-addr2
                    }

                    node {
                        ring1_addr: node2-addr1
                        ring0_addr: node2-addr0
                        name: node2
                        nodeid: 2
                        ring2_addr: node2-addr2
                    }
                }
            """
            ),
        )

    def test_options_no_linknumber(self):
        self._assert_add(
            {"node1": "node1-addr2", "node2": "node2-addr2"},
            {
                "link_priority": "10",
                "mcastport": "5405",
                "ping_interval": "100",
                "ping_precision": "10",
                "ping_timeout": "20",
                "pong_count": "5",
                "transport": "sctp",
            },
            self.before,
            dedent(
                """\
                totem {
                    transport: knet

                    interface {
                        linknumber: 1
                        knet_transport: udp
                    }

                    interface {
                        knet_link_priority: 10
                        knet_ping_interval: 100
                        knet_ping_precision: 10
                        knet_ping_timeout: 20
                        knet_pong_count: 5
                        knet_transport: sctp
                        linknumber: 2
                        mcastport: 5405
                    }
                }

                nodelist {
                    node {
                        ring0_addr: node1-addr0
                        ring1_addr: node1-addr1
                        name: node1
                        nodeid: 1
                        ring2_addr: node1-addr2
                    }

                    node {
                        ring1_addr: node2-addr1
                        ring0_addr: node2-addr0
                        name: node2
                        nodeid: 2
                        ring2_addr: node2-addr2
                    }
                }
            """
            ),
        )

    def test_custom_link_number_no_options(self):
        self._assert_add(
            {"node1": "node1-addr2", "node2": "node2-addr2"},
            {"linknumber": "4"},
            self.before,
            dedent(
                """\
                totem {
                    transport: knet

                    interface {
                        linknumber: 1
                        knet_transport: udp
                    }
                }

                nodelist {
                    node {
                        ring0_addr: node1-addr0
                        ring1_addr: node1-addr1
                        name: node1
                        nodeid: 1
                        ring4_addr: node1-addr2
                    }

                    node {
                        ring1_addr: node2-addr1
                        ring0_addr: node2-addr0
                        name: node2
                        nodeid: 2
                        ring4_addr: node2-addr2
                    }
                }
            """
            ),
        )

    def test_custom_link_number_options(self):
        self._assert_add(
            {"node1": "node1-addr2", "node2": "node2-addr2"},
            {"linknumber": "4", "transport": "sctp"},
            self.before,
            dedent(
                """\
                totem {
                    transport: knet

                    interface {
                        linknumber: 1
                        knet_transport: udp
                    }

                    interface {
                        knet_transport: sctp
                        linknumber: 4
                    }
                }

                nodelist {
                    node {
                        ring0_addr: node1-addr0
                        ring1_addr: node1-addr1
                        name: node1
                        nodeid: 1
                        ring4_addr: node1-addr2
                    }

                    node {
                        ring1_addr: node2-addr1
                        ring0_addr: node2-addr0
                        name: node2
                        nodeid: 2
                        ring4_addr: node2-addr2
                    }
                }
            """
            ),
        )

    def test_set_as_link_0_if_available(self):
        before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 1
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring2_addr: node1-addr2
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    ring2_addr: node2-addr2
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
                    linknumber: 1
                    knet_transport: udp
                }

                interface {
                    knet_transport: sctp
                    linknumber: 0
                }
            }

            nodelist {
                node {
                    ring2_addr: node1-addr2
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                    ring0_addr: node1-addr0
                }

                node {
                    ring1_addr: node2-addr1
                    ring2_addr: node2-addr2
                    name: node2
                    nodeid: 2
                    ring0_addr: node2-addr0
                }
            }
        """
        )
        self._assert_add(
            {"node1": "node1-addr0", "node2": "node2-addr0"},
            {"transport": "sctp"},
            before,
            after,
        )

    def test_set_as_first_available_link(self):
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
                    ring2_addr: node2-addr2
                    ring0_addr: node2-addr0
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
                    knet_transport: udp
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
                    ring2_addr: node2-addr2
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                    ring1_addr: node2-addr1
                }
            }
        """
        )
        self._assert_add(
            {"node1": "node1-addr1", "node2": "node2-addr1"}, {}, before, after
        )

    def test_no_linknumber_available(self):
        before = dedent(
            """\
            totem {
                transport: knet
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    ring2_addr: node1-addr2
                    ring3_addr: node1-addr3
                    ring4_addr: node1-addr4
                    ring5_addr: node1-addr5
                    ring6_addr: node1-addr6
                    ring7_addr: node1-addr7
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
                    ring2_addr: node2-addr2
                    ring3_addr: node2-addr3
                    ring4_addr: node2-addr4
                    ring5_addr: node2-addr5
                    ring6_addr: node2-addr6
                    ring7_addr: node2-addr7
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        with self.assertRaises(AssertionError) as cm:
            self._assert_add(
                {"node1": "node1-addr-new", "node2": "node2-addr-new"},
                {},
                before,
                "does not matter",
            )
        self.assertEqual(str(cm.exception), "No link number available")

    def test_more_sections(self):
        before = dedent(
            """\
            totem {
                interface {
                    linknumber: 1
                    knet_transport: udp
                }
            }

            totem {
                transport: knet
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }
            }

            nodelist {
                node {
                    ring1_addr: node2-addr1
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self._assert_add(
            {"node1": "node1-addr4", "node2": "node2-addr4"},
            {"linknumber": "4", "transport": "sctp"},
            before,
            dedent(
                """\
                totem {
                    interface {
                        linknumber: 1
                        knet_transport: udp
                    }
                }

                totem {
                    transport: knet

                    interface {
                        knet_transport: sctp
                        linknumber: 4
                    }
                }

                nodelist {
                    node {
                        ring0_addr: node1-addr0
                        ring1_addr: node1-addr1
                        name: node1
                        nodeid: 1
                        ring4_addr: node1-addr4
                    }
                }

                nodelist {
                    node {
                        ring1_addr: node2-addr1
                        ring0_addr: node2-addr0
                        name: node2
                        nodeid: 2
                        ring4_addr: node2-addr4
                    }
                }
            """
            ),
        )


class RemoveLinks(TestCase):
    @staticmethod
    def assert_remove(links, before, after):
        facade = _get_facade(before)
        facade.remove_links(links)
        ac(after, facade.config.export())

    def test_nonexistent_links(self):
        config = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
                }

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
                    ring2_addr: node2-addr2
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self.assert_remove(["1"], config, config)

    def test_link_without_options(self):
        before = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
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
            }
        """
        )
        self.assert_remove(["1"], before, after)

    def test_link_with_options(self):
        before = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        after = dedent(
            """\
            nodelist {
                node {
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self.assert_remove(["0"], before, after)

    def test_link_without_addrs(self):
        before = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        after = dedent(
            """\
            nodelist {
                node {
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self.assert_remove(["0"], before, after)

    def test_more_links(self):
        before = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    ring2_addr: node1-addr2
                    name: node1
                    nodeid: 1
                }

                node {
                    ring2_addr: node2-addr2
                    ring1_addr: node2-addr1
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        after = dedent(
            """\
            nodelist {
                node {
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self.assert_remove(["0", "2"], before, after)

    def test_more_occurrences(self):
        before = dedent(
            """\
            totem {
                interface {
                    linknumber: 1
                    knet_transport: udp
                }

                interface {
                    linknumber: 2
                    knet_transport: sctp
                }

                interface {
                    linknumber: 1
                    knet_ping_interval: 100
                }
            }

            totem {
                interface {
                    linknumber: 1
                    knet_link_priority: 3
                }

                interface {
                    linknumber: 2
                    knet_link_priority: 5
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    ring1_addr: node1-addr1a
                    ring2_addr: node1-addr2
                    name: node1
                    nodeid: 1
                }

                node {
                    ring2_addr: node2-addr2
                    ring1_addr: node2-addr1
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }

            nodelist {
                node {
                    ring1_addr: node2-addr1b
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                interface {
                    linknumber: 2
                    knet_transport: sctp
                }
            }

            totem {
                interface {
                    linknumber: 2
                    knet_link_priority: 5
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
                    ring2_addr: node2-addr2
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }

            nodelist {
                node {
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self.assert_remove(["1"], before, after)

    def test_link_with_options_nonumbered(self):
        before = dedent(
            """\
            totem {
                interface {
                    knet_transport: udp
                }

                interface {
                    linknumber: 1
                    knet_transport: sctp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                interface {
                    linknumber: 1
                    knet_transport: sctp
                }
            }

            nodelist {
                node {
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self.assert_remove(["0"], before, after)

    def test_more_linknumbers(self):
        before = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
                    linknumber: 1
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
                    linknumber: 1
                }
            }

            nodelist {
                node {
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self.assert_remove(["0"], before, after)


class UpdateLink(TestCase):
    def _assert_update(self, before, after, linknumber, options, node_addr_map):
        facade = _get_facade(before)
        facade.update_link(linknumber, node_addr_map, options)
        ac(after, facade.config.export())
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_changes(self):
        config = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 1
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self._assert_update(config, config, "1", {}, {})

    def test_wrong_linknumber(self):
        before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 1
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
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
                    linknumber: 1
                    knet_transport: udp
                }

                interface {
                    linknumber: 2
                    knet_transport: sctp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                    ring2_addr: new-addr
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self._assert_update(
            before, after, "2", {"transport": "sctp"}, {"node1": "new-addr"}
        )

    def test_do_not_allow_linknumber_change(self):
        before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 1
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
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
                    linknumber: 1
                    knet_transport: sctp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: new-addr
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self._assert_update(
            before,
            after,
            "1",
            {"linknumber": "2", "transport": "sctp"},
            {"node1": "new-addr"},
        )

    def test_addresses(self):
        before = dedent(
            """\
            totem {
                transport: knet
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
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
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: new-addr
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
        """
        )
        self._assert_update(
            before, after, "1", {}, {"node1": "new-addr", "nodeX": "addrX"}
        )

    def test_addresses_more_sections(self):
        before = dedent(
            """\
            totem {
                transport: knet
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    ring0_addr: node1-addr0a
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0b
                    name: node1
                    nodeid: 1
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                transport: knet
            }

            nodelist {
                node {
                    ring0_addr: new-addr
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }

            nodelist {
                node {
                    ring0_addr: new-addr
                    name: node1
                    nodeid: 1
                }
            }
        """
        )
        self._assert_update(before, after, "0", {}, {"node1": "new-addr"})

    def test_options(self):
        before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 0
                    knet_transport: sctp
                }

                interface {
                    linknumber: 1
                    knet_transport: udp
                    mcastport: 1234
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 0
                    knet_transport: sctp
                }

                interface {
                    linknumber: 1
                    knet_transport: sctp
                    knet_pong_count: 10
                }
            }
        """
        )
        self._assert_update(
            before,
            after,
            "1",
            {"transport": "sctp", "mcastport": "", "pong_count": "10"},
            {},
        )

    def test_options_more_interface_sections(self):
        before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 1
                    knet_transport: udp
                    mcastport: 1234
                }

                interface {
                    linknumber: 0
                    knet_transport: sctp
                }

                interface {
                    linknumber: 1
                    mcastport: 2345
                }
            }

            totem {
                interface {
                    linknumber: 1
                    mcastport: 3456
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 1
                    knet_transport: udp
                }

                interface {
                    linknumber: 0
                    knet_transport: sctp
                }
            }

            totem {
                interface {
                    linknumber: 1
                    mcastport: 9876
                }
            }
        """
        )
        self._assert_update(before, after, "1", {"mcastport": "9876"}, {})

    def test_remove_all_options_removes_linknumber_and_section(self):
        before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 0
                    knet_transport: udp
                }

                interface {
                    linknumber: 1
                    knet_transport: udp
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 1
                    knet_transport: udp
                }
            }
        """
        )
        self._assert_update(before, after, "0", {"transport": ""}, {})

    def test_create_interface_section(self):
        before = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 0
                    knet_transport: udp
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                transport: knet

                interface {
                    linknumber: 0
                    knet_transport: udp
                }

                interface {
                    linknumber: 1
                    knet_transport: sctp
                }
            }
        """
        )
        self._assert_update(before, after, "1", {"transport": "sctp"}, {})

    def test_enable_broadcast(self):
        before = dedent(
            """\
            totem {
                transport: udp

                interface {
                    mcastport: 1234
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                transport: udp

                interface {
                    mcastport: 1234
                    broadcast: yes
                }
            }
        """
        )
        self._assert_update(before, after, "0", {"broadcast": "1"}, {})

    def test_disable_broadcast(self):
        before = dedent(
            """\
            totem {
                transport: udp

                interface {
                    mcastport: 1234
                    broadcast: yes
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                transport: udp

                interface {
                    mcastport: 1234
                }
            }
        """
        )
        self._assert_update(before, after, "0", {"broadcast": "0"}, {})

    def test_default_broadcast(self):
        before = dedent(
            """\
            totem {
                transport: udp

                interface {
                    mcastport: 1234
                    broadcast: yes
                }
            }
        """
        )
        after = dedent(
            """\
            totem {
                transport: udp

                interface {
                    mcastport: 1234
                }
            }
        """
        )
        self._assert_update(before, after, "0", {"broadcast": ""}, {})
