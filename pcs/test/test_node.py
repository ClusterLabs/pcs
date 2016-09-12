from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil
from pcs.test.tools import pcs_unittest as unittest
from pcs.test.tools.pcs_unittest import mock

from pcs import node
from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.misc import (
    ac,
    get_test_resource as rc,
)
from pcs.test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

from pcs import utils

empty_cib = rc("cib-empty-withnodes.xml")
temp_cib = rc("temp-cib.xml")

class NodeTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def test_node_maintenance(self):
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
"""
        ac(expected_out, output)
        output, returnVal = pcs(temp_cib, "node maintenance rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node maintenance rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node maintenance --all")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance rh7-2 rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node maintenance rh7-1 rh7-2")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(
            temp_cib, "node maintenance nonexistant-node and-another"
        )
        self.assertEqual(returnVal, 1)
        self.assertEqual(
            output,
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n"
        )
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-1: maintenance=on
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance rh7-1")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
Node Attributes:
 rh7-2: maintenance=on
"""
        ac(expected_out, output)

        output, returnVal = pcs(temp_cib, "node unmaintenance --all")
        ac("", output)
        self.assertEqual(returnVal, 0)
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
"""
        ac(expected_out, output)

        output, returnVal = pcs(
            temp_cib, "node unmaintenance nonexistant-node and-another"
        )
        self.assertEqual(returnVal, 1)
        self.assertEqual(
            output,
            "Error: Node 'nonexistant-node' does not appear to exist in configuration\n"
            "Error: Node 'and-another' does not appear to exist in configuration\n"
        )
        output, _ = pcs(temp_cib, "property")
        expected_out = """\
Cluster Properties:
"""
        ac(expected_out, output)

    def test_node_standby(self):
        output, returnVal = pcs(temp_cib, "node standby rh7-1")
        ac(output, "")
        self.assertEqual(returnVal, 0)

        # try to standby node which is already in standby mode
        output, returnVal = pcs(temp_cib, "node standby rh7-1")
        ac(output, "")
        self.assertEqual(returnVal, 0)

        output, returnVal = pcs(temp_cib, "node unstandby rh7-1")
        ac(output, "")
        self.assertEqual(returnVal, 0)

        # try to unstandby node which is no in standby mode
        output, returnVal = pcs(temp_cib, "node unstandby rh7-1")
        ac(output, "")
        self.assertEqual(returnVal, 0)

        output, returnVal = pcs(temp_cib, "node standby nonexistant-node")
        self.assertEqual(
            output,
            "Error: node 'nonexistant-node' does not appear to exist in configuration\n"
        )
        self.assertEqual(returnVal, 1)

        output, returnVal = pcs(temp_cib, "node unstandby nonexistant-node")
        self.assertEqual(
            output,
            "Error: node 'nonexistant-node' does not appear to exist in configuration\n"
        )
        self.assertEqual(returnVal, 1)


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


class NodeAttributeTest(unittest.TestCase, AssertPcsMixin):
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

        utils.usefile = True
        utils.filename = temp_cib
        output, retval = utils.run([
            "cibadmin", "--modify", '--xml-text', "\n".join(xml_lines)
        ])
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

class SetNodeUtilizationTest(unittest.TestCase, AssertPcsMixin):
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

class PrintNodeUtilizationTest(unittest.TestCase, AssertPcsMixin):
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
