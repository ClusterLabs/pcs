from unittest import TestCase

from lxml import etree

from pcs.common import reports
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
    CibNvsetDto,
)
from pcs.common.pacemaker.rule import (
    CibRuleDateCommonDto,
    CibRuleExpressionDto,
)
from pcs.common.tools import Version
from pcs.common.types import (
    CibRuleExpressionType,
    CibRuleInEffectStatus,
)
from pcs.lib.cib import nvpair_multi
from pcs.lib.cib.rule import RuleInEffectEval
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BOOL_OR,
    NODE_ATTR_OP_DEFINED,
    NODE_ATTR_OP_GT,
    NODE_ATTR_TYPE_NUMBER,
    BoolExpr,
    NodeAttrExpr,
    OpExpr,
    RscExpr,
)
from pcs.lib.cib.tools import IdProvider

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.xml import etree_to_str


class RuleInEffectEvalMock(RuleInEffectEval):
    def __init__(self, mock_data=None):
        self._mock_data = mock_data or {}

    def get_rule_status(self, rule_id):
        return self._mock_data.get(rule_id, CibRuleInEffectStatus.UNKNOWN)


def get_in_effect_eval(mock_data=None):
    return RuleInEffectEvalMock(mock_data)


class NvpairElementToDto(TestCase):
    def test_success(self):
        xml = etree.fromstring(
            """
            <nvpair id="my-id" name="my-name" value="my-value" />
        """
        )
        self.assertEqual(
            nvpair_multi.nvpair_element_to_dto(xml),
            CibNvpairDto("my-id", "my-name", "my-value"),
        )


