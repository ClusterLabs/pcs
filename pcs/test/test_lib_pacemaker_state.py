from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from lxml import etree

from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.xml import get_xml_manipulation_creator_from_file

from pcs.lib.pacemaker_state import (
    ClusterState,
    _Attrs,
    _Children,
)

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severities

class AttrsTest(TestCase):
    def test_get_declared_attr(self):
        attrs = _Attrs('test', {'node-name': 'node1'}, {'name': 'node-name'})
        self.assertEqual('node1', attrs.name)

    def test_raises_on_undeclared_attribute(self):
        attrs = _Attrs('test', {'node-name': 'node1'}, {})
        self.assertRaises(AttributeError, lambda: attrs.name)

    def test_raises_on_missing_required_attribute(self):
        attrs = _Attrs('test', {}, {'name': 'node-name'})
        self.assertRaises(AttributeError, lambda: attrs.name)

    def test_attr_transformation_success(self):
        attrs = _Attrs('test', {'number': '7'}, {'count': ('number', int)})
        self.assertEqual(7, attrs.count)

    def test_attr_transformation_fail(self):
        attrs = _Attrs('test', {'number': 'abc'}, {'count': ('number', int)})
        self.assertRaises(ValueError, lambda: attrs.count)

class ChildrenTest(TestCase):
    def setUp(self):
        self.dom = etree.fromstring(
            '<main><some name="0"/><any name="1"/><any name="2"/></main>'
        )

    def wrap(self, element):
        return '{0}.{1}'.format(element.tag, element.attrib['name'])

    def test_get_declared_section(self):
        children = _Children(
            'test', self.dom, {}, {'some_section': ('some', self.wrap)}
        )
        self.assertEqual('some.0', children.some_section)

    def test_get_declared_children(self):
        children = _Children('test', self.dom, {'anys': ('any', self.wrap)}, {})
        self.assertEqual(['any.1', 'any.2'], children.anys)

    def test_raises_on_undeclared_children(self):
        children = _Children('test', self.dom, {}, {})
        self.assertRaises(AttributeError, lambda: children.some_section)


class TestBase(TestCase):
    def setUp(self):
        self.create_covered_status = get_xml_manipulation_creator_from_file(
            rc('crm_mon.minimal.xml')
        )
        self.covered_status = self.create_covered_status()

class ClusterStatusTest(TestBase):
    def test_minimal_crm_mon_is_valid(self):
        ClusterState(str(self.covered_status))

    def test_refuse_invalid_xml(self):
        assert_raise_library_error(
            lambda: ClusterState('invalid xml'),
            (severities.ERROR, report_codes.BAD_CLUSTER_STATE_FORMAT, {})
        )

    def test_refuse_invalid_document(self):
        self.covered_status.append_to_first_tag_name(
            'nodes',
            '<node without="required attributes" />'
        )

        assert_raise_library_error(
            lambda: ClusterState(str(self.covered_status)),
            (severities.ERROR, report_codes.BAD_CLUSTER_STATE_FORMAT, {})
        )


class WorkWithClusterStatusNodesTest(TestBase):
    def fixture_node_string(self, **kwargs):
        attrs = dict(name='name', id='id', type='member')
        attrs.update(kwargs)
        return '''<node
            name="{name}"
            id="{id}"
            online="true"
            standby="true"
            standby_onfail="false"
            maintenance="false"
            pending="false"
            unclean="false"
            shutdown="false"
            expected_up="false"
            is_dc="false"
            resources_running="0"
            type="{type}"
        />'''.format(**attrs)

    def test_can_get_node_names(self):
        self.covered_status.append_to_first_tag_name(
            'nodes',
            self.fixture_node_string(name='node1', id='1'),
            self.fixture_node_string(name='node2', id='2'),
        )
        xml = str(self.covered_status)
        self.assertEqual(
            ['node1', 'node2'],
            [node.attrs.name for node in ClusterState(xml).node_section.nodes]
        )

    def test_can_filter_out_remote_nodes(self):
        self.covered_status.append_to_first_tag_name(
            'nodes',
            self.fixture_node_string(name='node1', id='1'),
            self.fixture_node_string(name='node2', type='remote', id='2'),
        )
        xml = str(self.covered_status)
        self.assertEqual(
            ['node1'],
            [
                node.attrs.name
                for node in ClusterState(xml).node_section.nodes
                if node.attrs.type != 'remote'
            ]
        )


class WorkWithClusterStatusSummaryTest(TestBase):
    def test_nodes_count(self):
        xml = str(self.covered_status)
        self.assertEqual(0, ClusterState(xml).summary.nodes.attrs.count)

    def test_resources_count(self):
        xml = str(self.covered_status)
        self.assertEqual(0, ClusterState(xml).summary.resources.attrs.count)
