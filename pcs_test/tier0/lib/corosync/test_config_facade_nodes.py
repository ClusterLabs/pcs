from textwrap import dedent
from unittest import TestCase

import pcs.lib.corosync.config_facade as lib
from pcs.common.corosync_conf import CorosyncNodeAddressType
from pcs.lib.corosync.config_parser import Parser

from pcs_test.tools.assertions import ac


def _get_facade(config_text):
    return lib.ConfigFacade(Parser.parse(config_text.encode("utf-8")))


class GetNodesTest(TestCase):
    def assert_equal_nodelist(self, expected, real):
        real_nodes = [
            {
                "name": node.name,
                "id": node.nodeid,
                "addrs": [(addr.link, addr.addr) for addr in node.addrs],
            }
            for node in real
        ]
        self.assertEqual(expected, real_nodes)

    def nodes_from_config(self, config):
        facade = _get_facade(config)
        nodes = facade.get_nodes()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        return nodes

    def test_no_nodelist(self):
        config = ""
        nodes = self.nodes_from_config(config)
        self.assertEqual(0, len(nodes))

    def test_empty_nodelist(self):
        config = dedent(
            """\
            nodelist {
            }
        """
        )
        nodes = self.nodes_from_config(config)
        self.assertEqual(0, len(nodes))

    def test_one_nodelist(self):
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: n1a
                    nodeid: 1
                    name: n1n
                }
                node {
                    ring0_addr: n2a
                    ring1_addr: n2b
                    name: n2n
                    nodeid: 2
                }
            }
        """
        )
        nodes = self.nodes_from_config(config)
        self.assert_equal_nodelist(
            [
                {"id": "1", "name": "n1n", "addrs": [("0", "n1a")]},
                {
                    "id": "2",
                    "name": "n2n",
                    "addrs": [("0", "n2a"), ("1", "n2b")],
                },
            ],
            nodes,
        )

    def test_more_nodelists(self):
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: n1a
                    nodeid: 1
                    name: n1n
                }
            }
            nodelist {
                node {
                    ring0_addr: n2a
                    ring1_addr: n2b
                    name: n2n
                    nodeid: 2
                }
            }
        """
        )
        nodes = self.nodes_from_config(config)
        self.assert_equal_nodelist(
            [
                {"id": "1", "name": "n1n", "addrs": [("0", "n1a")]},
                {
                    "id": "2",
                    "name": "n2n",
                    "addrs": [("0", "n2a"), ("1", "n2b")],
                },
            ],
            nodes,
        )

    def test_missing_values(self):
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: n1a
                    nodeid: 1
                }
                node {
                    ring0_addr: n2a
                    name: n2n
                }
                node {
                    nodeid: 3
                    name: n3n
                }
                node {
                }
                node {
                    ring1_addr: n4b
                    nodeid: 4
                    name: n4n
                }
                node {
                    ring1_addr: n5b
                    ring2_addr: 
                    ring3_addr: n5d
                    nodeid: 5
                    name: n5n
                }
            }
        """
        )
        nodes = self.nodes_from_config(config)
        self.assert_equal_nodelist(
            [
                {"id": "1", "name": None, "addrs": [("0", "n1a")]},
                {"id": None, "name": "n2n", "addrs": [("0", "n2a")]},
                {"id": "3", "name": "n3n", "addrs": []},
                {"id": "4", "name": "n4n", "addrs": [("1", "n4b")]},
                {
                    "id": "5",
                    "name": "n5n",
                    "addrs": [("1", "n5b"), ("3", "n5d")],
                },
            ],
            nodes,
        )
        self.assertEqual(["n1a"], nodes[0].addrs_plain())
        self.assertEqual(["n2a"], nodes[1].addrs_plain())
        self.assertEqual([], nodes[2].addrs_plain())
        self.assertEqual(["n4b"], nodes[3].addrs_plain())
        self.assertEqual(["n5b", "n5d"], nodes[4].addrs_plain())

    def test_sort_rings(self):
        config = dedent(
            """\
            nodelist {
                node {
                    ring3_addr: n1d
                    ring0_addr: n1a
                    ring1_addr: n1b
                    nodeid: 1
                    name: n1n
                }
            }
        """
        )
        nodes = self.nodes_from_config(config)
        self.assert_equal_nodelist(
            [
                {
                    "id": "1",
                    "name": "n1n",
                    "addrs": [("0", "n1a"), ("1", "n1b"), ("3", "n1d")],
                },
            ],
            nodes,
        )

    def test_addr_type(self):
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: 10.0.0.1
                    ring1_addr: node1b
                    nodeid: 1
                    name: n1n
                }
                node {
                    ring0_addr: node2a
                    ring1_addr: ::192:168:123:42
                    name: n2n
                    nodeid: 2
                }
            }
        """
        )
        nodes = self.nodes_from_config(config)
        self.assertEqual(nodes[0].addrs[0].type, CorosyncNodeAddressType.IPV4)
        self.assertEqual(nodes[0].addrs[1].type, CorosyncNodeAddressType.FQDN)
        self.assertEqual(nodes[1].addrs[0].type, CorosyncNodeAddressType.FQDN)
        self.assertEqual(nodes[1].addrs[1].type, CorosyncNodeAddressType.IPV6)


