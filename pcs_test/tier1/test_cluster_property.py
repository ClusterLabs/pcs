import json
from textwrap import dedent
from unittest import TestCase

from lxml import etree

from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
    ListCibNvsetDto,
)
from pcs.common.str_tools import (
    format_list,
    format_plural,
)

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_data_to_tmpfile,
    write_file_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import (
    XmlManipulation,
    etree_to_str,
)

property_cib = rc("cib-property.xml")
UNCHANGED_CRM_CONFIG = etree_to_str(
    etree.parse(property_cib).findall(".//crm_config")[0]
)
FIXTURE_CONFIG_OUTPUT = dedent(
    """\
    Cluster Properties: cib-bootstrap-options
      cluster-name=HACluster
      enable-acl=false
      have-watchdog=false
      maintenance-mode=false
      placement-strategy=minimal
    """
)
_DEFAULT_MARK_REGEXP = r"(  .*=.* \(default\)\n)+"
_CONFIG_PROPERTIES_REGEXP_LIST = [
    r"Cluster Properties: cib-bootstrap-options\n",
    r"  cluster-name=HACluster\n",
    r"  enable-acl=false\n",
    r"  have-watchdog=false\n",
    r"  maintenance-mode=false\n",
    r"  placement-strategy=minimal\n",
]
CONFIG_ALL_REGEXP = (
    _DEFAULT_MARK_REGEXP.join(_CONFIG_PROPERTIES_REGEXP_LIST)
    + rf"{_DEFAULT_MARK_REGEXP}$"
)
DEFAULTS_REGEXP = r"^batch-limit=0\n(.*=.*\n)+$"
ALLOWED_PROPERTIES_REGEXP = r"'[^']+'(, '[^']+')*"


def get_invalid_option_messages_regexp(
    option_names, error=True, forceable=True
):
    error_occurred = (
        "Error: Errors have occurred, therefore pcs is unable to continue\n"
    )
    use_force = ", use --force to override"
    return (
        r"{severity}: invalid cluster property {option_pl} {option_name_list}, "
        r"allowed options are: {allowed_properties_regexp}{use_force}\n"
        r"{error_occurred}"
    ).format(
        severity="Error" if error else "Warning",
        option_name_list=format_list(option_names),
        option_pl=format_plural(option_names, "option", "options:"),
        allowed_properties_regexp=ALLOWED_PROPERTIES_REGEXP,
        use_force=use_force if error and forceable else "",
        error_occurred=error_occurred if error else "",
    )


