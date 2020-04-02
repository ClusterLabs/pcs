import shutil
from unittest import TestCase

from lxml import etree

from pcs_test.tools.assertions import ac
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.pcs_runner import (
    pcs,
    PcsRunner,
)

# pylint: disable=invalid-name, no-self-use, bad-whitespace, line-too-long

empty_cib = rc("cib-empty.xml")
temp_cib = rc("temp-cib.xml")


class PropertyTest(TestCase):
    def setUp(self):
        shutil.copy(empty_cib, temp_cib)

    def testEmpty(self):
        output, returnVal = pcs(temp_cib, "property")
        assert returnVal == 0, "Unable to list resources"
        assert output == "Cluster Properties:\n", [output]

    def testDefaults(self):
        output, returnVal = pcs(temp_cib, "property --defaults")
        prop_defaults = output
        assert returnVal == 0, "Unable to list resources"
        assert output.startswith("Cluster Properties:\n batch-limit")

        output, returnVal = pcs(temp_cib, "property --all")
        assert returnVal == 0, "Unable to list resources"
        assert output.startswith("Cluster Properties:\n batch-limit")
        ac(output, prop_defaults)

        output, returnVal = pcs(temp_cib, "property set blahblah=blah")
        assert returnVal == 1
        assert (
            output
            == "Error: unknown cluster property: 'blahblah', (use --force to override)\n"
        ), [output]

        output, returnVal = pcs(temp_cib, "property set blahblah=blah --force")
        assert returnVal == 0, output
        assert output == "", output

        output, returnVal = pcs(temp_cib, "property set stonith-enabled=false")
        assert returnVal == 0, output
        assert output == "", output

        output, returnVal = pcs(temp_cib, "property")
        assert returnVal == 0
        assert (
            output
            == "Cluster Properties:\n blahblah: blah\n stonith-enabled: false\n"
        ), [output]

        output, returnVal = pcs(temp_cib, "property --defaults")
        assert returnVal == 0, "Unable to list resources"
        assert output.startswith("Cluster Properties:\n batch-limit")
        ac(output, prop_defaults)

        output, returnVal = pcs(temp_cib, "property --all")
        assert returnVal == 0, "Unable to list resources"
        assert "blahblah: blah" in output
        assert "stonith-enabled: false" in output
        assert output.startswith("Cluster Properties:\n batch-limit")

    def testBadProperties(self):
        o, r = pcs(temp_cib, "property set xxxx=zzzz")
        self.assertEqual(r, 1)
        ac(
            o,
            "Error: unknown cluster property: 'xxxx', (use --force to override)\n",
        )
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

        o, r = pcs(temp_cib, "property unset zzzzz")
        self.assertEqual(r, 1)
        ac(o, "Error: can't remove property: 'zzzzz' that doesn't exist\n")
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

        o, r = pcs(temp_cib, "property unset zzzz --force")
        self.assertEqual(r, 0)
        ac(o, "")
        o, _ = pcs(temp_cib, "property list")
        ac(o, "Cluster Properties:\n")

    def test_set_property_validation_enum(self):
        output, returnVal = pcs(
            temp_cib, "property set no-quorum-policy=freeze"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 no-quorum-policy: freeze
""",
        )

        output, returnVal = pcs(
            temp_cib, "property set no-quorum-policy=freeze --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 no-quorum-policy: freeze
""",
        )

        output, returnVal = pcs(
            temp_cib, "property set no-quorum-policy=not_valid_value"
        )
        ac(
            output,
            "Error: invalid value of property: "
            "'no-quorum-policy=not_valid_value', (use --force to override)\n",
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 no-quorum-policy: freeze
""",
        )

        output, returnVal = pcs(
            temp_cib, "property set no-quorum-policy=not_valid_value --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 no-quorum-policy: not_valid_value
""",
        )

    def test_set_property_validation_boolean(self):
        output, returnVal = pcs(temp_cib, "property set enable-acl=TRUE")
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 enable-acl: TRUE
""",
        )

        output, returnVal = pcs(temp_cib, "property set enable-acl=no")
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 enable-acl: no
""",
        )

        output, returnVal = pcs(
            temp_cib, "property set enable-acl=TRUE --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 enable-acl: TRUE
""",
        )

        output, returnVal = pcs(
            temp_cib, "property set enable-acl=not_valid_value"
        )
        ac(
            output,
            "Error: invalid value of property: "
            "'enable-acl=not_valid_value', (use --force to override)\n",
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 enable-acl: TRUE
""",
        )

        output, returnVal = pcs(
            temp_cib, "property set enable-acl=not_valid_value --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 enable-acl: not_valid_value
""",
        )

    def test_set_property_validation_integer(self):
        output, returnVal = pcs(temp_cib, "property set migration-limit=0")
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 migration-limit: 0
""",
        )

        output, returnVal = pcs(temp_cib, "property set migration-limit=-10")
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 migration-limit: -10
""",
        )

        output, returnVal = pcs(
            temp_cib, "property set migration-limit=0 --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 migration-limit: 0
""",
        )

        output, returnVal = pcs(temp_cib, "property set migration-limit=0.1")
        ac(
            output,
            "Error: invalid value of property: "
            "'migration-limit=0.1', (use --force to override)\n",
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 migration-limit: 0
""",
        )

        output, returnVal = pcs(
            temp_cib, "property set migration-limit=0.1 --force"
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(temp_cib, "property list")
        ac(
            o,
            """Cluster Properties:
 migration-limit: 0.1
""",
        )


class PropertyUnset(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//crm_config")[0]
        )
    ),
):
    def setUp(self):
        self.empty_cib = empty_cib
        self.temp_cib = temp_cib
        shutil.copy(self.empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib)

    @staticmethod
    def fixture_xml_no_props():
        # must match empty_cib
        return """
            <crm_config />
        """

    @staticmethod
    def fixture_xml_empty_props():
        # must match empty_cib
        return """
            <crm_config>
                <cluster_property_set id="cib-bootstrap-options" />
            </crm_config>
        """

    @staticmethod
    def fixture_xml_with_props():
        # must match empty_cib
        return """
            <crm_config>
                <cluster_property_set id="cib-bootstrap-options">
                    <nvpair id="cib-bootstrap-options-batch-limit"
                        name="batch-limit" value="100"
                    />
                </cluster_property_set>
            </crm_config>
        """

    def test_keep_empty_nvset(self):
        self.assert_effect(
            "property set batch-limit=100", self.fixture_xml_with_props()
        )
        self.assert_effect(
            "property unset batch-limit", self.fixture_xml_empty_props()
        )

    def test_dont_create_nvset_on_removal(self):
        # pcs mimics crm_attribute. So this behaves differently than the rest
        # of pcs - instead of doing nothing it returns an error.
        # Should be changed to be consistent with the rest of pcs.
        self.assert_pcs_fail(
            "property unset batch-limit",
            "Error: can't remove property: 'batch-limit' that doesn't exist\n",
        )