class AddNodesTest(TestCase):
    def test_adding_two_nodes(self):
        # pylint: disable=no-self-use
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    ring1_addr: node1-addr2
                    nodeid: 1
                    name: node1
                }
            }
        """
        )
        facade = _get_facade(config)
        facade.add_nodes(
            [
                dict(
                    name="node3",
                    addrs=["node3-addr1", "node3-addr2"],
                ),
                dict(
                    name="node2",
                    addrs=["node2-addr1", "node2-addr2"],
                ),
            ]
        )

        expected_config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    ring1_addr: node1-addr2
                    nodeid: 1
                    name: node1
                }

                node {
                    ring0_addr: node3-addr1
                    ring1_addr: node3-addr2
                    name: node3
                    nodeid: 2
                }

                node {
                    ring0_addr: node2-addr1
                    ring1_addr: node2-addr2
                    name: node2
                    nodeid: 3
                }
            }
        """
        )
        ac(expected_config, facade.config.export())

    def test_skipped_and_out_of_order_links_and_nodes_ids(self):
        # pylint: disable=no-self-use
        config = dedent(
            """\
            nodelist {
                node {
                    ring1_addr: node1-addr1
                    ring5_addr: node1-addr5
                    ring2_addr: node1-addr2
                    nodeid: 1
                    name: node1
                }

                node {
                    ring1_addr: node4-addr1
                    ring5_addr: node4-addr5
                    ring2_addr: node4-addr2
                    nodeid: 4
                    name: node4
                }

                node {
                    ring1_addr: node2-addr1
                    ring5_addr: node2-addr5
                    ring2_addr: node2-addr2
                    nodeid: 2
                    name: node2
                }
            }
        """
        )
        facade = _get_facade(config)
        facade.add_nodes(
            [
                dict(
                    name="node6",
                    addrs=["node6-addr1", "node6-addr2", "node6-addr5"],
                ),
                dict(
                    name="node3",
                    addrs=["node3-addr1", "node3-addr2", "node3-addr5"],
                ),
                dict(
                    name="node5",
                    addrs=["node5-addr1", "node5-addr2", "node5-addr5"],
                ),
            ]
        )

        expected_config = dedent(
            """\
            nodelist {
                node {
                    ring1_addr: node1-addr1
                    ring5_addr: node1-addr5
                    ring2_addr: node1-addr2
                    nodeid: 1
                    name: node1
                }

                node {
                    ring1_addr: node4-addr1
                    ring5_addr: node4-addr5
                    ring2_addr: node4-addr2
                    nodeid: 4
                    name: node4
                }

                node {
                    ring1_addr: node2-addr1
                    ring5_addr: node2-addr5
                    ring2_addr: node2-addr2
                    nodeid: 2
                    name: node2
                }

                node {
                    ring1_addr: node6-addr1
                    ring2_addr: node6-addr2
                    ring5_addr: node6-addr5
                    name: node6
                    nodeid: 3
                }

                node {
                    ring1_addr: node3-addr1
                    ring2_addr: node3-addr2
                    ring5_addr: node3-addr5
                    name: node3
                    nodeid: 5
                }

                node {
                    ring1_addr: node5-addr1
                    ring2_addr: node5-addr2
                    ring5_addr: node5-addr5
                    name: node5
                    nodeid: 6
                }
            }
        """
        )
        ac(expected_config, facade.config.export())

    def test_enable_two_node(self):
        # pylint: disable=no-self-use
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }
            }

            quorum {
                provider: corosync_votequorum
            }
        """
        )
        facade = _get_facade(config)
        facade.add_nodes(
            [
                dict(name="node2", addrs=["node2-addr1"]),
            ]
        )
        expected_config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }

            quorum {
                provider: corosync_votequorum
                two_node: 1
            }
        """
        )
        ac(expected_config, facade.config.export())

    def test_disable_two_node(self):
        # pylint: disable=no-self-use
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }

            quorum {
                provider: corosync_votequorum
                two_node: 1
            }
        """
        )
        facade = _get_facade(config)
        facade.add_nodes(
            [
                dict(name="node3", addrs=["node3-addr1"]),
            ]
        )
        expected_config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }

                node {
                    ring0_addr: node3-addr1
                    name: node3
                    nodeid: 3
                }
            }

            quorum {
                provider: corosync_votequorum
            }
        """
        )
        ac(expected_config, facade.config.export())


