import os.path
from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.command_env.config_runner_pcmk import (
    RULE_IN_EFFECT_RETURNCODE,
    RULE_EXPIRED_RETURNCODE,
    RULE_NOT_YET_IN_EFFECT_RETURNCODE,
)

from pcs import settings
from pcs.common import reports
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
)
from pcs.common.pacemaker.rule import (
    CibRuleDateCommonDto,
    CibRuleExpressionDto,
)
from pcs.common.types import (
    CibNvsetType,
    CibRuleInEffectStatus,
    CibRuleExpressionType,
)
from pcs.lib.commands import cib_options


class DefaultsCreateMixin:
    command = lambda *args, **kwargs: None
    tag = ""

    def setUp(self):
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load()

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

    def test_success_cib_upgrade_rsc_rules(self):
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
                    force_code=reports.codes.FORCE,
                    option_names=["unknown-option"],
                    allowed=["id", "score"],
                    option_type=None,
                    allowed_patterns=[],
                ),
                fixture.error(
                    reports.codes.RULE_EXPRESSION_PARSE_ERROR,
                    rule_string="bad rule",
                    reason="Expected 'eq'",
                    rule_line="bad rule",
                    line_number=1,
                    column_number=5,
                    position=4,
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
            force_flags={reports.codes.FORCE},
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
                self.env_assist.get_env(),
                {},
                {},
                "op monitor",
                force_flags={reports.codes.FORCE},
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

    def test_rule_node_attr_expression_not_allowed(self):
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", instead="runner.cib.load"
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.command(
                self.env_assist.get_env(),
                {},
                {},
                "defined attr",
                force_flags={reports.codes.FORCE},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                    expression_type=CibRuleExpressionType.EXPRESSION,
                ),
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
                        <rule id="my-id-rule-rule" boolean-op="or" score="0">
                            <date_expression id="my-id-rule-rule-expr"
                                operation="lt" end="2020-08-07"
                            />
                            <date_expression id="my-id-rule-rule-expr-1"
                                operation="in_range"
                                start="2020-09-01" end="2020-09-11"
                            />
                            <date_expression id="my-id-rule-rule-expr-2"
                                operation="in_range" start="2020-10-01"
                            >
                                <duration id="my-id-rule-rule-expr-2-duration"
                                    months="1"
                                />
                            </date_expression>
                            <date_expression id="my-id-rule-rule-expr-3"
                                operation="date_spec"
                            >
                                <date_spec id="my-id-rule-rule-expr-3-datespec"
                                    years="2021-2022"
                                />
                            </date_expression>
                            <date_expression id="my-id-rule-rule-expr-4"
                                operation="in_range" end="2020-12-11"
                            />
                        </rule>
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
            nvset_rule=(
                "resource ocf:pacemaker:Dummy and "
                "(date lt 2020-08-07 or "
                "date in_range 2020-09-01 to 2020-09-11 or "
                "date in_range 2020-10-01 to duration months=1 or "
                "date-spec years=2021-2022 or "
                "date in_range to 2020-12-11)"
            ),
        )

        self.env_assist.assert_reports(
            [fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN)]
        )


