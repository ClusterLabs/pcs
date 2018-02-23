import shutil
from unittest import mock, TestCase

from pcs import node
from pcs.test.tools.assertions import (
    ac,
    AssertPcsMixin,
)
from pcs.test.tools.misc import (
    get_test_resource as rc,
    outdent,
)
from pcs.test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

from pcs import utils

empty_cib = rc("cib-empty-withnodes.xml")
temp_cib = rc("temp-cib.xml")

class NodeTest(TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def test_node_utilization_set(self):
        output, returnVal = pcs(temp_cib, "node utilization rh7-1 test1=10")
        ac("", output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "node utilization rh7-2")
        expected_out = """\
Node Utilization:
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "node utilization rh7-1")
        expected_out = """\
Node Utilization:
 rh7-1: test1=10
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "node utilization rh7-1 test1=-10 test4=1234"
        )
        ac("", output)
        self.assertEqual(0, returnVal)
        output, returnVal = pcs(temp_cib, "node utilization rh7-1")
        expected_out = """\
Node Utilization:
 rh7-1: test1=-10 test4=1234
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "node utilization rh7-2 test2=321 empty="
        )
        ac("", output)
        self.assertEqual(0, returnVal)
        output, returnVal = pcs(temp_cib, "node utilization rh7-2")
        expected_out = """\
Node Utilization:
 rh7-2: test2=321
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "node utilization")
        expected_out = """\
Node Utilization:
 rh7-1: test1=-10 test4=1234
 rh7-2: test2=321
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib, "node utilization rh7-2 test1=-20"
        )
        ac("", output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(temp_cib, "node utilization --name test1")
        expected_out = """\
Node Utilization:
 rh7-1: test1=-10
 rh7-2: test1=-20
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

        output, returnVal = pcs(
            temp_cib,
            "node utilization --name test1 rh7-2"
        )
        expected_out = """\
Node Utilization:
 rh7-2: test1=-20
"""
        ac(expected_out, output)
        self.assertEqual(0, returnVal)

    def test_node_utilization_set_invalid(self):
        output, returnVal = pcs(temp_cib, "node utilization rh7-1 test")
        expected_out = """\
Error: missing value of 'test' option
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "node utilization rh7-1 =10")
        expected_out = """\
Error: missing key in '=10' option
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(temp_cib, "node utilization rh7-0 test=10")
        expected_out = """\
Error: Unable to find a node: rh7-0
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)

        output, returnVal = pcs(
            temp_cib, "node utilization rh7-1 test1=10 test=int"
        )
        expected_out = """\