class RemoveNodes(TestCase):
    def test_remove(self):
        # pylint: disable=no-self-use
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }

                node {
                    ring0_addr: node3-addr1
                    name: node3
                    nodeid: 3
                }

                node {
                    ring0_addr: node5-addr1
                    name: node5
                    nodeid: 5
                }
            }

            nodelist {
                node {
                    ring0_addr: node3-addr1
                    ring1_addr: node3-addr2
                    name: node3
                    nodeid: 3
                }

                node {
                    ring0_addr: node4-addr1
                    ring1_addr: node4-addr2
                    name: node4
                    nodeid: 4
                }
            }

            quorum {
                provider: corosync_votequorum
            }
        """
        )
        facade = _get_facade(config)
        facade.remove_nodes(["node3", "node4", "nodeX"])
        expected_config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }

                node {
                    ring0_addr: node5-addr1
                    name: node5
                    nodeid: 5
                }
            }

            quorum {
                provider: corosync_votequorum
            }
        """
        )
        ac(expected_config, facade.config.export())

    def test_enable_two_nodes(self):
        # pylint: disable=no-self-use
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }

                node {
                    ring0_addr: node3-addr1
                    name: node3
                    nodeid: 3
                }
            }

            quorum {
                provider: corosync_votequorum
            }
        """
        )
        facade = _get_facade(config)
        facade.remove_nodes(["node3"])
        expected_config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }

            quorum {
                provider: corosync_votequorum
                two_node: 1
            }
        """
        )
        ac(expected_config, facade.config.export())

    def test_disable_two_nodes(self):
        # pylint: disable=no-self-use
        config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }

            quorum {
                provider: corosync_votequorum
                two_node: 1
            }
        """
        )
        facade = _get_facade(config)
        facade.remove_nodes(["node2"])
        expected_config = dedent(
            """\
            nodelist {
                node {
                    ring0_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }
            }

            quorum {
                provider: corosync_votequorum
            }
        """
        )
        ac(expected_config, facade.config.export())