class OperationDefaultsCreate(DefaultsCreateMixin, TestCase):
    command = staticmethod(cib_options.operation_defaults_create)
    tag = "op_defaults"

    def test_success_full(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="my-id" score="10">
                    <rule id="my-id-rule" boolean-op="and" score="INFINITY">
                        <rsc_expression id="my-id-rule-rsc-ocf-pacemaker-Dummy"
                            class="ocf" provider="pacemaker" type="Dummy"
                        />
                        <op_expression id="my-id-rule-op-monitor" name="monitor"
                            interval="30"
                        />
                        <rule id="my-id-rule-rule" boolean-op="or" score="0">
                            <expression id="my-id-rule-rule-expr"
                                operation="defined" attribute="attr1"
                            />
                            <expression id="my-id-rule-rule-expr-1"
                                attribute="attr2" operation="gt"
                                type="number" value="5"
                            />
                            <date_expression id="my-id-rule-rule-expr-2"
                                operation="lt" end="2020-08-07"
                            />
                            <date_expression id="my-id-rule-rule-expr-3"
                                operation="in_range"
                                start="2020-09-01" end="2020-09-11"
                            />
                            <date_expression id="my-id-rule-rule-expr-4"
                                operation="in_range" start="2020-10-01"
                            >
                                <duration id="my-id-rule-rule-expr-4-duration"
                                    months="1"
                                />
                            </date_expression>
                            <date_expression id="my-id-rule-rule-expr-5"
                                operation="date_spec"
                            >
                                <date_spec id="my-id-rule-rule-expr-5-datespec"
                                    years="2021-2022"
                                />
                            </date_expression>
                            <date_expression id="my-id-rule-rule-expr-6"
                                operation="in_range" end="2020-12-11"
                            />
                        </rule>
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
            nvset_rule=(
                "resource ocf:pacemaker:Dummy and op monitor interval=30 and "
                "(defined attr1 or attr2 gt number 5 or date lt 2020-08-07 or "
                "date in_range 2020-09-01 to 2020-09-11 or "
                "date in_range 2020-10-01 to duration months=1 or "
                "date-spec years=2021-2022 or "
                "date in_range to 2020-12-11)"
            ),
        )

        self.env_assist.assert_reports(
            [fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN)]
        )

    def test_success_cib_upgrade_node_attr_type_int(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes">
                    <rule id="{self.tag}-meta_attributes-rule"
                        boolean-op="and" score="INFINITY"
                    >
                        <expression id="{self.tag}-meta_attributes-rule-expr"
                            attribute="attr" operation="eq" type="integer" value="5"
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
            filename="cib-empty-3.5.xml", instead="runner.cib.load"
        )
        self.config.env.push_cib(optional_in_conf=defaults_xml)

        self.command(
            self.env_assist.get_env(),
            {},
            {},
            nvset_rule="attr eq integer 5",
        )

        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL),
                fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN),
            ]
        )

    def test_success_cib_upgrade_node_attr_type_int_not_upgraded(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes">
                    <rule id="{self.tag}-meta_attributes-rule"
                        boolean-op="and" score="INFINITY"
                    >
                        <expression id="{self.tag}-meta_attributes-rule-expr"
                            attribute="attr" operation="eq" type="number" value="5"
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
            nvset_rule="attr eq integer 5",
        )

        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL),
                fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN),
            ]
        )

    def test_success_cib_upgrade_mixed(self):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="{self.tag}-meta_attributes">
                    <rule id="{self.tag}-meta_attributes-rule"
                        boolean-op="and" score="INFINITY"
                    >
                        <op_expression
                            id="{self.tag}-meta_attributes-rule-op-monitor"
                            name="monitor"
                        />
                        <expression id="{self.tag}-meta_attributes-rule-expr"
                            attribute="attr" operation="eq" type="integer"
                            value="5"
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
            filename="cib-empty-3.5.xml", instead="runner.cib.load"
        )
        self.config.env.push_cib(optional_in_conf=defaults_xml)

        self.command(
            self.env_assist.get_env(),
            {},
            {},
            nvset_rule="op monitor and attr eq integer 5",
        )

        self.env_assist.assert_reports(
            [
                fixture.info(reports.codes.CIB_UPGRADE_SUCCESSFUL),
                fixture.warn(reports.codes.DEFAULTS_CAN_BE_OVERRIDEN),
            ]
        )


