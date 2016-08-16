from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil
from pcs.test.tools import pcs_unittest as unittest

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

empty_cib = rc("cib-empty.xml")
temp_cib = rc("temp-cib.xml")

class PropertyTest(unittest.TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def testEmpty(self):
        output, returnVal = pcs(temp_cib, "property")
        assert returnVal == 0, 'Unable to list resources'
        assert output == "Cluster Properties:\n", [output]

    def testDefaults(self):
        output, returnVal = pcs(temp_cib, "property --defaults")
        prop_defaults = output
        assert returnVal == 0, 'Unable to list resources'
        assert output.startswith('Cluster Properties:\n batch-limit')

        output, returnVal = pcs(temp_cib, "property --all")
        assert returnVal == 0, 'Unable to list resources'
        assert output.startswith('Cluster Properties:\n batch-limit')
        ac(output,prop_defaults)

        output, returnVal = pcs(temp_cib, "property set blahblah=blah")
        assert returnVal == 1
        assert output == "Error: unknown cluster property: 'blahblah', (use --force to override)\n",[output]

        output, returnVal = pcs(temp_cib, "property set blahblah=blah --force")
        assert returnVal == 0,output
        assert output == "",output

        output, returnVal = pcs(temp_cib, "property set stonith-enabled=false")
        assert returnVal == 0,output
        assert output == "",output

        output, returnVal = pcs(temp_cib, "property")
        assert returnVal == 0
        assert output == "Cluster Properties:\n blahblah: blah\n stonith-enabled: false\n", [output]

        output, returnVal = pcs(temp_cib, "property --defaults")
        assert returnVal == 0, 'Unable to list resources'
        assert output.startswith('Cluster Properties:\n batch-limit')
        ac(output,prop_defaults)

        output, returnVal = pcs(temp_cib, "property --all")
        assert returnVal == 0, 'Unable to list resources'
        assert "blahblah: blah" in output
        assert "stonith-enabled: false" in output
        assert output.startswith('Cluster Properties:\n batch-limit')

    def testBadProperties(self):
        o,r = pcs(temp_cib, "property set xxxx=zzzz")
        self.assertEqual(r, 1)
        ac(o,"Error: unknown cluster property: 'xxxx', (use --force to override)\n")
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

        output, returnVal = pcs(temp_cib, "property set =5678 --force")
        ac(output, "Error: empty property name: '=5678'\n")
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

        output, returnVal = pcs(temp_cib, "property set =5678")
        ac(output, "Error: empty property name: '=5678'\n")
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

        output, returnVal = pcs(temp_cib, "property set bad_format")
        ac(output, "Error: invalid property format: 'bad_format'\n")
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

        output, returnVal = pcs(temp_cib, "property set bad_format --force")
        ac(output, "Error: invalid property format: 'bad_format'\n")
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

        o,r = pcs(temp_cib, "property unset zzzzz")
        self.assertEqual(r, 1)
        ac(o,"Error: can't remove property: 'zzzzz' that doesn't exist\n")
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

        o,r = pcs(temp_cib, "property unset zzzz --force")
        self.assertEqual(r, 0)
        ac(o,"")
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

    def test_set_property_validation_enum(self):
        output, returnVal = pcs(
            temp_cib, "property set no-quorum-policy=freeze"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 no-quorum-policy: freeze
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set no-quorum-policy=freeze --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 no-quorum-policy: freeze
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set no-quorum-policy=not_valid_value"
        )
        ac(
            output,
            "Error: invalid value of property: "
            "'no-quorum-policy=not_valid_value', (use --force to override)\n"
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 no-quorum-policy: freeze
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set no-quorum-policy=not_valid_value --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 no-quorum-policy: not_valid_value
"""
        )

    def test_set_property_validation_boolean(self):
        output, returnVal = pcs(temp_cib, "property set enable-acl=TRUE")
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 enable-acl: TRUE
"""
        )

        output, returnVal = pcs(temp_cib, "property set enable-acl=no")
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 enable-acl: no
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set enable-acl=TRUE --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 enable-acl: TRUE
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set enable-acl=not_valid_value"
        )
        ac(
            output,
            "Error: invalid value of property: "
            "'enable-acl=not_valid_value', (use --force to override)\n"
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 enable-acl: TRUE
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set enable-acl=not_valid_value --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 enable-acl: not_valid_value
"""
        )

    def test_set_property_validation_integer(self):
        output, returnVal = pcs(
            temp_cib, "property set default-resource-stickiness=0"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 default-resource-stickiness: 0
"""
        )


        output, returnVal = pcs(
            temp_cib, "property set default-resource-stickiness=-10"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 default-resource-stickiness: -10
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set default-resource-stickiness=0 --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 default-resource-stickiness: 0
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set default-resource-stickiness=0.1"
        )
        ac(
            output,
            "Error: invalid value of property: "
            "'default-resource-stickiness=0.1', (use --force to override)\n"
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 default-resource-stickiness: 0
"""
        )

        output, returnVal = pcs(
            temp_cib, "property set default-resource-stickiness=0.1 --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(o, """Cluster Properties:
 default-resource-stickiness: 0.1
"""
        )


class NodePropertyTestBase(unittest.TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)
        self.pcs_runner = PcsRunner(temp_cib)

    def fixture_nodes(self, nodes, attrs=None):
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

class NodePropertyShowTest(NodePropertyTestBase):
    def test_empty(self):
        self.fixture_nodes(["rh7-1", "rh7-2"])
        self.assert_pcs_success(
            "property",
            "Cluster Properties:\n"
        )

    def test_nonempty(self):
        self.fixture_nodes(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "property",
            """\
Cluster Properties:
Node Attributes:
 rh7-1: IP=192.168.1.1
 rh7-2: IP=192.168.1.2
"""
        )

    def test_multiple_per_node(self):
        self.fixture_nodes(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", "alias": "node1", },
                "rh7-2": {"IP": "192.168.1.2", "alias": "node2", },
            }
        )
        self.assert_pcs_success(
            "property",
            """\
Cluster Properties:
Node Attributes:
 rh7-1: IP=192.168.1.1 alias=node1
 rh7-2: IP=192.168.1.2 alias=node2
"""
        )

    def test_name_filter_not_exists(self):
        self.fixture_nodes(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "property show alias",
            """\
Cluster Properties:
"""
        )

    def test_name_filter_exists(self):
        self.fixture_nodes(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", "alias": "node1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "property show alias",
            """\
Cluster Properties:
Node Attributes:
 rh7-1: alias=node1
"""
        )

class NodePropertySetTest(NodePropertyTestBase):
    def test_set_new(self):
        self.fixture_nodes(["rh7-1", "rh7-2"])
        self.assert_pcs_success(
            "property set --node=rh7-1 IP=192.168.1.1"
        )
        self.assert_pcs_success(
            "property",
            """\
Cluster Properties:
Node Attributes:
 rh7-1: IP=192.168.1.1
"""
        )
        self.assert_pcs_success(
            "property set --node=rh7-2 IP=192.168.1.2"
        )
        self.assert_pcs_success(
            "property",
            """\
Cluster Properties:
Node Attributes:
 rh7-1: IP=192.168.1.1
 rh7-2: IP=192.168.1.2
"""
        )

    def test_set_existing(self):
        self.fixture_nodes(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "property set --node=rh7-2 IP=192.168.2.2"
        )
        self.assert_pcs_success(
            "property",
            """\
Cluster Properties:
Node Attributes:
 rh7-1: IP=192.168.1.1
 rh7-2: IP=192.168.2.2
"""
        )

    def test_unset(self):
        self.fixture_nodes(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "property set --node=rh7-2 IP="
        )
        self.assert_pcs_success(
            "property",
            """\
Cluster Properties:
Node Attributes:
 rh7-1: IP=192.168.1.1
"""
        )

    def test_unset_nonexisting(self):
        self.fixture_nodes(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_result(
            "property unset --node=rh7-1 missing",
            "Error: attribute: 'missing' doesn't exist for node: 'rh7-1'\n",
            returncode=2
        )

    def test_unset_nonexisting_forced(self):
        self.fixture_nodes(
            ["rh7-1", "rh7-2"],
            {
                "rh7-1": {"IP": "192.168.1.1", },
                "rh7-2": {"IP": "192.168.1.2", },
            }
        )
        self.assert_pcs_success(
            "property unset --node=rh7-1 missing --force",
            ""
        )
