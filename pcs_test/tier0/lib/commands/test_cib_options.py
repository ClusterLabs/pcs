from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common import reports
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
)
from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.types import (
    CibNvsetType,
    CibRuleExpressionType,
)
from pcs.lib.commands import cib_options


class DefaultsCreateMixin:
    command = lambda *args, **kwargs: None
    tag = ""

    def setUp(self):
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(filename="cib-empty-1.2.xml")

    def test_success_minimal(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes" />
            </{self.tag}>
        """
        self.config.env.push_cib(optional_in_conf=defaults_xml)

        self.command(self.env_assist.get_env(), {}, {})

        self.env_assist.assert_reports(
            [fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN)]
        )

    def test_success_one_set_already_there(self):
        defaults_xml_1 = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes" />
            </{self.tag}>
        """
        defaults_xml_2 = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes" />
                <meta_attributes id="{self.tag}-meta_attributes-1" />
            </{self.tag}>
        """
        self.config.runner.cib.load(
            instead="runner.cib.load", optional_in_conf=defaults_xml_1
        )
        self.config.env.push_cib(optional_in_conf=defaults_xml_2)

        self.command(self.env_assist.get_env(), {}, {})

        self.env_assist.assert_reports(
            [fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN)]
        )

    def test_success_cib_upgrade(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes">
                    <rule id="{self.tag}-meta_attributes-rule"
                        boolean-op="and" score="INFINITY"
                    >
                        <rsc_expression
                            id="{self.tag}-meta_attributes-rule-rsc-ocf-pacemaker-Dummy"
                            class="ocf" provider="pacemaker" type="Dummy"
                        />
                    </rule>
                </meta_attributes>
            </{self.tag}>
        """
        self.config.runner.cib.load(
            name="load_cib_old_version",
            filename="cib-empty-3.3.xml",
            before="runner.cib.load",
        )
        self.config.runner.cib.upgrade(before="runner.cib.load")
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", instead="runner.cib.load"
        )
        self.config.env.push_cib(optional_in_conf=defaults_xml)

        self.command(
            self.env_assist.get_env(),
            {},
            {},
            nvset_rule="resource ocf:pacemaker:Dummy",
        )

        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL),
                fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN),
            ]
        )

    def test_success_full(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="my-id" score="10">
                    <rule id="my-id-rule" boolean-op="and" score="INFINITY">
                        <rsc_expression id="my-id-rule-rsc-ocf-pacemaker-Dummy"
                            class="ocf" provider="pacemaker" type="Dummy"
                        />
                    </rule>
                    <nvpair id="my-id-name1" name="name1" value="value1" />
                    <nvpair id="my-id-2name" name="2na#me" value="value2" />
                </meta_attributes>
            </{self.tag}>
        """
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", instead="runner.cib.load"
        )
        self.config.env.push_cib(optional_in_conf=defaults_xml)

        self.command(
            self.env_assist.get_env(),
            {"name1": "value1", "2na#me": "value2"},
            {"id": "my-id", "score": "10"},
            nvset_rule="resource ocf:pacemaker:Dummy",
        )

        self.env_assist.assert_reports(
            [fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN)]
        )

    def test_validation(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", instead="runner.cib.load"
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                self.env_assist.get_env(),
                {},
                {"unknown-option": "value"},
                "bad rule",
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE_OPTIONS,
                    option_names=["unknown-option"],
                    allowed=["id", "score"],
                    option_type=None,
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.RULE_EXPRESSION_PARSE_ERROR,
                    rule_string="bad rule",
                    reason='Expected "resource"',
                    rule_line="bad rule",
                    line_number=1,
                    column_number=1,
                    position=0,
                ),
            ]
        )

    def test_validation_forced(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes"
                    unknown-option="value"
                />
            </{self.tag}>
        """
        self.config.env.push_cib(optional_in_conf=defaults_xml)

        self.command(
            self.env_assist.get_env(),
            {},
            {"unknown-option": "value"},
            force_flags={reports.codes.FORCE_OPTIONS},
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["unknown-option"],
                    allowed=["id", "score"],
                    option_type=None,
                    allowed_patterns=[],
                ),
                fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN),
            ]
        )


class ResourceDefaultsCreate(DefaultsCreateMixin, TestCase):
    command = staticmethod(cib_options.resource_defaults_create)
    tag = "rsc_defaults"

    def test_rule_op_expression_not_allowed(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", instead="runner.cib.load"
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                self.env_assist.get_env(), {}, {}, "op monitor"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                    expression_type=CibRuleExpressionType.OP_EXPRESSION,
                ),
            ]
        )


