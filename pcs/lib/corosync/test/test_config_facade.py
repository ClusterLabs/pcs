import re
from textwrap import dedent
from unittest import TestCase

from pcs.test.tools import fixture
from pcs.test.tools.assertions import (
    ac,
    assert_raise_library_error,
)
from pcs.test.tools.misc import get_test_resource as rc, outdent

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity

import pcs.lib.corosync.config_facade as lib


class FromStringTest(TestCase):
    def test_success(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(facade.__class__, lib.ConfigFacade)
        self.assertEqual(facade.config.export(), config)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_parse_error_missing_brace(self):
        config = "section {"
        assert_raise_library_error(
            lambda: lib.ConfigFacade.from_string(config),
            (
                severity.ERROR,
                report_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
                {}
            )
        )

    def test_parse_error_unexpected_brace(self):
        config = "}"
        assert_raise_library_error(
            lambda: lib.ConfigFacade.from_string(config),
            (
                severity.ERROR,
                report_codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE,
                {}
            )
        )


class GetClusterNameTest(TestCase):
    def test_no_name(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_name(self):
        config = "totem {\n cluster_name:\n}\n"
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_one_name(self):
        config = "totem {\n cluster_name: test\n}\n"
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("test", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_names(self):
        config = "totem {\n cluster_name: test\n cluster_name: TEST\n}\n"
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("TEST", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_sections(self):
        config = "totem{\ncluster_name:test\n}\ntotem{\ncluster_name:TEST\n}\n"
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual("TEST", facade.get_cluster_name())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


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
        facade = lib.ConfigFacade.from_string(config)
        nodes = facade.get_nodes()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        return nodes

    def test_no_nodelist(self):
        config = ""
        nodes = self.nodes_from_config(config)
        self.assertEqual(0, len(nodes))

    def test_empty_nodelist(self):
        config = outdent("""\
            nodelist {
            }
        """)
        nodes = self.nodes_from_config(config)
        self.assertEqual(0, len(nodes))

    def test_one_nodelist(self):
        config = outdent("""\
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
        """)
        nodes = self.nodes_from_config(config)
        self.assert_equal_nodelist(
            [
                {"id": "1", "name": "n1n", "addrs": [(0, "n1a")]},
                {"id": "2", "name": "n2n", "addrs": [(0, "n2a"), (1, "n2b")]}
            ],
            nodes
        )

    def test_more_nodelists(self):
        config = outdent("""\
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
        """)
        nodes = self.nodes_from_config(config)
        self.assert_equal_nodelist(
            [
                {"id": "1", "name": "n1n", "addrs": [(0, "n1a")]},
                {"id": "2", "name": "n2n", "addrs": [(0, "n2a"), (1, "n2b")]}
            ],
            nodes
        )

    def test_missing_values(self):
        config = outdent("""\
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
        """)
        nodes = self.nodes_from_config(config)
        self.assert_equal_nodelist(
            [
                {"id": "1", "name": None, "addrs": [(0, "n1a")]},
                {"id": None, "name": "n2n", "addrs": [(0, "n2a")]},
                {"id": "3", "name": "n3n", "addrs": []},
                {"id": "4", "name": "n4n", "addrs": [(1, "n4b")]},
                {"id": "5", "name": "n5n", "addrs": [(1, "n5b"), (3, "n5d")]},
            ],
            nodes
        )
        self.assertEqual(["n1a"], nodes[0].addrs_plain)
        self.assertEqual(["n2a"], nodes[1].addrs_plain)
        self.assertEqual([], nodes[2].addrs_plain)
        self.assertEqual(["n4b"], nodes[3].addrs_plain)
        self.assertEqual(["n5b", "n5d"], nodes[4].addrs_plain)

    def test_sort_rings(self):
        config = outdent("""\
            nodelist {
                node {
                    ring3_addr: n1d
                    ring0_addr: n1a
                    ring1_addr: n1b
                    nodeid: 1
                    name: n1n
                }
            }
        """)
        nodes = self.nodes_from_config(config)
        self.assert_equal_nodelist(
            [
                {
                    "id": "1",
                    "name": "n1n",
                    "addrs": [(0, "n1a"), (1, "n1b"), (3, "n1d")]
                },
            ],
            nodes
        )

    def test_addr_type(self):
        config = outdent("""\
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
        """)
        nodes = self.nodes_from_config(config)
        self.assertEqual(nodes[0].addrs[0].type, "IPv4")
        self.assertEqual(nodes[0].addrs[1].type, "FQDN")
        self.assertEqual(nodes[1].addrs[0].type, "FQDN")
        self.assertEqual(nodes[1].addrs[1].type, "IPv6")


class GetNodesNames(TestCase):
    def test_no_nodelist(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        nodes_names = facade.get_nodes_names()
        self.assertEqual([], nodes_names)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_nodelist(self):
        config = outdent("""\
            nodelist {
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        nodes_names = facade.get_nodes_names()
        self.assertEqual([], nodes_names)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_one_nodelist(self):
        config = outdent("""\
            nodelist {
                node {
                    ring0_addr: n1a
                    name: n1n
                    nodeid: 1
                }

                node {
                    ring0_addr: n2a
                    ring1_addr: n2b
                    name: n2n
                    nodeid: 2
                }
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        nodes_names = facade.get_nodes_names()
        self.assertEqual(["n1n", "n2n"], nodes_names)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_nodelists(self):
        config = outdent("""\
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
        """)
        facade = lib.ConfigFacade.from_string(config)
        nodes_names = facade.get_nodes_names()
        self.assertEqual(["n1n", "n2n"], nodes_names)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_missing_name(self):
        config = outdent("""\
            nodelist {
                node {
                    ring0_addr: n1a
                    nodeid: 1
                }

                node {
                    ring0_addr: n2a
                    ring1_addr: n2b
                    name: n2n
                    nodeid: 2
                }
            }
        """)
        facade = lib.ConfigFacade.from_string(config)
        nodes_names = facade.get_nodes_names()
        self.assertEqual(["n2n"], nodes_names)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class AddNodesTest(TestCase):
    def test_adding_two_nodes(self):
        config = outdent("""\
        nodelist {
            node {
                ring0_addr: node1-addr1
                ring1_addr: node1-addr2
                nodeid: 1
                name: node1
            }
        }
        """)
        facade = lib.ConfigFacade.from_string(config)
        facade.add_nodes([
            dict(
                name="node3",
                addrs=["node3-addr1", "node3-addr2"],
            ),
            dict(
                name="node2",
                addrs=["node2-addr1", "node2-addr2"],
            ),
        ])

        expected_config = outdent("""\
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
        """)
        ac(expected_config, facade.config.export())

    def test_skipped_and_out_of_order_links_and_nodes_ids(self):
        config = outdent("""\
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
        """)
        facade = lib.ConfigFacade.from_string(config)
        facade.add_nodes([
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
        ])

        expected_config = outdent("""\
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
        """)
        ac(expected_config, facade.config.export())

    def test_enable_two_node(self):
        config = outdent("""\
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
        """)
        facade = lib.ConfigFacade.from_string(config)
        facade.add_nodes([
            dict(name="node2", addrs=["node2-addr1"]),
        ])
        expected_config = outdent("""\
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
        """)
        ac(expected_config, facade.config.export())

    def test_disable_two_node(self):
        config = outdent("""\
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
        """)
        facade = lib.ConfigFacade.from_string(config)
        facade.add_nodes([
            dict(name="node3", addrs=["node3-addr1"]),
        ])
        expected_config = outdent("""\
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
        """)
        ac(expected_config, facade.config.export())


class GetQuorumOptionsTest(TestCase):
    def test_no_quorum(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_quorum(self):
        config = """\
quorum {
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_options(self):
        config = """\
quorum {
    provider: corosync_votequorum
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual({}, options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_some_options(self):
        config = """\
quorum {
    provider: corosync_votequorum
    wait_for_all: 0
    nonsense: ignored
    auto_tie_breaker: 1
    last_man_standing: 0
    last_man_standing_window: 1000
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual(
            {
                "auto_tie_breaker": "1",
                "last_man_standing": "0",
                "last_man_standing_window": "1000",
                "wait_for_all": "0",
            },
            options
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_option_repeated(self):
        config = """\
quorum {
    wait_for_all: 0
    wait_for_all: 1
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual(
            {
                "wait_for_all": "1",
            },
            options
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_quorum_repeated(self):
        config = """\
quorum {
    wait_for_all: 0
    last_man_standing: 0
}
quorum {
    last_man_standing_window: 1000
    wait_for_all: 1
}
"""
        facade = lib.ConfigFacade.from_string(config)
        options = facade.get_quorum_options()
        self.assertEqual(
            {
                "last_man_standing": "0",
                "last_man_standing_window": "1000",
                "wait_for_all": "1",
            },
            options
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class IsEnabledAutoTieBreaker(TestCase):
    def test_enabled(self):
        config = """\
quorum {
    auto_tie_breaker: 1
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertTrue(facade.is_enabled_auto_tie_breaker())

    def test_disabled(self):
        config = """\
quorum {
    auto_tie_breaker: 0
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.is_enabled_auto_tie_breaker())

    def test_no_value(self):
        config = """\
quorum {
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.is_enabled_auto_tie_breaker())


class SetQuorumOptionsTest(TestCase):
    def get_two_node(self, facade):
        two_node = None
        for quorum in facade.config.get_sections("quorum"):
            for dummy_name, value in quorum.get_attributes("two_node"):
                two_node = value
        return two_node

    def test_add_missing_section(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options({"wait_for_all": "0"})
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            """\
quorum {
    wait_for_all: 0
}
""",
            facade.config.export()
        )

    def test_del_missing_section(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options({"wait_for_all": ""})
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual("", facade.config.export())

    def test_add_all_options(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        expected_options = {
            "auto_tie_breaker": "1",
            "last_man_standing": "0",
            "last_man_standing_window": "1000",
            "wait_for_all": "0",
        }
        facade.set_quorum_options(expected_options)

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        test_facade = lib.ConfigFacade.from_string(facade.config.export())
        self.assertEqual(
            expected_options,
            test_facade.get_quorum_options()
        )

    def test_complex(self):
        config = """\
quorum {
    wait_for_all: 0
    last_man_standing_window: 1000
}
quorum {
    wait_for_all: 0
    last_man_standing: 1
}
"""
        facade = lib.ConfigFacade.from_string(config)
        facade.set_quorum_options(
            {
                "auto_tie_breaker": "1",
                "wait_for_all": "1",
                "last_man_standing_window": "",
            }
        )

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        test_facade = lib.ConfigFacade.from_string(facade.config.export())
        self.assertEqual(
            {
                "auto_tie_breaker": "1",
                "last_man_standing": "1",
                "wait_for_all": "1",
            },
            test_facade.get_quorum_options()
        )

    def test_2nodes_atb_on(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(2, len(facade.get_nodes()))

        facade.set_quorum_options({"auto_tie_breaker": "1"})

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "1",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")

    def test_2nodes_atb_off(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(2, len(facade.get_nodes()))

        facade.set_quorum_options({"auto_tie_breaker": "0"})

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "0",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node == "1")

    def test_3nodes_atb_on(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(3, len(facade.get_nodes()))

        facade.set_quorum_options({"auto_tie_breaker": "1"})

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "1",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")

    def test_3nodes_atb_off(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(3, len(facade.get_nodes()))

        facade.set_quorum_options({"auto_tie_breaker": "0"})

        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "0",
            facade.get_quorum_options().get("auto_tie_breaker", None)
        )

        two_node = self.get_two_node(facade)
        self.assertTrue(two_node is None or two_node == "0")


class HasQuorumDeviceTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_device(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_device(self):
        config = """\
quorum {
    device {
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_device_set(self):
        config = """\
quorum {
    device {
        model: net
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertTrue(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_model(self):
        config = """\
quorum {
    device {
        option: value
        net {
            host: 127.0.0.1
        }
    }
}
"""
        facade = lib.ConfigFacade.from_string(config)
        self.assertFalse(facade.has_quorum_device())
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class GetQuorumDeviceModel(TestCase):
    def assert_model(self, config, expected_model):
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            expected_model,
            facade.get_quorum_device_model()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_config(self):
        config = ""
        self.assert_model(config, None)

    def test_no_device(self):
        config = open(rc("corosync.conf")).read()
        self.assert_model(config, None)

    def test_empty_device(self):
        config = dedent("""\
            quorum {
                device {
                }
            }
            """
        )
        self.assert_model(config, None)

    def test_no_model(self):
        config = dedent("""\
            quorum {
                device {
                    option: value
                    net {
                        host: 127.0.0.1
                    }
                }
            }
            """
        )
        self.assert_model(config, None)

    def test_configured_properly(self):
        config = dedent("""\
            quorum {
                device {
                    option: value
                    model: net
                    net {
                        host: 127.0.0.1
                    }
                }
            }
            """
        )
        self.assert_model(config, "net")

    def test_more_devices_one_quorum(self):
        config = dedent("""\
            quorum {
                device {
                    option0: valueX
                    option1: value1
                    model: disk
                    net {
                        host: 127.0.0.1
                    }
                    heuristics {
                        mode: sync
                        exec_ls: test -f /tmp/test
                    }
                }
                device {
                    option0: valueY
                    option2: value2
                    model: net
                    disk {
                        path: /dev/quorum_disk
                    }
                    heuristics {
                        mode: on
                    }
                    heuristics {
                        timeout: 5
                    }
                }
            }
            """
        )
        self.assert_model(config, "net")

    def test_more_devices_more_quorum(self):
        config = dedent("""\
            quorum {
                device {
                    option0: valueX
                    option1: value1
                    model: disk
                    net {
                        host: 127.0.0.1
                    }
                    heuristics {
                        mode: sync
                        exec_ls: test -f /tmp/test
                    }
                }
            }
            quorum {
                device {
                    option0: valueY
                    option2: value2
                    model: net
                    disk {
                        path: /dev/quorum_disk
                    }
                    heuristics {
                        mode: on
                    }
                    heuristics {
                        timeout: 5
                    }
                }
            }
            """
        )
        self.assert_model(config, "net")


class GetQuorumDeviceSettingsTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_device(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_device(self):
        config = dedent("""\
            quorum {
                device {
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_model(self):
        config = dedent("""\
            quorum {
                device {
                    option: value
                    net {
                        host: 127.0.0.1
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (None, {}, {"option": "value"}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_configured_properly(self):
        config = dedent("""\
            quorum {
                device {
                    option: value
                    model: net
                    net {
                        host: 127.0.0.1
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            ("net", {"host": "127.0.0.1"}, {"option": "value"}, {}),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_configured_properly_heuristics(self):
        config = dedent("""\
            quorum {
                device {
                    option: value
                    model: net
                    net {
                        host: 127.0.0.1
                    }
                    heuristics {
                        mode: on
                        exec_ls: test -f /tmp/test
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (
                "net",
                {"host": "127.0.0.1"},
                {"option": "value"},
                {"exec_ls": "test -f /tmp/test", "mode": "on"}
            ),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_devices_one_quorum(self):
        config = dedent("""\
            quorum {
                device {
                    option0: valueX
                    option1: value1
                    model: disk
                    net {
                        host: 127.0.0.1
                    }
                    heuristics {
                        mode: sync
                        exec_ls: test -f /tmp/test
                    }
                }
                device {
                    option0: valueY
                    option2: value2
                    model: net
                    disk {
                        path: /dev/quorum_disk
                    }
                    heuristics {
                        mode: on
                    }
                    heuristics {
                        timeout: 5
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (
                "net",
                {"host": "127.0.0.1"},
                {"option0": "valueY", "option1": "value1", "option2": "value2"},
                {"exec_ls": "test -f /tmp/test", "mode": "on", "timeout": "5"}
            ),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_more_devices_more_quorum(self):
        config = dedent("""\
            quorum {
                device {
                    option0: valueX
                    option1: value1
                    model: disk
                    net {
                        host: 127.0.0.1
                    }
                    heuristics {
                        mode: sync
                        exec_ls: test -f /tmp/test
                    }
                }
            }
            quorum {
                device {
                    option0: valueY
                    option2: value2
                    model: net
                    disk {
                        path: /dev/quorum_disk
                    }
                    heuristics {
                        mode: on
                    }
                    heuristics {
                        timeout: 5
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            (
                "net",
                {"host": "127.0.0.1"},
                {"option0": "valueY", "option1": "value1", "option2": "value2"},
                {"exec_ls": "test -f /tmp/test", "mode": "on", "timeout": "5"}
            ),
            facade.get_quorum_device_settings()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class IsQuorumDeviceHeuristicsEnabledWithNoExec(TestCase):
    def assert_result(self, config, expected_result):
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(
            expected_result,
            facade.is_quorum_device_heuristics_enabled_with_no_exec()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_empty_config(self):
        config = ""
        self.assert_result(config, False)

    def test_no_device(self):
        config = open(rc("corosync.conf")).read()
        self.assert_result(config, False)

    def test_empty_heuristics(self):
        config = dedent("""\
            quorum {
                device {
                    heuristics {
                    }
                }
            }
            """
        )
        self.assert_result(config, False)

    def test_heuristics_off(self):
        config = dedent("""\
            quorum {
                device {
                    heuristics {
                        mode: off
                    }
                }
            }
            """
        )
        self.assert_result(config, False)

    def test_heuristics_on_no_exec(self):
        config = dedent("""\
            quorum {
                device {
                    heuristics {
                        mode: on
                    }
                }
            }
            """
        )
        self.assert_result(config, True)

    def test_heuristics_sync_no_exec(self):
        config = dedent("""\
            quorum {
                device {
                    heuristics {
                        mode: on
                        exec_ls:
                    }
                }
            }
            """
        )
        self.assert_result(config, True)

    def test_heuristics_on_with_exec(self):
        config = dedent("""\
            quorum {
                device {
                    heuristics {
                        mode: on
                        exec_ls: test -f /tmp/test
                    }
                }
            }
            """
        )
        self.assert_result(config, False)

    def test_heuristics_sync_with_exec(self):
        config = dedent("""\
            quorum {
                device {
                    heuristics {
                        mode: sync
                        exec_ls: test -f /tmp/test
                    }
                }
            }
            """
        )
        self.assert_result(config, False)

    def test_heuristics_unknown_no_exec(self):
        config = dedent("""\
            quorum {
                device {
                    heuristics {
                        mode: unknown
                    }
                }
            }
            """
        )
        self.assert_result(config, False)

    def test_heuristics_unknown_with_exec(self):
        config = dedent("""\
            quorum {
                device {
                    heuristics {
                        mode: unknown
                    }
                }
            }
            """
        )
        self.assert_result(config, False)


class AddQuorumDeviceTest(TestCase):
    def test_success_net_minimal_ffsplit(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net
        votes: 1

        net {
            algorithm: ffsplit
            host: 127.0.0.1
        }
    }"""
            ),
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_success_net_minimal_lms(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            "net",
            {"host": "127.0.0.1", "algorithm": "lms"},
            {},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net

        net {
            algorithm: lms
            host: 127.0.0.1
        }
    }"""
            ),
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_success_remove_nodes_votes(self):
        config = open(rc("corosync-3nodes.conf")).read()
        config_votes = config.replace("node {", "node {\nquorum_votes: 2")
        facade = lib.ConfigFacade.from_string(config_votes)
        facade.add_quorum_device(
            "net",
            {"host": "127.0.0.1", "algorithm": "lms"},
            {},
            {}
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum",
                """\
    provider: corosync_votequorum

    device {
        model: net

        net {
            algorithm: lms
            host: 127.0.0.1
        }
    }"""
            ),
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_success_net_full(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            "net",
            {
                "host": "127.0.0.1",
                "port": "4433",
                "algorithm": "ffsplit",
                "connect_timeout": "12345",
                "force_ip_version": "4",
                "tie_breaker": "lowest",
            },
            {
                "timeout": "23456",
                "sync_timeout": "34567"
            },
            {
                "mode": "on",
                "timeout": "5",
                "sync_timeout": "15",
                "interval": "30",
                "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                "exec_ls": "test -f /tmp/test",
            }
        )
        ac(
            config.replace(
                "    provider: corosync_votequorum\n",
                outdent("""\
                    provider: corosync_votequorum

                    device {
                        sync_timeout: 34567
                        timeout: 23456
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            connect_timeout: 12345
                            force_ip_version: 4
                            host: 127.0.0.1
                            port: 4433
                            tie_breaker: lowest
                        }

                        heuristics {
                            exec_ls: test -f /tmp/test
                            exec_ping: ping -q -c 1 "127.0.0.1"
                            interval: 30
                            mode: on
                            sync_timeout: 15
                            timeout: 5
                        }
                    }
                """)
            ),
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_remove_conflicting_options(self):
        config = open(rc("corosync.conf")).read()
        config = config.replace(
            "    two_node: 1\n",
            "\n".join([
                "    two_node: 1",
                "    auto_tie_breaker: 1",
                "    last_man_standing: 1",
                "    last_man_standing_window: 987",
                "    allow_downscale: 1",
                ""
            ])
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {},
            {}
        )
        ac(
            re.sub(
                re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
                """\
quorum {
    provider: corosync_votequorum

    device {
        model: net
        votes: 1

        net {
            algorithm: ffsplit
            host: 127.0.0.1
        }
    }
}""",
                config
            ),
            facade.config.export()
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_remove_old_configuration(self):
        config = dedent("""\
            quorum {
                provider: corosync_votequorum
                device {
                    option: value_old1
                    heuristics {
                        h_option: hvalue_old1
                    }
                }
            }
            quorum {
                provider: corosync_votequorum
                device {
                    option: value_old2
                    heuristics {
                        h_option: hvalue_old2
                    }
                }
            }
            """
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.add_quorum_device(
            "net",
            {"host": "127.0.0.1", "algorithm": "ffsplit"},
            {},
            {}
        )
        ac(
            dedent("""\
                quorum {
                    provider: corosync_votequorum
                }

                quorum {
                    provider: corosync_votequorum

                    device {
                        model: net
                        votes: 1

                        net {
                            algorithm: ffsplit
                            host: 127.0.0.1
                        }
                    }
                }
                """
            )
            ,
            facade.config.export()
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class UpdateQuorumDeviceTest(TestCase):
    def fixture_add_device(self, config, votes=None):
        with_device = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent("""\
                quorum {
                    provider: corosync_votequorum

                    device {
                        timeout: 12345
                        model: net

                        net {
                            host: 127.0.0.1
                            port: 4433
                        }
                    }
                }"""
            ),
            config
        )
        if votes:
            with_device = with_device.replace(
                "model: net",
                "model: net\n        votes: {0}".format(votes)
            )
        return with_device

    def fixture_add_device_with_heuristics(self, config, votes=None):
        with_device = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent("""\
                quorum {
                    provider: corosync_votequorum

                    device {
                        timeout: 12345
                        model: net

                        net {
                            host: 127.0.0.1
                            port: 4433
                        }

                        heuristics {
                            exec_ls: test -f /tmp/test
                            interval: 30
                            mode: on
                        }
                    }
                }"""
            ),
            config
        )
        if votes:
            with_device = with_device.replace(
                "model: net",
                "model: net\n        votes: {0}".format(votes)
            )
        return with_device

    def test_not_existing(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                {"host": "127.0.0.1"},
                {},
                {}
            ),
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_not_existing_add_heuristics(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            lambda: facade.update_quorum_device(
                {},
                {},
                {"mode": "on"}
            ),
            fixture.error(report_codes.QDEVICE_NOT_DEFINED)
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_success_model_options_net(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read(),
            votes="1"
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            {"host": "127.0.0.2", "port": "", "algorithm": "ffsplit"},
            {},
            {}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "host: 127.0.0.1\n            port: 4433",
                "host: 127.0.0.2\n            algorithm: ffsplit"
            ),
            facade.config.export()
        )

    def test_success_generic_options(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            {},
            {"timeout": "", "sync_timeout": "23456"},
            {}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "timeout: 12345\n        model: net",
                "model: net\n        sync_timeout: 23456",
            ),
            facade.config.export()
        )

    def test_success_all_options(self):
        config = self.fixture_add_device_with_heuristics(
            open(rc("corosync-3nodes.conf")).read()
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            {"port": "4444"},
            {"timeout": "23456"},
            {"interval": "35"}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config
                .replace("port: 4433", "port: 4444")
                .replace("timeout: 12345", "timeout: 23456")
                .replace("interval: 30", "interval: 35")
            ,
            facade.config.export()
        )

    def test_success_add_heuristics(self):
        config = self.fixture_add_device(
            open(rc("corosync-3nodes.conf")).read()
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            {},
            {},
            {"mode": "on", "exec_ls": "test -f /tmp/test", "interval": "30"}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            self.fixture_add_device_with_heuristics(
                open(rc("corosync-3nodes.conf")).read()
            ),
            facade.config.export()
        )

    def test_success_remove_heuristics(self):
        config = self.fixture_add_device_with_heuristics(
            open(rc("corosync-3nodes.conf")).read()
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            {},
            {},
            {"mode": "", "exec_ls": "", "interval": ""}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            self.fixture_add_device(
                open(rc("corosync-3nodes.conf")).read()
            ),
            facade.config.export()
        )

    def test_success_change_heuristics(self):
        config = self.fixture_add_device_with_heuristics(
            open(rc("corosync-3nodes.conf")).read()
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.update_quorum_device(
            {},
            {},
            {"mode": "sync", "interval": "", "timeout": "20"}
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(
            config.replace(
                "interval: 30\n            mode: on",
                "mode: sync\n            timeout: 20",
            ),
            facade.config.export()
        )


class RemoveQuorumDeviceTest(TestCase):
    def test_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            facade.remove_quorum_device,
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_no_device(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            facade.remove_quorum_device,
            (
                severity.ERROR,
                report_codes.QDEVICE_NOT_DEFINED,
                {}
            )
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_remove_all_devices(self):
        config_no_devices = open(rc("corosync-3nodes.conf")).read()
        config = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            """\
quorum {
    provider: corosync_votequorum

    device {
        option: value
        model: net

        net {
            host: 127.0.0.1
            port: 4433
        }
    }

    device {
        option: value
    }
}

quorum {
    device {
        option: value
        model: disk

        net {
            host: 127.0.0.1
            port: 4433
        }
    }
}""",
            config_no_devices
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.remove_quorum_device()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(
            config_no_devices,
            facade.config.export()
        )

    def test_restore_two_node(self):
        config_no_devices = open(rc("corosync.conf")).read()
        config = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            """\
quorum {
    provider: corosync_votequorum

    device {
        option: value
        model: net

        net {
            host: 127.0.0.1
            port: 4433
        }
    }
}""",
            config_no_devices
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.remove_quorum_device()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        ac(
            config_no_devices,
            facade.config.export()
        )


class RemoveQuorumDeviceHeuristics(TestCase):
    def test_error_on_empty_config(self):
        config = ""
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            facade.remove_quorum_device_heuristics,
            fixture.error(report_codes.QDEVICE_NOT_DEFINED)
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_error_on_no_device(self):
        config = open(rc("corosync-3nodes.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        assert_raise_library_error(
            facade.remove_quorum_device_heuristics,
            fixture.error(report_codes.QDEVICE_NOT_DEFINED)
        )
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_noop_on_no_heuristics(self):
        config = open(rc("corosync-3nodes-qdevice.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        facade.remove_quorum_device_heuristics()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(config, facade.config.export())

    def test_remove_all_heuristics(self):
        config_no_devices = open(rc("corosync-3nodes.conf")).read()
        config_no_heuristics = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent("""\
                quorum {
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            host: 127.0.0.1
                        }
                    }

                    device {
                        option: value
                    }
                }

                quorum {
                    device {
                        model: net

                        net {
                            host: 127.0.0.2
                        }
                    }
                }"""
            ),
            config_no_devices
        )
        config_heuristics = re.sub(
            re.compile(r"quorum {[^}]*}", re.MULTILINE | re.DOTALL),
            dedent("""\
                quorum {
                    provider: corosync_votequorum

                    device {
                        model: net

                        net {
                            host: 127.0.0.1
                        }

                        heuristics {
                            mode: on
                        }
                    }

                    device {
                        option: value

                        heuristics {
                            interval: 3000
                        }
                    }
                }

                quorum {
                    device {
                        model: net

                        net {
                            host: 127.0.0.2
                        }

                        heuristics {
                            exec_ls: test -f /tmp/test
                        }
                    }
                }"""
            ),
            config_no_devices
        )

        facade = lib.ConfigFacade.from_string(config_heuristics)
        facade.remove_quorum_device_heuristics()
        self.assertFalse(facade.need_stopped_cluster)
        self.assertTrue(facade.need_qdevice_reload)
        ac(config_no_heuristics, facade.config.export())