class NvsetElementToDto(TestCase):
    all_nvsets = (
        nvpair_multi.NVSET_INSTANCE,
        nvpair_multi.NVSET_META,
        nvpair_multi.NVSET_UTILIZATION,
    )

    def test_minimal(self):
        for tag in self.all_nvsets:
            with self.subTest(tag=tag):
                xml = etree.fromstring(f"""<{tag} id="my-id" />""")
                self.assertEqual(
                    nvpair_multi.nvset_element_to_dto(
                        xml, get_in_effect_eval()
                    ),
                    CibNvsetDto("my-id", {}, None, []),
                )

    def test_expired(self):
        for tag in self.all_nvsets:
            with self.subTest(tag=tag):
                xml = etree.fromstring(
                    f"""
                    <{tag} id="my-id" score="150">
                        <rule id="my-id-rule" boolean-op="and">
                            <rsc_expression
                                id="my-id-rule-rsc-ocf-pacemaker-Dummy"
                                class="ocf" provider="pacemaker" type="Dummy"
                            />
                        </rule>
                        <nvpair id="my-id-pair1" name="name1" value="value1" />
                    </{tag}>
                """
                )
                self.assertEqual(
                    nvpair_multi.nvset_element_to_dto(
                        xml,
                        get_in_effect_eval(
                            {"my-id-rule": CibRuleInEffectStatus.EXPIRED}
                        ),
                    ),
                    CibNvsetDto(
                        "my-id",
                        {"score": "150"},
                        CibRuleExpressionDto(
                            "my-id-rule",
                            CibRuleExpressionType.RULE,
                            CibRuleInEffectStatus.EXPIRED,
                            {"boolean-op": "and"},
                            None,
                            None,
                            [
                                CibRuleExpressionDto(
                                    "my-id-rule-rsc-ocf-pacemaker-Dummy",
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
                            ],
                            "resource ocf:pacemaker:Dummy",
                        ),
                        [CibNvpairDto("my-id-pair1", "name1", "value1")],
                    ),
                )

    def test_full(self):
        for tag in self.all_nvsets:
            with self.subTest(tag=tag):
                xml = etree.fromstring(
                    f"""
                    <{tag} id="my-id" score="150">
                        <rule id="my-id-rule" boolean-op="and">
                            <rsc_expression
                                id="my-id-rule-rsc-ocf-pacemaker-Dummy"
                                class="ocf" provider="pacemaker" type="Dummy"
                            />
                            <op_expression id="my-id-rule-op" name="monitor" />
                            <rule id="my-id-rule-rule" boolean-op="or">
                                <expression id="my-id-rule-rule-expr"
                                    operation="defined" attribute="attr1"
                                />
                                <expression id="my-id-rule-rule-expr-1"
                                    attribute="attr2" operation="gt"
                                    type="integer" value="5"
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
                                    operation="in_range" end="2020-09-11"
                                />
                            </rule>
                        </rule>
                        <nvpair id="my-id-pair1" name="name1" value="value1" />
                        <nvpair id="my-id-pair2" name="name2" value="value2" />
                    </{tag}>
                """
                )
                self.assertEqual(
                    nvpair_multi.nvset_element_to_dto(
                        xml, get_in_effect_eval()
                    ),
                    CibNvsetDto(
                        "my-id",
                        {"score": "150"},
                        CibRuleExpressionDto(
                            "my-id-rule",
                            CibRuleExpressionType.RULE,
                            CibRuleInEffectStatus.UNKNOWN,
                            {"boolean-op": "and"},
                            None,
                            None,
                            [
                                CibRuleExpressionDto(
                                    "my-id-rule-rsc-ocf-pacemaker-Dummy",
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
                                    "my-id-rule-op",
                                    CibRuleExpressionType.OP_EXPRESSION,
                                    CibRuleInEffectStatus.UNKNOWN,
                                    {"name": "monitor"},
                                    None,
                                    None,
                                    [],
                                    "op monitor",
                                ),
                                CibRuleExpressionDto(
                                    "my-id-rule-rule",
                                    CibRuleExpressionType.RULE,
                                    CibRuleInEffectStatus.UNKNOWN,
                                    {"boolean-op": "or"},
                                    None,
                                    None,
                                    [
                                        CibRuleExpressionDto(
                                            "my-id-rule-rule-expr",
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
                                            "my-id-rule-rule-expr-1",
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
                                            "my-id-rule-rule-expr-2",
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
                                            "my-id-rule-rule-expr-3",
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
                                            "my-id-rule-rule-expr-4",
                                            CibRuleExpressionType.DATE_EXPRESSION,
                                            CibRuleInEffectStatus.UNKNOWN,
                                            {
                                                "operation": "in_range",
                                                "start": "2020-10-01",
                                            },
                                            None,
                                            CibRuleDateCommonDto(
                                                "my-id-rule-rule-expr-4-duration",
                                                {"months": "1"},
                                            ),
                                            [],
                                            "date in_range 2020-10-01 to duration months=1",
                                        ),
                                        CibRuleExpressionDto(
                                            "my-id-rule-rule-expr-5",
                                            CibRuleExpressionType.DATE_EXPRESSION,
                                            CibRuleInEffectStatus.UNKNOWN,
                                            {"operation": "date_spec"},
                                            CibRuleDateCommonDto(
                                                "my-id-rule-rule-expr-5-datespec",
                                                {"years": "2021-2022"},
                                            ),
                                            None,
                                            [],
                                            "date-spec years=2021-2022",
                                        ),
                                        CibRuleExpressionDto(
                                            "my-id-rule-rule-expr-6",
                                            CibRuleExpressionType.DATE_EXPRESSION,
                                            CibRuleInEffectStatus.UNKNOWN,
                                            {
                                                "operation": "in_range",
                                                "end": "2020-09-11",
                                            },
                                            None,
                                            None,
                                            [],
                                            "date in_range to 2020-09-11",
                                        ),
                                    ],
                                    "defined attr1 or attr2 gt integer 5 or "
                                    "date lt 2020-08-07 or "
                                    "date in_range 2020-09-01 to 2020-09-11 or "
                                    "date in_range 2020-10-01 to duration months=1 or "
                                    "date-spec years=2021-2022 or "
                                    "date in_range to 2020-09-11",
                                ),
                            ],
                            "resource ocf:pacemaker:Dummy and op monitor and "
                            "(defined attr1 or attr2 gt integer 5 or "
                            "date lt 2020-08-07 or "
                            "date in_range 2020-09-01 to 2020-09-11 or "
                            "date in_range 2020-10-01 to duration months=1 "
                            "or date-spec years=2021-2022 or "
                            "date in_range to 2020-09-11)",
                        ),
                        [
                            CibNvpairDto("my-id-pair1", "name1", "value1"),
                            CibNvpairDto("my-id-pair2", "name2", "value2"),
                        ],
                    ),
                )


class FindNvsets(TestCase):
    def setUp(self):
        self.xml = etree.fromstring(
            """
            <parent>
                <meta_attributes id="set1" />
                <instance_attributes id="set2" />
                <not_an_nvset id="set3" />
                <instance_attributes id="set6" />
                <meta_attributes id="set5" />
            </parent>
        """
        )

    def test_empty(self):
        xml = etree.fromstring("<parent />")
        self.assertEqual(
            [], nvpair_multi.find_nvsets(xml, nvpair_multi.NVSET_META)
        )

    def test_meta(self):
        self.assertEqual(
            ["set1", "set5"],
            [
                el.get("id")
                for el in nvpair_multi.find_nvsets(
                    self.xml, nvpair_multi.NVSET_META
                )
            ],
        )

    def test_instance(self):
        self.assertEqual(
            ["set2", "set6"],
            [
                el.get("id")
                for el in nvpair_multi.find_nvsets(
                    self.xml, nvpair_multi.NVSET_INSTANCE
                )
            ],
        )


class FindNvsetsByIds(TestCase):
    def test_success(self):
        xml = etree.fromstring(
            """
            <parent>
                <meta_attributes id="set1" />
                <instance_attributes id="set2" />
                <not_an_nvset id="set3" />
                <meta_attributes id="set4" />
            </parent>
        """
        )
        element_list, report_list = nvpair_multi.find_nvsets_by_ids(
            xml, ["set1", "set2", "set3", "setX"]
        )
        self.assertEqual(
            ["set1", "set2"],
            [el.get("id") for el in element_list],
        )
        assert_report_item_list_equal(
            report_list,
            [
                fixture.report_unexpected_element(
                    "set3", "not_an_nvset", ["options set"]
                ),
                fixture.report_not_found(
                    "setX",
                    context_type="parent",
                    expected_types=["options set"],
                ),
            ],
        )


class ValidateNvsetAppendNew(TestCase):
    def setUp(self):
        self.id_provider = IdProvider(
            etree.fromstring("""<cib><tags><tag id="a" /></tags></cib>""")
        )

    def test_success_minimal(self):
        validator = nvpair_multi.ValidateNvsetAppendNew(
            self.id_provider, {}, {}
        )
        assert_report_item_list_equal(
            validator.validate(force_options=True), []
        )
        self.assertIsNone(validator.get_parsed_rule())

    def test_success_full(self):
        validator = nvpair_multi.ValidateNvsetAppendNew(
            self.id_provider,
            {"name": "value"},
            {"id": "some-id", "score": "10"},
            nvset_rule="resource ::stateful",
            rule_allows_rsc_expr=True,
            rule_allows_op_expr=True,
            rule_allows_node_attr_expr=True,
        )
        assert_report_item_list_equal(
            validator.validate(),
            [],
        )
        self.assertEqual(
            repr(validator.get_parsed_rule()),
            "BoolExpr(operator='AND', children=["
            "RscExpr(standard=None, provider=None, type='stateful')"
            "])",
        )

    def test_id_not_valid(self):
        validator = nvpair_multi.ValidateNvsetAppendNew(
            self.id_provider, {}, {"id": "123"}
        )
        assert_report_item_list_equal(
            validator.validate(force_options=True),
            [fixture.report_invalid_id("123", "1")],
        )
        self.assertIsNone(validator.get_parsed_rule())

    def test_id_not_available(self):
        validator = nvpair_multi.ValidateNvsetAppendNew(
            self.id_provider, {}, {"id": "a"}
        )
        assert_report_item_list_equal(
            validator.validate(force_options=True),
            [fixture.error(reports.codes.ID_ALREADY_EXISTS, id="a")],
        )
        self.assertIsNone(validator.get_parsed_rule())

    def test_score_not_valid(self):
        validator = nvpair_multi.ValidateNvsetAppendNew(
            self.id_provider, {}, {"score": "a"}
        )
        assert_report_item_list_equal(
            validator.validate(force_options=True),
            [fixture.error(reports.codes.INVALID_SCORE, score="a")],
        )
        self.assertIsNone(validator.get_parsed_rule())

    def test_options_names(self):
        validator = nvpair_multi.ValidateNvsetAppendNew(
            self.id_provider, {}, {"not_valid": "a"}
        )
        assert_report_item_list_equal(
            validator.validate(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    force_code=reports.codes.FORCE,
                    option_names=["not_valid"],
                    allowed=["id", "score"],
                    option_type=None,
                    allowed_patterns=[],
                ),
            ],
        )
        self.assertIsNone(validator.get_parsed_rule())

    def test_options_names_forced(self):
        validator = nvpair_multi.ValidateNvsetAppendNew(
            self.id_provider, {}, {"not_valid": "a"}
        )
        assert_report_item_list_equal(
            validator.validate(force_options=True),
            [
                fixture.warn(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["not_valid"],
                    allowed=["id", "score"],
                    option_type=None,
                    allowed_patterns=[],
                ),
            ],
        )
        self.assertIsNone(validator.get_parsed_rule())

    def test_rule_not_valid(self):
        validator = nvpair_multi.ValidateNvsetAppendNew(
            self.id_provider,
            {},
            {},
            "bad rule",
            rule_allows_rsc_expr=True,
            rule_allows_op_expr=True,
            rule_allows_node_attr_expr=True,
        )
        assert_report_item_list_equal(
            validator.validate(force_options=True),
            [
                fixture.error(
                    reports.codes.RULE_EXPRESSION_PARSE_ERROR,
                    rule_string="bad rule",
                    reason="Expected 'eq'",
                    rule_line="bad rule",
                    line_number=1,
                    column_number=5,
                    position=4,
                ),
            ],
        )
        self.assertIsNone(validator.get_parsed_rule())


