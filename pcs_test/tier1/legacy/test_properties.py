from unittest import TestCase

from lxml import etree

from pcs.common.str_tools import format_list

from pcs_test.tier0.lib.commands.test_cluster_property import ALLOWED_PROPERTIES
from pcs_test.tools.assertions import ac
from pcs_test.tools.cib import (
    get_assert_pcs_effect_mixin_old as get_assert_pcs_effect_mixin,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunnerOld as PcsRunner
from pcs_test.tools.pcs_runner import pcs_old as pcs

# pylint: disable=invalid-name

empty_cib = rc("cib-empty.xml")


def get_invalid_option_messages(option_name, error=True):
    error_occurred = (
        "Error: Errors have occurred, therefore pcs is unable to continue\n"
    )
    use_force = ", use --force to override"
    return (
        "{severity}: invalid cluster property option '{option_name}', allowed "
        "options are: {allowed_properties}{use_force}\n"
        "{error_occurred}"
    ).format(
        severity="Error" if error else "Warning",
        option_name=option_name,
        allowed_properties=format_list(ALLOWED_PROPERTIES),
        use_force=use_force if error else "",
        error_occurred=error_occurred if error else "",
    )


class PropertyTest(TestCase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_properties")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def testEmpty(self):
        output, returnVal = pcs(self.temp_cib.name, ["property"])
        assert returnVal == 0, "Unable to list resources"
        assert output == "", [output]

    def testDefaults(self):
        output, returnVal = pcs(
            self.temp_cib.name, "property --defaults".split()
        )
        prop_defaults = output
        assert returnVal == 0, "Unable to list resources"
        assert output.startswith(
            "Deprecation Warning: Option --defaults is deprecated and will be "
            "removed. Please use command 'pcs property defaults' "
            "instead.\nbatch-limit=0"
        )

        output, returnVal = pcs(self.temp_cib.name, "property --all".split())
        assert returnVal == 0, "Unable to list resources"
        assert output.startswith("Cluster Properties:\n  batch-limit")

        output, returnVal = pcs(
            self.temp_cib.name, "property set blahblah=blah".split()
        )
        assert returnVal == 1
        assert output == get_invalid_option_messages("blahblah"), [output]

        output, returnVal = pcs(
            self.temp_cib.name, "property set blahblah=blah --force".split()
        )
        assert returnVal == 0, output
        assert output == get_invalid_option_messages(
            "blahblah", error=False
        ), output

        output, returnVal = pcs(
            self.temp_cib.name, "property set stonith-enabled=false".split()
        )
        assert returnVal == 0, output
        assert output == "", output

        output, returnVal = pcs(self.temp_cib.name, ["property"])
        assert returnVal == 0
        assert (
            output
            == "Cluster Properties: cib-bootstrap-options\n  blahblah=blah\n  stonith-enabled=false\n"
        ), [output]

        output, returnVal = pcs(
            self.temp_cib.name, "property --defaults".split()
        )
        assert returnVal == 0, "Unable to list resources"
        assert output.startswith(
            "Deprecation Warning: Option --defaults is deprecated and will be "
            "removed. Please use command 'pcs property defaults' "
            "instead.\nbatch-limit=0"
        )
        ac(output, prop_defaults)

        output, returnVal = pcs(self.temp_cib.name, "property --all".split())
        assert returnVal == 0, "Unable to list resources"
        assert "blahblah=blah" in output
        assert "stonith-enabled=false" in output
        assert output.startswith(
            "Cluster Properties: cib-bootstrap-options\n  batch-limit"
        )

        output, returnVal = pcs(
            self.temp_cib.name, "property config stonith-action".split()
        )
        assert returnVal == 0, output
        assert "stonith-action=reboot" in output

    def testBadProperties(self):
        o, r = pcs(self.temp_cib.name, "property set xxxx=zzzz".split())
        self.assertEqual(r, 1)
        ac(
            o,
            get_invalid_option_messages("xxxx"),
        )
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(o, "")

        output, returnVal = pcs(
            self.temp_cib.name, "property set =5678 --force".split()
        )
        ac(output, "Error: missing key in '=5678' option\n")
        self.assertEqual(returnVal, 1)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(o, "")

        output, returnVal = pcs(
            self.temp_cib.name, "property set =5678".split()
        )
        ac(output, "Error: missing key in '=5678' option\n")
        self.assertEqual(returnVal, 1)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(o, "")

        output, returnVal = pcs(
            self.temp_cib.name, "property set bad_format".split()
        )
        ac(output, "Error: missing value of 'bad_format' option\n")
        self.assertEqual(returnVal, 1)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(o, "")

        output, returnVal = pcs(
            self.temp_cib.name, "property set bad_format --force".split()
        )
        ac(output, "Error: missing value of 'bad_format' option\n")
        self.assertEqual(returnVal, 1)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(o, "")

        o, r = pcs(self.temp_cib.name, "property unset zzzzz".split())
        self.assertEqual(r, 1)
        ac(
            o,
            "Error: Cannot remove property 'zzzzz', it is not present in "
            "property set 'cib-bootstrap-options', use --force to override\n"
            "Error: Errors have occurred, therefore pcs is unable to continue\n",
        )
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(o, "")

        o, r = pcs(self.temp_cib.name, "property unset zzzz --force".split())
        self.assertEqual(r, 0)
        ac(
            o,
            "Warning: Cannot remove property 'zzzz', it is not present in "
            "property set 'cib-bootstrap-options'\n",
        )
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(o, "Cluster Properties: cib-bootstrap-options\n")

    def test_set_property_validation_enum(self):
        output, returnVal = pcs(
            self.temp_cib.name, "property set no-quorum-policy=freeze".split()
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  no-quorum-policy=freeze
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "property set no-quorum-policy=freeze --force".split(),
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  no-quorum-policy=freeze
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "property set no-quorum-policy=not_valid_value".split(),
        )
        ac(
            output,
            (
                "Error: 'not_valid_value' is not a valid no-quorum-policy "
                "value, use 'demote', 'freeze', 'ignore', 'stop', 'suicide', "
                "use --force to override\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  no-quorum-policy=freeze
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "property set no-quorum-policy=not_valid_value --force".split(),
        )
        ac(
            output,
            (
                "Warning: 'not_valid_value' is not a valid no-quorum-policy "
                "value, use 'demote', 'freeze', 'ignore', 'stop', 'suicide'\n"
            ),
        )
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  no-quorum-policy=not_valid_value
""",
        )

    def test_set_property_validation_boolean(self):
        output, returnVal = pcs(
            self.temp_cib.name, "property set enable-acl=TRUE".split()
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  enable-acl=TRUE
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name, "property set enable-acl=no".split()
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  enable-acl=no
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "property set enable-acl=TRUE --force".split(),
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  enable-acl=TRUE
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "property set enable-acl=not_valid_value".split(),
        )
        ac(
            output,
            (
                "Error: 'not_valid_value' is not a valid enable-acl value, use "
                "a pacemaker boolean value: '0', '1', 'false', 'n', 'no', "
                "'off', 'on', 'true', 'y', 'yes', use --force to override\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  enable-acl=TRUE
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "property set enable-acl=not_valid_value --force".split(),
        )
        ac(
            output,
            (
                "Warning: 'not_valid_value' is not a valid enable-acl value, "
                "use a pacemaker boolean value: '0', '1', 'false', 'n', 'no', "
                "'off', 'on', 'true', 'y', 'yes'\n"
            ),
        )
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  enable-acl=not_valid_value
""",
        )

    def test_set_property_validation_integer(self):
        output, returnVal = pcs(
            self.temp_cib.name, "property set migration-limit=0".split()
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  migration-limit=0
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name, "property set migration-limit=-10".split()
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  migration-limit=-10
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "property set migration-limit=0 --force".split(),
        )
        ac(output, "")
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  migration-limit=0
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name, "property set migration-limit=0.1".split()
        )
        ac(
            output,
            (
                "Error: '0.1' is not a valid migration-limit value, use an "
                "integer or INFINITY or -INFINITY, use --force to override\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assertEqual(returnVal, 1)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  migration-limit=0
""",
        )

        output, returnVal = pcs(
            self.temp_cib.name,
            "property set migration-limit=0.1 --force".split(),
        )
        ac(
            output,
            (
                "Warning: '0.1' is not a valid migration-limit value, use an "
                "integer or INFINITY or -INFINITY\n"
            ),
        )
        self.assertEqual(returnVal, 0)
        o, _ = pcs(self.temp_cib.name, "property config".split())
        ac(
            o,
            """Cluster Properties: cib-bootstrap-options
  migration-limit=0.1
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
        self.temp_cib = get_tmp_file("tier1_properties_unset")
        write_file_to_tmpfile(empty_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

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
            "property set batch-limit=100".split(),
            self.fixture_xml_with_props(),
        )
        self.assert_effect(
            "property unset batch-limit".split(), self.fixture_xml_empty_props()
        )

    def test_dont_create_nvset_on_removal(self):
        self.assert_pcs_fail(
            "property unset batch-limit".split(),
            (
                "Error: Cannot remove property 'batch-limit', it is not present"
                " in property set 'cib-bootstrap-options', use --force to "
                "override\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