Error: Value of utilization attribute must be integer: 'test=int'
"""
        ac(expected_out, output)
        self.assertEqual(1, returnVal)


class NodeStandby(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(rc("cib-empty-with3nodes.xml"), temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def fixture_standby_all(self):
        self.assert_pcs_success(
            "node standby --all"
        )
        self.assert_standby_all()

    def assert_standby_none(self):
        self.assert_pcs_success(
            "node attribute",
            "Node Attributes:\n"
        )

    def assert_standby_all(self):
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-1: standby=on
                 rh7-2: standby=on
                 rh7-3: standby=on
                """
            )
        )

    def test_local_node(self):
        self.assert_standby_none()
        self.assert_pcs_fail(
            "node standby",
            "Error: Node(s) must be specified if -f is used\n"
        )
        self.assert_standby_none()

        self.fixture_standby_all()
        self.assert_pcs_fail(
            "node unstandby",
            "Error: Node(s) must be specified if -f is used\n"
        )
        self.assert_standby_all()

    def test_one_bad_node(self):
        self.assert_standby_none()
        self.assert_pcs_fail(
            "node standby nonexistant-node",
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
        )
        self.assert_standby_none()

        self.fixture_standby_all()
        self.assert_pcs_fail(
            "node unstandby nonexistant-node",
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
        )
        self.assert_standby_all()

    def test_bad_node_cancels_all_changes(self):
        self.assert_standby_none()
        self.assert_pcs_fail(
            "node standby rh7-1 nonexistant-node and-another rh7-2",
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n"
        )
        self.assert_standby_none()

        self.fixture_standby_all()
        self.assert_pcs_fail(
            "node standby rh7-1 nonexistant-node and-another rh7-2",
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n"
        )
        self.assert_standby_all()

    def test_all_nodes(self):
        self.assert_standby_none()
        self.assert_pcs_success(
            "node standby --all"
        )
        self.fixture_standby_all()

        self.assert_pcs_success(
            "node unstandby --all"
        )
        self.assert_standby_none()

    def test_one_node_with_repeat(self):
        self.assert_standby_none()
        self.assert_pcs_success(
            "node standby rh7-1"
        )
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-1: standby=on
                """
            )
        )
        self.assert_pcs_success(
            "node standby rh7-1"
        )

        self.fixture_standby_all()
        self.assert_pcs_success(
            "node unstandby rh7-1"
        )
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-2: standby=on
                 rh7-3: standby=on
                """
            )
        )
        self.assert_pcs_success(
            "node unstandby rh7-1"
        )

    def test_more_nodes(self):
        self.assert_standby_none()
        self.assert_pcs_success(
            "node standby rh7-1 rh7-2"
        )
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-1: standby=on
                 rh7-2: standby=on
                """
            )
        )

        self.fixture_standby_all()
        self.assert_pcs_success(
            "node unstandby rh7-1 rh7-2"
        )
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-3: standby=on
                """
            )
        )

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "node standby rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )
        self.assert_pcs_fail(
            "node unstandby rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )


class NodeMaintenance(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(rc("cib-empty-with3nodes.xml"), temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def fixture_maintenance_all(self):
        self.assert_pcs_success(
            "node maintenance --all"
        )
        self.assert_maintenance_all()

    def assert_maintenance_none(self):
        self.assert_pcs_success(
            "node attribute",
            "Node Attributes:\n"
        )

    def assert_maintenance_all(self):
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-1: maintenance=on
                 rh7-2: maintenance=on
                 rh7-3: maintenance=on
                """
            )
        )

    def test_local_node(self):
        self.assert_maintenance_none()
        self.assert_pcs_fail(
            "node maintenance",
            "Error: Node(s) must be specified if -f is used\n"
        )
        self.assert_maintenance_none()

        self.fixture_maintenance_all()
        self.assert_pcs_fail(
            "node unmaintenance",
            "Error: Node(s) must be specified if -f is used\n"
        )
        self.assert_maintenance_all()

    def test_one_bad_node(self):
        self.assert_maintenance_none()
        self.assert_pcs_fail(
            "node maintenance nonexistant-node",
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
        )
        self.assert_maintenance_none()

        self.fixture_maintenance_all()
        self.assert_pcs_fail(
            "node unmaintenance nonexistant-node",
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
        )
        self.assert_maintenance_all()

    def test_bad_node_cancels_all_changes(self):
        self.assert_maintenance_none()
        self.assert_pcs_fail(
            "node maintenance rh7-1 nonexistant-node and-another rh7-2",
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n"
        )
        self.assert_maintenance_none()

        self.fixture_maintenance_all()
        self.assert_pcs_fail(
            "node maintenance rh7-1 nonexistant-node and-another rh7-2",
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n"
        )
        self.assert_maintenance_all()

    def test_all_nodes(self):
        self.assert_maintenance_none()
        self.assert_pcs_success(
            "node maintenance --all"
        )
        self.fixture_maintenance_all()

        self.assert_pcs_success(
            "node unmaintenance --all"
        )
        self.assert_maintenance_none()

    def test_one_node_with_repeat(self):
        self.assert_maintenance_none()
        self.assert_pcs_success(
            "node maintenance rh7-1"
        )
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-1: maintenance=on
                """
            )
        )
        self.assert_pcs_success(
            "node maintenance rh7-1"
        )

        self.fixture_maintenance_all()
        self.assert_pcs_success(
            "node unmaintenance rh7-1"
        )
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-2: maintenance=on
                 rh7-3: maintenance=on
                """
            )
        )
        self.assert_pcs_success(
            "node unmaintenance rh7-1"
        )

    def test_more_nodes(self):
        self.assert_maintenance_none()
        self.assert_pcs_success(
            "node maintenance rh7-1 rh7-2"
        )
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-1: maintenance=on
                 rh7-2: maintenance=on
                """
            )
        )

        self.fixture_maintenance_all()
        self.assert_pcs_success(
            "node unmaintenance rh7-1 rh7-2"
        )
        self.assert_pcs_success(
            "node attribute",
            outdent(
                """\
                Node Attributes:
                 rh7-3: maintenance=on
                """
            )
        )

    def test_all_and_nodelist(self):
        self.assert_pcs_fail(
            "node maintenance rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )
        self.assert_pcs_fail(
            "node unmaintenance rh7-1 rh7-2 --all",
            stdout_full="Error: Cannot specify both --all and a list of nodes.\n"
        )


class NodeAttributeTest(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def fixture_attrs(self, nodes, attrs=None):
        attrs = dict() if attrs is None else attrs
        xml_lines = ['<nodes>']
        for node_id, node_name in enumerate(nodes, 1):
            xml_lines.extend([
                '<node id="{0}" uname="{1}">'.format(node_id, node_name),
                '<instance_attributes id="nodes-{0}">'.format(node_id),
            ])
            nv = '<nvpair id="nodes-{id}-{name}" name="{name}" value="{val}"/>'
            for name, value in attrs.get(node_name, dict()).items():
                xml_lines.append(nv.format(id=node_id, name=name, val=value))
            xml_lines.extend([
                '</instance_attributes>',
                '</node>'
            ])
        xml_lines.append('</nodes>')

        utils_usefile_original = utils.usefile
        utils_filename_original = utils.filename
        utils.usefile = True
        utils.filename = temp_cib
        output, retval = utils.run([
            "cibadmin", "--modify", '--xml-text', "\n".join(xml_lines)
        ])
        utils.usefile = utils_usefile_original
        utils.filename = utils_filename_original
        assert output == ""
        assert retval == 0

    def test_show_empty(self):
        self.fixture_attrs(["rh7-1", "rh7-2"])
        self.assert_pcs_success(
            "node attribute",
            "Node Attributes:\n"
        )

    def test_show_nonempty(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "node attribute",
            """\
Node Attributes:
 rh7-1: IP=192.168.1.1
 rh7-2: IP=192.168.1.2
"""
        )

    def test_show_multiple_per_node(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", "alias": "node1", },
                "rh7-2": {"IP": "192.168.1.2", "alias": "node2", },
            }
        )
        self.assert_pcs_success(
            "node attribute",
            """\
Node Attributes:
 rh7-1: IP=192.168.1.1 alias=node1
 rh7-2: IP=192.168.1.2 alias=node2
"""
        )

    def test_show_one_node(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", "alias": "node1", },
                "rh7-2": {"IP": "192.168.1.2", "alias": "node2", },
            }
        )
        self.assert_pcs_success(
            "node attribute rh7-1",
            """\
Node Attributes:
 rh7-1: IP=192.168.1.1 alias=node1
"""
        )

    def test_show_missing_node(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", "alias": "node1", },
                "rh7-2": {"IP": "192.168.1.2", "alias": "node2", },
            }
        )
        self.assert_pcs_success(
            "node attribute rh7-3",
            """\
Node Attributes:
"""
        )

    def test_show_name(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", "alias": "node1", },
                "rh7-2": {"IP": "192.168.1.2", "alias": "node2", },
            }
        )
        self.assert_pcs_success(
            "node attribute --name alias",
            """\
Node Attributes:
 rh7-1: alias=node1
 rh7-2: alias=node2
"""
        )

    def test_show_missing_name(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", "alias": "node1", },
                "rh7-2": {"IP": "192.168.1.2", "alias": "node2", },
            }
        )
        self.assert_pcs_success(
            "node attribute --name missing",
            """\
Node Attributes:
"""
        )

    def test_show_node_and_name(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", "alias": "node1", },
                "rh7-2": {"IP": "192.168.1.2", "alias": "node2", },
            }
        )
        self.assert_pcs_success(
            "node attribute --name alias rh7-1",
            """\
Node Attributes:
 rh7-1: alias=node1
"""
        )

    def test_set_new(self):
        self.fixture_attrs(["rh7-1", "rh7-2"])
        self.assert_pcs_success(
            "node attribute rh7-1 IP=192.168.1.1"
        )
        self.assert_pcs_success(
            "node attribute",
            """\
Node Attributes:
 rh7-1: IP=192.168.1.1
"""
        )
        self.assert_pcs_success(
            "node attribute rh7-2 IP=192.168.1.2"
        )
        self.assert_pcs_success(
            "node attribute",
            """\
Node Attributes:
 rh7-1: IP=192.168.1.1
 rh7-2: IP=192.168.1.2
"""
        )

    def test_set_existing(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "node attribute rh7-2 IP=192.168.2.2"
        )
        self.assert_pcs_success(
            "node attribute",
            """\
Node Attributes:
 rh7-1: IP=192.168.1.1
 rh7-2: IP=192.168.2.2
"""
        )

    def test_unset(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "node attribute rh7-2 IP="
        )
        self.assert_pcs_success(
            "node attribute",
            """\
Node Attributes:
 rh7-1: IP=192.168.1.1
"""
        )

    def test_unset_nonexisting(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_result(
            "node attribute rh7-1 missing=",
            "Error: attribute: 'missing' doesn't exist for node: 'rh7-1'\n",
            returncode=2
        )

    def test_unset_nonexisting_forced(self):
        self.fixture_attrs(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "node attribute rh7-1 missing= --force",
            ""
        )

class SetNodeUtilizationTest(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def test_refuse_non_option_attribute_parameter_among_options(self):
        self.assert_pcs_fail("node utilization rh7-1 net", [
            "Error: missing value of 'net' option",
        ])

    def test_refuse_option_without_key(self):
        self.assert_pcs_fail("node utilization rh7-1 =1", [
            "Error: missing key in '=1' option",
        ])

class PrintNodeUtilizationTest(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    @mock.patch("pcs.node.utils")
    def test_refuse_when_node_not_in_cib_and_is_not_remote(self, mock_utils):
        mock_cib = mock.MagicMock()
        mock_cib.getElementsByTagName = mock.Mock(return_value=[])

        mock_utils.get_cib_dom = mock.Mock(return_value=mock_cib)
        mock_utils.usefile = False
        mock_utils.getNodeAttributesFromPacemaker = mock.Mock(return_value=[])
        mock_utils.err = mock.Mock(side_effect=SystemExit)

        self.assertRaises(
            SystemExit,
            lambda: node.print_node_utilization("some")
        )

    def test_refuse_when_node_not_in_mocked_cib(self):
        self.assert_pcs_fail("node utilization some_nonexistent_node", [
            "Error: Unable to find a node: some_nonexistent_node",
        ])