class NvsetAppendNew(TestCase):
    # pylint: disable=no-self-use
    def test_minimal(self):
        context_element = etree.fromstring("""<context id="a" />""")
        id_provider = IdProvider(context_element)
        nvpair_multi.nvset_append_new(
            context_element,
            id_provider,
            Version(3, 5, 0),
            nvpair_multi.NVSET_META,
            {},
            {},
        )
        assert_xml_equal(
            """
                <context id="a">
                    <meta_attributes id="a-meta_attributes" />
                </context>
            """,
            etree_to_str(context_element),
        )

    def test_nvpairs(self):
        context_element = etree.fromstring("""<context id="a" />""")
        id_provider = IdProvider(context_element)
        nvpair_multi.nvset_append_new(
            context_element,
            id_provider,
            Version(3, 5, 0),
            nvpair_multi.NVSET_META,
            {"attr1": "value1", "attr-empty": "", "attr2": "value2"},
            {},
        )
        assert_xml_equal(
            """
                <context id="a">
                    <meta_attributes id="a-meta_attributes">
                        <nvpair id="a-meta_attributes-attr1"
                            name="attr1" value="value1"
                        />
                        <nvpair id="a-meta_attributes-attr2"
                            name="attr2" value="value2"
                        />
                    </meta_attributes>
                </context>
            """,
            etree_to_str(context_element),
        )

    def assert_rule(self, cib_version, score_present):
        context_element = etree.fromstring("""<context id="a" />""")
        id_provider = IdProvider(context_element)
        nvpair_multi.nvset_append_new(
            context_element,
            id_provider,
            cib_version,
            nvpair_multi.NVSET_META,
            {},
            {},
            nvset_rule=BoolExpr(
                BOOL_AND,
                [
                    RscExpr("ocf", "pacemaker", "Dummy"),
                    OpExpr("start", None),
                    BoolExpr(
                        BOOL_OR,
                        [
                            NodeAttrExpr(
                                NODE_ATTR_OP_DEFINED, "attr1", None, None
                            ),
                            NodeAttrExpr(
                                NODE_ATTR_OP_GT,
                                "attr2",
                                "5",
                                NODE_ATTR_TYPE_NUMBER,
                            ),
                        ],
                    ),
                ],
            ),
        )
        assert_xml_equal(
            f"""
                <context id="a">
                    <meta_attributes id="a-meta_attributes">
                        <rule id="a-meta_attributes-rule"
                            boolean-op="and"
                            {'score="INFINITY"' if score_present else ""}
                        >
                            <rsc_expression
                                id="a-meta_attributes-rule-rsc-ocf-pacemaker-Dummy"
                                class="ocf" provider="pacemaker" type="Dummy"
                            />
                            <op_expression id="a-meta_attributes-rule-op-start" 
                                name="start"
                            />
                            <rule id="a-meta_attributes-rule-rule"
                                boolean-op="or"
                                {'score="0"' if score_present else ""}
                            >
                                <expression id="a-meta_attributes-rule-rule-expr"
                                    operation="defined" attribute="attr1"
                                />
                                <expression id="a-meta_attributes-rule-rule-expr-1"
                                    attribute="attr2" operation="gt"
                                    type="number" value="5"
                                />
                            </rule>
                        </rule>
                    </meta_attributes>
                </context>
            """,
            etree_to_str(context_element),
        )

    def test_rule_cib_3_5(self):
        self.assert_rule(Version(3, 5, 0), score_present=True)

    def test_rule_cib_3_9(self):
        self.assert_rule(Version(3, 9, 0), score_present=False)

    def test_custom_id(self):
        context_element = etree.fromstring("""<context id="a" />""")
        id_provider = IdProvider(context_element)
        nvpair_multi.nvset_append_new(
            context_element,
            id_provider,
            Version(3, 5, 0),
            nvpair_multi.NVSET_META,
            {},
            {"id": "custom-id"},
        )
        assert_xml_equal(
            """
                <context id="a">
                    <meta_attributes id="custom-id" />
                </context>
            """,
            etree_to_str(context_element),
        )

    def test_options(self):
        context_element = etree.fromstring("""<context id="a" />""")
        id_provider = IdProvider(context_element)
        nvpair_multi.nvset_append_new(
            context_element,
            id_provider,
            Version(3, 5, 0),
            nvpair_multi.NVSET_META,
            {},
            {"score": "INFINITY", "empty-attr": ""},
        )
        assert_xml_equal(
            """
                <context id="a">
                    <meta_attributes id="a-meta_attributes" score="INFINITY" />
                </context>
            """,
            etree_to_str(context_element),
        )

    def test_everything(self):
        context_element = etree.fromstring("""<context id="a" />""")
        id_provider = IdProvider(context_element)
        nvpair_multi.nvset_append_new(
            context_element,
            id_provider,
            Version(3, 5, 0),
            nvpair_multi.NVSET_META,
            {"attr1": "value1", "attr-empty": "", "attr2": "value2"},
            {"id": "custom-id", "score": "INFINITY", "empty-attr": ""},
            nvset_rule=BoolExpr(
                BOOL_AND,
                [RscExpr("ocf", "pacemaker", "Dummy"), OpExpr("start", None)],
            ),
        )
        assert_xml_equal(
            """
                <context id="a">
                    <meta_attributes id="custom-id" score="INFINITY">
                        <rule id="custom-id-rule"
                            boolean-op="and" score="INFINITY"
                        >
                            <rsc_expression id="custom-id-rule-rsc-ocf-pacemaker-Dummy"
                                class="ocf" provider="pacemaker" type="Dummy"
                            />
                            <op_expression id="custom-id-rule-op-start" 
                                name="start"
                            />
                        </rule>
                        <nvpair id="custom-id-attr1"
                            name="attr1" value="value1"
                        />
                        <nvpair id="custom-id-attr2"
                            name="attr2" value="value2"
                        />
                    </meta_attributes>
                </context>
            """,
            etree_to_str(context_element),
        )