class OperationDefaultsCreate(DefaultsCreateMixin, TestCase):
    command = staticmethod(cib_options.operation_defaults_create)
    tag = "op_defaults"


class DefaultsConfigMixin:
    command = lambda *args, **kwargs: None
    tag = ""

    def setUp(self):
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(self)

    def test_empty(self):
        defaults_xml = f"""<{self.tag} />"""
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", optional_in_conf=defaults_xml
        )
        self.assertEqual([], self.command(self.env_assist.get_env()))

    def test_full(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes">
                    <rule id="{self.tag}-meta_attributes-rule"
                        boolean-op="and" score="INFINITY"
                    >
                        <rsc_expression
                            id="{self.tag}-meta_attributes-rule-rsc-Dummy"
                            class="ocf" provider="pacemaker" type="Dummy"
                        />
                    </rule>
                    <nvpair id="my-id-pair1" name="name1" value="value1" />
                    <nvpair id="my-id-pair2" name="name2" value="value2" />
                </meta_attributes>
                <instance_attributes id="instance">
                    <nvpair id="instance-pair" name="inst" value="ance" />
                </instance_attributes>
                <meta_attributes id="meta-plain" score="123">
                    <nvpair id="my-id-pair3" name="name1" value="value1" />
                </meta_attributes>
            </{self.tag}>
        """
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", optional_in_conf=defaults_xml
        )
        self.assertEqual(
            [
                CibNvsetDto(
                    f"{self.tag}-meta_attributes",
                    CibNvsetType.META,
                    {},
                    CibRuleExpressionDto(
                        f"{self.tag}-meta_attributes-rule",
                        CibRuleExpressionType.RULE,
                        False,
                        {"boolean-op": "and", "score": "INFINITY"},
                        None,
                        None,
                        [
                            CibRuleExpressionDto(
                                f"{self.tag}-meta_attributes-rule-rsc-Dummy",
                                CibRuleExpressionType.RSC_EXPRESSION,
                                False,
                                {
                                    "class": "ocf",
                                    "provider": "pacemaker",
                                    "type": "Dummy",
                                },
                                None,
                                None,
                                [],
                                "resource ocf:pacemaker:Dummy",
                            ),
                        ],
                        "resource ocf:pacemaker:Dummy",
                    ),
                    [
                        CibNvpairDto("my-id-pair1", "name1", "value1"),
                        CibNvpairDto("my-id-pair2", "name2", "value2"),
                    ],
                ),
                CibNvsetDto(
                    "instance",
                    CibNvsetType.INSTANCE,
                    {},
                    None,
                    [CibNvpairDto("instance-pair", "inst", "ance")],
                ),
                CibNvsetDto(
                    "meta-plain",
                    CibNvsetType.META,
                    {"score": "123"},
                    None,
                    [CibNvpairDto("my-id-pair3", "name1", "value1")],
                ),
            ],
            self.command(self.env_assist.get_env()),
        )


class ResourceDefaultsConfig(DefaultsConfigMixin, TestCase):
    command = staticmethod(cib_options.resource_defaults_config)
    tag = "rsc_defaults"


class OperationDefaultsConfig(DefaultsConfigMixin, TestCase):
    command = staticmethod(cib_options.operation_defaults_config)
    tag = "op_defaults"


class DefaultsRemoveMixin:
    command = lambda *args, **kwargs: None
    tag = ""

    def setUp(self):
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(self)

    def test_nothing_to_delete(self):
        self.command(self.env_assist.get_env(), [])

    def test_defaults_section_missing(self):
        self.config.runner.cib.load(filename="cib-empty-1.2.xml")
        self.env_assist.assert_raise_library_error(
            lambda: self.command(self.env_assist.get_env(), ["set1"])
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    "set1",
                    context_type=self.tag,
                    expected_types=["options set"],
                ),
            ]
        )

    def test_success(self):
        self.config.runner.cib.load(
            filename="cib-empty-1.2.xml",
            optional_in_conf=f"""
                <{self.tag}>
                    <meta_attributes id="set1" />
                    <instance_attributes id="set2" />
                    <not_an_nvset id="set3" />
                    <meta_attributes id="set4" />
                    <instance_attributes id="set5" />
                </{self.tag}>
            """,
        )
        self.config.env.push_cib(
            optional_in_conf=f"""
                <{self.tag}>
                    <meta_attributes id="set1" />
                    <not_an_nvset id="set3" />
                    <meta_attributes id="set4" />
                </{self.tag}>
        """
        )
        self.command(self.env_assist.get_env(), ["set2", "set5"])

    def test_delete_all_keep_the_section(self):
        self.config.runner.cib.load(
            filename="cib-empty-1.2.xml",
            optional_in_conf=f"""
                <{self.tag}>
                    <meta_attributes id="set1" />
                </{self.tag}>
            """,
        )
        self.config.env.push_cib(optional_in_conf=f"<{self.tag} />")
        self.command(self.env_assist.get_env(), ["set1"])

    def test_nvset_not_found(self):
        self.config.runner.cib.load(
            filename="cib-empty-1.2.xml",
            optional_in_conf=f"""
                <{self.tag}>
                    <meta_attributes id="set1" />
                    <instance_attributes id="set2" />
                    <not_an_nvset id="set3" />
                    <meta_attributes id="set4" />
                    <instance_attributes id="set5" />
                </{self.tag}>
            """,
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                self.env_assist.get_env(), ["set2", "set3", "setX"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_unexpected_element(
                    "set3", "not_an_nvset", ["options set"]
                ),
                fixture.report_not_found(
                    "setX",
                    context_type=self.tag,
                    expected_types=["options set"],
                ),
            ]
        )


class ResourceDefaultsRemove(DefaultsRemoveMixin, TestCase):
    command = staticmethod(cib_options.resource_defaults_remove)
    tag = "rsc_defaults"


class OperationDefaultsRemove(DefaultsRemoveMixin, TestCase):
    command = staticmethod(cib_options.operation_defaults_remove)
    tag = "op_defaults"


class DefaultsUpdateLegacyMixin:
    # This class tests legacy use cases of not providing an nvset ID
    command = lambda *args, **kwargs: None
    tag = ""
    command_for_report = None

    def setUp(self):
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(self)
        self.reports = [fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN)]

    def tearDown(self):
        # pylint: disable=invalid-name
        self.env_assist.assert_reports(self.reports)

    def fixture_initial_defaults(self):
        return f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-options">
                    <nvpair id="{self.tag}-options-a" name="a" value="b"/>
                    <nvpair id="{self.tag}-options-b" name="b" value="c"/>
                </meta_attributes>
            </{self.tag}>
        """

    def test_change(self):
        self.config.runner.cib.load(
            optional_in_conf=self.fixture_initial_defaults()
        )
        self.config.env.push_cib(
            optional_in_conf=f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-options">
                    <nvpair id="{self.tag}-options-a" name="a" value="B"/>
                    <nvpair id="{self.tag}-options-b" name="b" value="C"/>
                </meta_attributes>
            </{self.tag}>
        """
        )
        self.command(self.env_assist.get_env(), None, {"a": "B", "b": "C"})

    def test_add(self):
        self.config.runner.cib.load(
            optional_in_conf=self.fixture_initial_defaults()
        )
        self.config.env.push_cib(
            optional_in_conf=f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-options">
                    <nvpair id="{self.tag}-options-a" name="a" value="b"/>
                    <nvpair id="{self.tag}-options-b" name="b" value="c"/>
                    <nvpair id="{self.tag}-options-c" name="c" value="d"/>
                </meta_attributes>
            </{self.tag}>
        """
        )
        self.command(self.env_assist.get_env(), None, {"c": "d"})

    def test_remove(self):
        self.config.runner.cib.load(
            optional_in_conf=self.fixture_initial_defaults()
        )
        self.config.env.push_cib(
            remove=(
                f"./configuration/{self.tag}/meta_attributes/nvpair[@name='a']"
            )
        )
        self.command(self.env_assist.get_env(), None, {"a": ""})

    def test_add_section_if_missing(self):
        self.config.runner.cib.load()
        self.config.env.push_cib(
            optional_in_conf=f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes">
                    <nvpair id="{self.tag}-meta_attributes-a" name="a" value="A"/>
                </meta_attributes>
            </{self.tag}>
        """
        )
        self.command(self.env_assist.get_env(), None, {"a": "A"})

    def test_add_meta_if_missing(self):
        self.config.runner.cib.load(optional_in_conf=f"<{self.tag} />")
        self.config.env.push_cib(
            optional_in_conf=f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes">
                    <nvpair id="{self.tag}-meta_attributes-a" name="a" value="A"/>
                </meta_attributes>
            </{self.tag}>
        """
        )
        self.command(self.env_assist.get_env(), None, {"a": "A"})

    def test_dont_add_section_if_only_removing(self):
        self.config.runner.cib.load()
        self.command(self.env_assist.get_env(), None, {"a": "", "b": ""})

    def test_dont_add_meta_if_only_removing(self):
        self.config.runner.cib.load(optional_in_conf=f"<{self.tag} />")
        self.command(self.env_assist.get_env(), None, {"a": "", "b": ""})

    def test_keep_section_when_empty(self):
        self.config.runner.cib.load(
            optional_in_conf=self.fixture_initial_defaults()
        )
        self.config.env.push_cib(remove=f"./configuration/{self.tag}//nvpair")
        self.command(self.env_assist.get_env(), None, {"a": "", "b": ""})

    def test_ambiguous(self):
        self.config.runner.cib.load(
            optional_in_conf=f"""
                <{self.tag}>
                    <meta_attributes id="{self.tag}-options">
                        <nvpair id="{self.tag}-options-a" name="a" value="b"/>
                        <nvpair id="{self.tag}-options-b" name="b" value="c"/>
                    </meta_attributes>
                    <meta_attributes id="{self.tag}-options-1">
                        <nvpair id="{self.tag}-options-c" name="c" value="d"/>
                    </meta_attributes>
                </{self.tag}>
            """
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command(self.env_assist.get_env(), None, {"x": "y"})
        )
        self.reports = [
            fixture.error(
                reports.codes.CIB_NVSET_AMBIGUOUS_PROVIDE_NVSET_ID,
                pcs_command=self.command_for_report,
            )
        ]


class DefaultsUpdateMixin:
    command = lambda *args, **kwargs: None
    tag = ""

    def setUp(self):
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(self)

    def fixture_initial_defaults(self):
        return f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-options">
                    <nvpair id="{self.tag}-options-a" name="a" value="b"/>
                    <nvpair id="{self.tag}-options-b" name="b" value="c"/>
                    <nvpair id="{self.tag}-options-c" name="c" value="d"/>
                </meta_attributes>
            </{self.tag}>
        """

    def test_success(self):
        self.config.runner.cib.load(
            optional_in_conf=self.fixture_initial_defaults()
        )
        self.config.env.push_cib(
            optional_in_conf=f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-options">
                    <nvpair id="{self.tag}-options-a" name="a" value="B"/>
                    <nvpair id="{self.tag}-options-b" name="b" value="c"/>
                    <nvpair id="{self.tag}-options-d" name="d" value="e"/>
                </meta_attributes>
            </{self.tag}>
        """
        )
        self.command(
            self.env_assist.get_env(),
            f"{self.tag}-options",
            {"a": "B", "c": "", "d": "e"},
        )
        self.env_assist.assert_reports(
            [fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN)]
        )

    def test_nvset_doesnt_exist(self):
        self.config.runner.cib.load(
            optional_in_conf=self.fixture_initial_defaults()
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                self.env_assist.get_env(), "wrong-nvset-id", {},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    "wrong-nvset-id",
                    context_type=self.tag,
                    expected_types=["options set"],
                ),
            ]
        )

    def test_keep_elements_when_empty(self):
        self.config.runner.cib.load(
            optional_in_conf=self.fixture_initial_defaults()
        )
        self.config.env.push_cib(remove=f"./configuration/{self.tag}//nvpair")
        self.command(
            self.env_assist.get_env(),
            f"{self.tag}-options",
            {"a": "", "b": "", "c": ""},
        )
        self.env_assist.assert_reports(
            [fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN)]
        )


class ResourceDefaultsUpdateLegacy(DefaultsUpdateLegacyMixin, TestCase):
    command = staticmethod(cib_options.resource_defaults_update)
    tag = "rsc_defaults"
    command_for_report = reports.const.PCS_COMMAND_RESOURCE_DEFAULTS_UPDATE


class OperationDefaultsUpdateLegacy(DefaultsUpdateLegacyMixin, TestCase):
    command = staticmethod(cib_options.operation_defaults_update)
    tag = "op_defaults"
    command_for_report = reports.const.PCS_COMMAND_OPERATION_DEFAULTS_UPDATE


class ResourceDefaultsUpdate(DefaultsUpdateMixin, TestCase):
    command = staticmethod(cib_options.resource_defaults_update)
    tag = "rsc_defaults"


class OperationDefaultsUpdate(DefaultsUpdateMixin, TestCase):
    command = staticmethod(cib_options.operation_defaults_update)
    tag = "op_defaults"