class DefaultsConfigMixin:
    command = lambda *args, **kwargs: None
    tag = ""

    def setUp(self):
        # pylint: disable=invalid-name
        self.env_assist, self.config = get_env_tools(self)

    @staticmethod
    def fixture_expired_dto(expired):
        return CibNvsetDto(
            "my-id",
            CibNvsetType.META,
            {},
            CibRuleExpressionDto(
                "my-id-rule",
                CibRuleExpressionType.RULE,
                expired,
                {"boolean-op": "and"},
                None,
                None,
                [
                    CibRuleExpressionDto(
                        "my-id-rule-expr",
                        CibRuleExpressionType.EXPRESSION,
                        CibRuleInEffectStatus.UNKNOWN,
                        {
                            "operation": "defined",
                            "attribute": "attr1",
                        },
                        None,
                        None,
                        [],
                        "defined attr1",
                    ),
                ],
                "defined attr1",
            ),
            [CibNvpairDto("my-id-pair1", "name1", "value1")],
        )

    def test_empty(self):
        defaults_xml = f"""<{self.tag} />"""
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", optional_in_conf=defaults_xml
        )
        self.config.fs.isfile(
            (os.path.join(settings.pacemaker_binaries, "crm_rule")),
            return_value=True,
        )
        self.assertEqual([], self.command(self.env_assist.get_env(), True))

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
                        <op_expression
                            id="{self.tag}-meta_attributes-rule-op-monitor"
                            name="monitor" interval="30"
                        />
                        <rule id="{self.tag}-meta_attributes-rule-rule"
                            boolean-op="or"
                        >
                            <expression
                                id="{self.tag}-meta_attributes-rule-rule-expr"
                                operation="defined" attribute="attr1"
                            />
                            <expression
                                id="{self.tag}-meta_attributes-rule-rule-expr-1"
                                attribute="attr2" operation="gt"
                                type="integer" value="5"
                            />
                            <date_expression
                                id="{self.tag}-meta_attributes-rule-rule-expr-2"
                                operation="lt" end="2020-08-07"
                            />
                            <date_expression
                                id="{self.tag}-meta_attributes-rule-rule-expr-3"
                                operation="in_range"
                                start="2020-09-01" end="2020-09-11"
                            />
                            <date_expression
                                id="{self.tag}-meta_attributes-rule-rule-expr-4"
                                operation="in_range" start="2020-10-01"
                            >
                                <duration
                                    id="{self.tag}-meta_attributes-rule-rule-expr-4-duration"
                                    months="1"
                                />
                            </date_expression>
                            <date_expression
                                id="{self.tag}-meta_attributes-rule-rule-expr-5"
                                operation="date_spec"
                            >
                                <date_spec
                                    id="{self.tag}-meta_attributes-rule-rule-expr-5-datespec"
                                    years="2021-2022"
                                />
                            </date_expression>
                            <date_expression
                                id="{self.tag}-meta_attributes-rule-rule-expr-6"
                                operation="in_range" end="2020-12-11"
                            />
                        </rule>
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
        self.config.fs.isfile(
            (os.path.join(settings.pacemaker_binaries, "crm_rule")),
            return_value=False,
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
                        CibRuleInEffectStatus.UNKNOWN,
                        {"boolean-op": "and", "score": "INFINITY"},
                        None,
                        None,
                        [
                            CibRuleExpressionDto(
                                f"{self.tag}-meta_attributes-rule-rsc-Dummy",
                                CibRuleExpressionType.RSC_EXPRESSION,
                                CibRuleInEffectStatus.UNKNOWN,
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
                            CibRuleExpressionDto(
                                f"{self.tag}-meta_attributes-rule-op-monitor",
                                CibRuleExpressionType.OP_EXPRESSION,
                                CibRuleInEffectStatus.UNKNOWN,
                                {
                                    "name": "monitor",
                                    "interval": "30",
                                },
                                None,
                                None,
                                [],
                                "op monitor interval=30",
                            ),
                            CibRuleExpressionDto(
                                f"{self.tag}-meta_attributes-rule-rule",
                                CibRuleExpressionType.RULE,
                                CibRuleInEffectStatus.UNKNOWN,
                                {"boolean-op": "or"},
                                None,
                                None,
                                [
                                    CibRuleExpressionDto(
                                        f"{self.tag}-meta_attributes-rule-rule-expr",
                                        CibRuleExpressionType.EXPRESSION,
                                        CibRuleInEffectStatus.UNKNOWN,
                                        {
                                            "operation": "defined",
                                            "attribute": "attr1",
                                        },
                                        None,
                                        None,
                                        [],
                                        "defined attr1",
                                    ),
                                    CibRuleExpressionDto(
                                        f"{self.tag}-meta_attributes-rule-rule-expr-1",
                                        CibRuleExpressionType.EXPRESSION,
                                        CibRuleInEffectStatus.UNKNOWN,
                                        {
                                            "attribute": "attr2",
                                            "operation": "gt",
                                            "type": "integer",
                                            "value": "5",
                                        },
                                        None,
                                        None,
                                        [],
                                        "attr2 gt integer 5",
                                    ),
                                    CibRuleExpressionDto(
                                        f"{self.tag}-meta_attributes-rule-rule-expr-2",
                                        CibRuleExpressionType.DATE_EXPRESSION,
                                        CibRuleInEffectStatus.UNKNOWN,
                                        {
                                            "operation": "lt",
                                            "end": "2020-08-07",
                                        },
                                        None,
                                        None,
                                        [],
                                        "date lt 2020-08-07",
                                    ),
                                    CibRuleExpressionDto(
                                        f"{self.tag}-meta_attributes-rule-rule-expr-3",
                                        CibRuleExpressionType.DATE_EXPRESSION,
                                        CibRuleInEffectStatus.UNKNOWN,
                                        {
                                            "operation": "in_range",
                                            "start": "2020-09-01",
                                            "end": "2020-09-11",
                                        },
                                        None,
                                        None,
                                        [],
                                        "date in_range 2020-09-01 to 2020-09-11",
                                    ),
                                    CibRuleExpressionDto(
                                        f"{self.tag}-meta_attributes-rule-rule-expr-4",
                                        CibRuleExpressionType.DATE_EXPRESSION,
                                        CibRuleInEffectStatus.UNKNOWN,
                                        {
                                            "operation": "in_range",
                                            "start": "2020-10-01",
                                        },
                                        None,
                                        CibRuleDateCommonDto(
                                            f"{self.tag}-meta_attributes-rule-rule-expr-4-duration",
                                            {"months": "1"},
                                        ),
                                        [],
                                        "date in_range 2020-10-01 to duration months=1",
                                    ),
                                    CibRuleExpressionDto(
                                        f"{self.tag}-meta_attributes-rule-rule-expr-5",
                                        CibRuleExpressionType.DATE_EXPRESSION,
                                        CibRuleInEffectStatus.UNKNOWN,
                                        {"operation": "date_spec"},
                                        CibRuleDateCommonDto(
                                            f"{self.tag}-meta_attributes-rule-rule-expr-5-datespec",
                                            {"years": "2021-2022"},
                                        ),
                                        None,
                                        [],
                                        "date-spec years=2021-2022",
                                    ),
                                    CibRuleExpressionDto(
                                        f"{self.tag}-meta_attributes-rule-rule-expr-6",
                                        CibRuleExpressionType.DATE_EXPRESSION,
                                        CibRuleInEffectStatus.UNKNOWN,
                                        {
                                            "operation": "in_range",
                                            "end": "2020-12-11",
                                        },
                                        None,
                                        None,
                                        [],
                                        "date in_range to 2020-12-11",
                                    ),
                                ],
                                "defined attr1 or attr2 gt integer 5 or "
                                "date lt 2020-08-07 or "
                                "date in_range 2020-09-01 to 2020-09-11 or "
                                "date in_range 2020-10-01 to duration months=1 "
                                "or date-spec years=2021-2022 or "
                                "date in_range to 2020-12-11",
                            ),
                        ],
                        "resource ocf:pacemaker:Dummy and "
                        "op monitor interval=30 and "
                        "(defined attr1 or attr2 gt integer 5 or "
                        "date lt 2020-08-07 or "
                        "date in_range 2020-09-01 to 2020-09-11 or "
                        "date in_range 2020-10-01 to duration months=1 or "
                        "date-spec years=2021-2022 or "
                        "date in_range to 2020-12-11)",
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
            self.command(self.env_assist.get_env(), True),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RULE_IN_EFFECT_STATUS_DETECTION_NOT_SUPPORTED
                ),
            ]
        )

    def _setup_rule_in_effect(self, crm_rule_check=True, crm_rule_present=True):
        defaults_xml = f"""
            <{self.tag}>
                <meta_attributes id="my-id">
                    <rule id="my-id-rule" boolean-op="and">
                        <expression
                            id="my-id-rule-expr"
                            operation="defined" attribute="attr1"
                        />
                    </rule>
                    <nvpair id="my-id-pair1" name="name1" value="value1" />
                </meta_attributes>
            </{self.tag}>
        """
        self.config.runner.cib.load(
            filename="cib-empty-3.4.xml", optional_in_conf=defaults_xml
        )
        if crm_rule_check:
            self.config.fs.isfile(
                (os.path.join(settings.pacemaker_binaries, "crm_rule")),
                return_value=crm_rule_present,
            )

    def test_crm_rule_missing(self):
        self._setup_rule_in_effect(crm_rule_present=False)
        self.assertEqual(
            [self.fixture_expired_dto(CibRuleInEffectStatus.UNKNOWN)],
            self.command(self.env_assist.get_env(), True),
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.RULE_IN_EFFECT_STATUS_DETECTION_NOT_SUPPORTED
                ),
            ]
        )

    def test_no_expire_check(self):
        self._setup_rule_in_effect(crm_rule_check=False)
        self.assertEqual(
            [self.fixture_expired_dto(CibRuleInEffectStatus.UNKNOWN)],
            self.command(self.env_assist.get_env(), False),
        )

    def test_expired(self):
        self._setup_rule_in_effect()
        self.config.runner.pcmk.get_rule_in_effect_status(
            "my-id-rule",
            RULE_EXPIRED_RETURNCODE,
        )
        self.assertEqual(
            [self.fixture_expired_dto(CibRuleInEffectStatus.EXPIRED)],
            self.command(self.env_assist.get_env(), True),
        )

    def test_not_yet_in_effect(self):
        self._setup_rule_in_effect()
        self.config.runner.pcmk.get_rule_in_effect_status(
            "my-id-rule",
            RULE_NOT_YET_IN_EFFECT_RETURNCODE,
        )
        self.assertEqual(
            [self.fixture_expired_dto(CibRuleInEffectStatus.NOT_YET_IN_EFFECT)],
            self.command(self.env_assist.get_env(), True),
        )

    def test_in_effect(self):
        self._setup_rule_in_effect()
        self.config.runner.pcmk.get_rule_in_effect_status(
            "my-id-rule",
            RULE_IN_EFFECT_RETURNCODE,
        )
        self.assertEqual(
            [self.fixture_expired_dto(CibRuleInEffectStatus.IN_EFFECT)],
            self.command(self.env_assist.get_env(), True),
        )

    def test_expired_error(self):
        self._setup_rule_in_effect()
        self.config.runner.pcmk.get_rule_in_effect_status(
            "my-id-rule",
            2,  # unexpected return code
        )
        self.assertEqual(
            [self.fixture_expired_dto(CibRuleInEffectStatus.UNKNOWN)],
            self.command(self.env_assist.get_env(), True),
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
        self.config.runner.cib.load()
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
                self.env_assist.get_env(),
                "wrong-nvset-id",
                {},
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
