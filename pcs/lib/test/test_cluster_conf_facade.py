from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.misc import outdent

from lxml import etree

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity

from pcs.lib import cluster_conf_facade as lib

class FromStringTest(TestCase):
    def test_success(self):
        facade = lib.ClusterConfFacade.from_string("<cluster/>")
        self.assertTrue(isinstance(facade, lib.ClusterConfFacade))
        assert_xml_equal("<cluster/>", etree.tostring(facade._config).decode())

    def test_syntax_error(self):
        assert_raise_library_error(
            lambda: lib.ClusterConfFacade.from_string("<cluster>"),
            (
                severity.ERROR,
                report_codes.CLUSTER_CONF_LOAD_ERROR_INVALID_FORMAT,
                {}
            )
        )

    def test_invalid_document_error(self):
        assert_raise_library_error(
            lambda: lib.ClusterConfFacade.from_string("string"),
            (
                severity.ERROR,
                report_codes.CLUSTER_CONF_LOAD_ERROR_INVALID_FORMAT,
                {}
            )
        )


class GetClusterNameTest(TestCase):
    def test_success(self):
        cfg = etree.XML('<cluster name="cluster-name"/>')
        self.assertEqual(
            "cluster-name",
            lib.ClusterConfFacade(cfg).get_cluster_name()
        )

    def test_no_name(self):
        cfg = etree.XML('<cluster/>')
        self.assertEqual("", lib.ClusterConfFacade(cfg).get_cluster_name())

    def test_not_cluster_element(self):
        cfg = etree.XML('<not_cluster/>')
        self.assertEqual("", lib.ClusterConfFacade(cfg).get_cluster_name())


class GetNodesTest(TestCase):
    def assert_equal_nodelist(self, expected_nodes, real_nodelist):
        real_nodes = [
            {"ring0": n.ring0, "ring1": n.ring1, "name": n.name, "id": n.id}
            for n in real_nodelist
        ]
        self.assertEqual(expected_nodes, real_nodes)

    def test_success(self):
        config = outdent("""
            <cluster>
                <clusternodes>
                    <clusternode name="node1" nodeid="1">
                        <altname name="node1-altname"/>
                    </clusternode>
                    <clusternode name="node2" nodeid="2"/>
                    <clusternode name="node3" nodeid="3"/>
                </clusternodes>
            </cluster>
        """)
        self.assert_equal_nodelist(
            [
                {
                    "ring0": "node1",
                    "ring1": "node1-altname",
                    "name": None,
                    "id": "1",
                },
                {
                    "ring0": "node2",
                    "ring1": None,
                    "name": None,
                    "id": "2",
                },
                {
                    "ring0": "node3",
                    "ring1": None,
                    "name": None,
                    "id": "3",
                }
            ],
            lib.ClusterConfFacade(etree.XML(config)).get_nodes()
        )

    def test_no_nodes(self):
        config = "<cluster/>"
        self.assert_equal_nodelist(
            [], lib.ClusterConfFacade(etree.XML(config)).get_nodes()
        )

    def test_missing_info(self):
        config = outdent("""
            <cluster>
                <clusternodes>
                    <clusternode nodeid="1"/>
                    <clusternode name="node2">
                        <altname/>
                    </clusternode>
                    <clusternode/>
                </clusternodes>
            </cluster>
        """)
        self.assert_equal_nodelist(
            [
                {
                    "ring0": None,
                    "ring1": None,
                    "name": None,
                    "id": "1",
                },
                {
                    "ring0": "node2",
                    "ring1": None,
                    "name": None,
                    "id": None,
                },
                {
                    "ring0": None,
                    "ring1": None,
                    "name": None,
                    "id": None,
                }
            ],
            lib.ClusterConfFacade(etree.XML(config)).get_nodes()
        )