class NvsetRemove(TestCase):
    # pylint: disable=no-self-use
    def test_success(self):
        xml = etree.fromstring(
            """
            <parent>
                <meta_attributes id="set1" />
                <instance_attributes id="set2" />
                <not_an_nvset id="set3" />
                <meta_attributes id="set4" />
            </parent>
        """
        )
        nvpair_multi.nvset_remove(
            [xml.find(".//*[@id='set2']"), xml.find(".//*[@id='set4']")]
        )
        assert_xml_equal(
            """
            <parent>
                <meta_attributes id="set1" />
                <not_an_nvset id="set3" />
            </parent>
            """,
            etree_to_str(xml),
        )


class NvsetUpdate(TestCase):
    # pylint: disable=no-self-use
    def test_success_nvpair_all_cases(self):
        nvset_element = etree.fromstring(
            """
            <meta_attributes id="set1">
                <nvpair id="pair1" name="name1" value="value1" />
                <nvpair id="pair2" name="name2" value="value2" />
                <nvpair id="pair3" name="name 3" value="value 3" />
                <nvpair id="pair4" name="name4" value="value4" />
                <nvpair id="pair4A" name="name4" value="value4A" />
                <nvpair id="pair4B" name="name4" value="value4B" />
            </meta_attributes>
        """
        )
        id_provider = IdProvider(nvset_element)
        nvpair_multi.nvset_update(
            nvset_element,
            id_provider,
            {
                "name2": "",  # delete
                "name 3": "value 3 new",  # change and escaping spaces
                "name4": "value4new",  # change and make unique
                "name5": "",  # do not add empty
                "name'6'": 'value"6"',  # escaping
            },
        )
        assert_xml_equal(
            """
            <meta_attributes id="set1">
                <nvpair id="pair1" name="name1" value="value1" />
                <nvpair id="pair3" name="name 3" value="value 3 new" />
                <nvpair id="pair4" name="name4" value="value4new" />
                <nvpair id="set1-name6"
                    name="name&#x27;6&#x27;" value="value&quot;6&quot;"
                />
            </meta_attributes>
            """,
            etree_to_str(nvset_element),
        )

    def test_keep_empty_nvset(self):
        parent_element = etree.fromstring(
            """
            <primitive>
                <meta_attributes id="set1">
                    <nvpair id="pair1" name="name1" value="value1" />
                </meta_attributes>
            </primitive>
            """
        )
        nvset_element = parent_element.find(".//meta_attributes")
        id_provider = IdProvider(parent_element)
        nvpair_multi.nvset_update(nvset_element, id_provider, {"name1": ""})
        assert_xml_equal(
            """
            <primitive>
                <meta_attributes id="set1">
                </meta_attributes>
            </primitive>
            """,
            etree_to_str(parent_element),
        )