class PropertyMixin(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//crm_config")[0])
    )
):
    def setUp(self):
        self.maxDiff = None
        self.temp_cib = get_tmp_file("tier1_cluster_property")
        write_file_to_tmpfile(property_cib, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
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
            stderr_start="\nUsage: pcs property set...",
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_missing_value(self):
        self.assert_pcs_fail(
            "property set keyword".split(),
            stderr_start="Error: missing value of 'keyword' option\n",
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_unknown_properties(self):
        self.assert_pcs_fail(
            "property set unknown=value".split(),
            stderr_regexp=get_invalid_option_messages_regexp(["unknown"]),
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
            stderr_regexp=get_invalid_option_messages_regexp(
                ["unknown"], error=False
            ),
        )

    def test_forbidden_properties(self):
        self.assert_pcs_fail(
            "property set cluster-name=NewName".split(),
            stderr_regexp=get_invalid_option_messages_regexp(
                ["cluster-name"], forceable=False
            ),
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_forbidden_properties_forced(self):
        self.assert_pcs_fail(
            "property set cluster-name=NewName --force".split(),
            stderr_regexp=get_invalid_option_messages_regexp(
                ["cluster-name"], forceable=False
            ),
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_set_stonith_watchdog_timeout_invalid_value(self):
        self.assert_pcs_fail(
            "property set stonith-watchdog-timeout=5x".split(),
            stderr_full=(
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
            stderr_start="\nUsage: pcs property unset...",
        )
        self.assert_resources_xml_in_cib(UNCHANGED_CRM_CONFIG)

    def test_unset_not_configured_properties(self):
        self.assert_pcs_fail(
            "property unset missing1 missing2".split(),
            stderr_full=(
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
            stderr_full=(
                "Warning: Cannot remove properties 'missing1', 'missing2', they "
                "are not present in property set 'cib-bootstrap-options'\n"
            ),
        )


class ConfigMixin(PropertyMixin):
    command = None

    def test_success(self):
        self.assert_pcs_success(self.command, stdout_full=FIXTURE_CONFIG_OUTPUT)

    def test_error(self):
        self.assert_pcs_fail(
            self.command + ["--output-format=format"],
            stderr_full=(
                "Error: Unknown value 'format' for '--output-format' option. "
                "Supported values are: 'cmd', 'json', 'text'\n"
            ),
        )

    def test_defaults_option(self):
        self.assert_pcs_success(
            self.command + ["--defaults"],
            stdout_regexp=DEFAULTS_REGEXP,
            stderr_full=(
                "Deprecation Warning: Option --defaults is deprecated and will "
                "be removed. Please use command 'pcs property defaults' "
                "instead.\n"
            ),
        )

    def test_all_option(self):
        self.assert_pcs_success(
            self.command + ["--all"], stdout_regexp=CONFIG_ALL_REGEXP
        )

    def test_json_format(self):
        stdout, stderr, retval = self.pcs_runner.run(
            "property config --output-format=json".split()
        )
        expected = ListCibNvsetDto(
            nvsets=[
                CibNvsetDto(
                    id="cib-bootstrap-options",
                    options={},
                    rule=None,
                    nvpairs=[
                        CibNvpairDto(
                            id="cib-bootstrap-options-cluster-name",
                            name="cluster-name",
                            value="HACluster",
                        ),
                        CibNvpairDto(
                            id="cib-bootstrap-options-enable-acl",
                            name="enable-acl",
                            value="false",
                        ),
                        CibNvpairDto(
                            id="cib-bootstrap-options-have-watchdog",
                            name="have-watchdog",
                            value="false",
                        ),
                        CibNvpairDto(
                            id="cib-bootstrap-options-maintenance-mode",
                            name="maintenance-mode",
                            value="false",
                        ),
                        CibNvpairDto(
                            id="cib-bootstrap-options-placement-strategy",
                            name="placement-strategy",
                            value="minimal",
                        ),
                    ],
                )
            ]
        )
        self.assertEqual(json.loads(stdout), to_dict(expected))
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)

    def test_cmd_format_with_readonly_properties(self):
        self.assert_pcs_success(
            self.command + ["--output-format=cmd"],
            stdout_full=dedent(
                """\
                pcs property set --force -- \\
                  enable-acl=false \\
                  maintenance-mode=false \\
                  placement-strategy=minimal
                """
            ),
        )

    def _get_as_json(self, runner):
        stdout, stderr, retval = runner.run(
            self.command + ["--output-format=json"]
        )
        self.assertEqual(stderr, "")
        self.assertEqual(retval, 0)
        return json.loads(stdout)

    def test_cmd_format_without_readonly_properties(self):
        orig_cib = get_tmp_file("tier1_cluster_property_orig")
        new_cib = get_tmp_file("tier1_cluster_property_new")
        xml_manip = XmlManipulation.from_file(rc("cib-empty.xml"))
        write_data_to_tmpfile(str(xml_manip), new_cib)
        xml_manip.append_to_first_tag_name(
            "crm_config",
            """
            <cluster_property_set id="cib-bootstrap-options">
                <nvpair id="cib-bootstrap-options-maintenance-mode"
                    name="maintenance-mode" value="false"/>
                <nvpair id="cib-bootstrap-options-placement-strategy"
                    name="placement-strategy" value="minimal"/>
                <nvpair id="cib-bootstrap-options-enable-acl" name="enable-acl"
                    value="false"/>
            </cluster_property_set>
            """,
        )
        write_data_to_tmpfile(str(xml_manip), orig_cib)
        pcs_runner_new = PcsRunner(new_cib.name)
        pcs_runner_orig = PcsRunner(orig_cib.name)

        stdout, stderr, retval = pcs_runner_orig.run(
            self.command + ["--output-format=cmd"]
        )
        self.assertEqual(retval, 0)
        self.assertEqual(stderr, "")

        cmd = stdout.replace("\\\n", "").split()
        stdout, stderr, retval = pcs_runner_new.run(cmd[1:])
        self.assertEqual(
            retval,
            0,
            (
                f"Command {cmd} exited with {retval}\nstdout:\n{stdout}\n"
                f"stderr:\n{stderr}"
            ),
        )
        self.assertEqual(
            self._get_as_json(pcs_runner_orig),
            self._get_as_json(pcs_runner_new),
        )
        orig_cib.close()
        new_cib.close()


class TestProperty(ConfigMixin, TestCase):
    command = ["property"]


class TestPropertyConfig(ConfigMixin, TestCase):
    command = ["property", "config"]

    def test_specific_properties(self):
        self.assert_effect_single(
            self.command + ["maintenance-mode", "batch-limit", "nodefault"],
            UNCHANGED_CRM_CONFIG,
            stdout_full=dedent(
                """\
                Cluster Properties: cib-bootstrap-options
                  batch-limit=0 (default)
                  maintenance-mode=false
                """
            ),
        )


class TestPropertyDefaults(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)

    def test_success(self):
        self.assert_pcs_success(
            "property defaults".split(), stdout_regexp=DEFAULTS_REGEXP
        )

    def test_success_full(self):
        self.assert_pcs_success(
            "property defaults --full".split(), stdout_regexp=DEFAULTS_REGEXP
        )

    def test_success_specific_properties_also_advanced(self):
        self.assert_pcs_success(
            "property defaults no-quorum-policy stonith-enabled".split(),
            stdout_full=dedent(
                """\
                no-quorum-policy=stop
                stonith-enabled=true
                """
            ),
        )

    def test_notexistent(self):
        self.assert_pcs_fail(
            "property defaults nonexistent".split(),
            stderr_full="Error: No default value for property: 'nonexistent'\n",
        )

    def test_unsupported_option(self):
        self.assert_pcs_fail(
            "property defaults --force".split(),
            stderr_full=(
                "Error: Specified option '--force' is not supported in this "
                "command\n"
            ),
        )


FIXTURE_BATCH_LIMIT_DESC = (
    "batch-limit\n"
    "  Description: Maximum number of jobs that the cluster may "
    'execute in parallel across all nodes. The "correct" value '
    "will depend on the speed and load of your network and "
    "cluster nodes. If set to 0, the cluster will impose a "
    "dynamically calculated limit when any node has a high load.\n"
    "  Type: integer\n"
    "  Default: 0\n"
)

FIXTURE_CLUSTER_NAME_DESC = (
    "cluster-name\n"
    "  Description: An arbitrary name for the cluster. This optional value is "
    "mostly for users' convenience as desired in administration, but may also "
    "be used in Pacemaker configuration rules via the #cluster-name node "
    "attribute, and by higher-level tools and resource agents.\n"
    "  Type: string\n"
)


class TestPropertyDescribe(TestCase, AssertPcsMixin):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)

    def test_success(self):
        self.assert_pcs_success(
            "property describe".split(),
            stdout_start=FIXTURE_BATCH_LIMIT_DESC,
        )

    def test_success_no_full(self):
        self.assert_pcs_success(
            "property describe".split(),
            stdout_regexp=r"(?!.*\(advanced use only\)).*",
        )

    def test_success_full(self):
        self.assert_pcs_success(
            "property describe --full".split(),
            stdout_regexp=r".*\(advanced use only\).*",
        )

    def test_success_specific(self):
        self.assert_pcs_success(
            "property describe cluster-name batch-limit".split(),
            stdout_full=FIXTURE_BATCH_LIMIT_DESC + FIXTURE_CLUSTER_NAME_DESC,
        )

    def test_notexistent(self):
        self.assert_pcs_fail(
            "property describe nonexistent".split(),
            stderr_full="Error: No description for property: 'nonexistent'\n",
        )

    def test_success_output_format_json(self):
        self.assert_pcs_success(
            "property describe --output-format=json".split(),
            stdout_regexp=(
                r'^{"properties_metadata": \[.*\], '
                r'"readonly_properties": \[.*\].*}$'
            ),
        )

    def test_fail_filter_and_output_format(self):
        self.assert_pcs_fail(
            "property describe property-name --output-format=json".split(),
            stderr_full=(
                "Error: property filtering is not supported with "
                "--output-format=json\n"
            ),
        )


class TestGetClusterPropertiesDefinition(AssertPcsMixin, TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)

    def test_success(self):
        self.assert_pcs_success(
            "property get_cluster_properties_definition".split(),
            stdout_regexp='^{".*": {.*}.*}$',
        )

    def test_fail_bad_syntax(self):
        self.assert_pcs_fail(
            "property get_cluster_properties_definition arg".split(),
            stderr_start="\nUsage: pcs property ...",
        )
