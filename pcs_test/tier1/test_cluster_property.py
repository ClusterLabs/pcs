from unittest import TestCase

from lxml import etree

from pcs.common.str_tools import (
    format_list,
    format_plural,
)

from pcs_test.tier0.lib.commands.test_cluster_property import ALLOWED_PROPERTIES
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import etree_to_str

property_cib = rc("cib-property.xml")
UNCHANGED_CRM_CONFIG = etree_to_str(
    etree.parse(property_cib).findall(".//crm_config")[0]
)


def get_invalid_option_messages(option_names, error=True, forceable=True):
    error_occurred = (
        "Error: Errors have occurred, therefore pcs is unable to continue\n"
    )
    use_force = ", use --force to override"
    return (
        "{severity}: invalid cluster property {option_pl} {option_name_list}, "
        "allowed options are: {allowed_properties}{use_force}\n"
        "{error_occurred}"
    ).format(
        severity="Error" if error else "Warning",
        option_name_list=format_list(option_names),
        option_pl=format_plural(option_names, "option", "options:"),
        allowed_properties=format_list(ALLOWED_PROPERTIES),
        use_force=use_force if error and forceable else "",
        error_occurred=error_occurred if error else "",
    )


class PropertyMixin(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//crm_config")[0]
        )
    )
):
    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_cluster_property")
        write_file_to_tmpfile(property_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        # pylint: disable=invalid-name
        self.temp_cib.close()


class TestPropertySet(PropertyMixin, TestCase):
    def test_success(self):
        self.assert_effect_single(
            (
                "property set enable-acl=true placement-strategy=utilization "
                "maintenance-mode="
            ).split(),
            """
            <crm_config>
                <cluster_property_set id="cib-bootstrap-options">
                    <nvpair id="cib-bootstrap-options-have-watchdog"
                        name="have-watchdog" value="false"
                    />
                    <nvpair id="cib-bootstrap-options-cluster-name"
                        name="cluster-name" value="HACluster"
                    />
                    <nvpair id="cib-bootstrap-options-placement-strategy"
                        name="placement-strategy" value="utilization"
                    />
                    <nvpair id="cib-bootstrap-options-enable-acl"
                        name="enable-acl" value="true"
                    />
                </cluster_property_set>
                <cluster_property_set id="second-set" score="10">
                    <nvpair id="second-set-maintenance-mode"
                        name="maintenance-mode" value="false"
                    />
                </cluster_property_set>
            </crm_config>
            """,
        )

    def test_properties_to_set_missing(self):
        self.assert_pcs_fail(
            "property set".split(),
            stdout_start="\nUsage: pcs property set...",
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_missing_value(self):
        self.assert_pcs_fail(
            "property set keyword".split(),
            stdout_start="Error: missing value of 'keyword' option\n",
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_unknown_properties(self):
        self.assert_pcs_fail(
            "property set unknown=value".split(),
            stdout_full=get_invalid_option_messages(["unknown"]),
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_unknown_properties_forced(self):
        self.assert_effect_single(
            "property set unknown=value --force".split(),
            """
            <crm_config>
                <cluster_property_set id="cib-bootstrap-options">
                    <nvpair id="cib-bootstrap-options-have-watchdog"
                        name="have-watchdog" value="false"
                    />
                    <nvpair id="cib-bootstrap-options-cluster-name"
                        name="cluster-name" value="HACluster"
                    />
                    <nvpair id="cib-bootstrap-options-maintenance-mode"
                        name="maintenance-mode" value="false"
                    />
                    <nvpair id="cib-bootstrap-options-placement-strategy"
                        name="placement-strategy" value="minimal"
                    />
                    <nvpair id="cib-bootstrap-options-enable-acl"
                        name="enable-acl" value="false"
                    />
                    <nvpair id="cib-bootstrap-options-unknown" name="unknown"
                        value="value"
                    />
                </cluster_property_set>
                <cluster_property_set id="second-set" score="10">
                    <nvpair id="second-set-maintenance-mode"
                        name="maintenance-mode" value="false"
                    />
                </cluster_property_set>
            </crm_config>
            """,
            output=get_invalid_option_messages(["unknown"], error=False),
        )

    def test_forbidden_properties(self):
        self.assert_pcs_fail(
            "property set cluster-name=NewName".split(),
            stdout_full=get_invalid_option_messages(
                ["cluster-name"], forceable=False
            ),
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_forbidden_properties_forced(self):
        self.assert_pcs_fail(
            "property set cluster-name=NewName --force".split(),
            stdout_full=get_invalid_option_messages(
                ["cluster-name"], forceable=False
            ),
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_set_stonith_watchdog_timeout(self):
        self.assert_pcs_fail(
            "property set stonith-watchdog-timeout=5s".split(),
            stdout_full=(
                "Error: stonith-watchdog-timeout can only be unset or set to 0 "
                "while SBD is disabled\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_set_stonith_watchdog_timeout_invalid_value(self):
        self.assert_pcs_fail(
            "property set stonith-watchdog-timeout=5x".split(),
            stdout_full=(
                "Error: '5x' is not a valid stonith-watchdog-timeout value, use"
                " time interval (e.g. 1, 2s, 3m, 4h, ...)\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)


class TestPropertyUnset(PropertyMixin, TestCase):
    def test_success(self):
        self.assert_effect_single(
            (
                "property unset placement-strategy enable-acl maintenance-mode"
            ).split(),
            """
            <crm_config>
                <cluster_property_set id="cib-bootstrap-options">
                    <nvpair id="cib-bootstrap-options-have-watchdog"
                        name="have-watchdog" value="false"
                    />
                    <nvpair id="cib-bootstrap-options-cluster-name"
                        name="cluster-name" value="HACluster"
                    />
                </cluster_property_set>
                <cluster_property_set id="second-set" score="10">
                    <nvpair id="second-set-maintenance-mode"
                        name="maintenance-mode" value="false"
                    />
                </cluster_property_set>
            </crm_config>
            """,
        )

    def test_properties_to_set_missing(self):
        self.assert_pcs_fail(
            "property unset".split(),
            stdout_start="\nUsage: pcs property unset...",
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_unset_not_configured_properties(self):
        self.assert_pcs_fail(
            "property unset missing1 missing2".split(),
            stdout_full=(
                "Error: Cannot remove properties 'missing1', 'missing2', they "
                "are not present in property set 'cib-bootstrap-options', use "
                "--force to override\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_unset_not_configured_properties_forced(self):
        self.assert_effect_single(
            "property unset missing1 missing2 --force".split(),
            UNCHANGED_CRM_CONFIG,
            output=(
                "Warning: Cannot remove properties 'missing1', 'missing2', they "
                "are not present in property set 'cib-bootstrap-options'\n"
            ),
        )
