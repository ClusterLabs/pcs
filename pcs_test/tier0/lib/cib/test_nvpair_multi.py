from unittest import TestCase

from lxml import etree

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.xml import etree_to_str

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
from pcs.lib.cib import nvpair_multi
from pcs.lib.cib.rule.expression_part import (
    BOOL_AND,
    BoolExpr,
    OpExpr,
    RscExpr,
)
from pcs.lib.cib.tools import IdProvider


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
    tag_type = (
        ("meta_attributes", CibNvsetType.META),
        ("instance_attributes", CibNvsetType.INSTANCE),
    )

    def test_minimal(self):
        for tag, nvtype in self.tag_type:
            with self.subTest(tag=tag, nvset_type=nvtype):
                xml = etree.fromstring(f"""<{tag} id="my-id" />""")
                self.assertEqual(
                    nvpair_multi.nvset_element_to_dto(xml),
                    CibNvsetDto("my-id", nvtype, {}, None, []),
                )

    def test_full(self):
        for tag, nvtype in self.tag_type:
            with self.subTest(tag=tag, nvset_type=nvtype):
                xml = etree.fromstring(
                    f"""
                    <{tag} id="my-id" score="150">
                        <rule id="my-id-rule" boolean-op="or">
                            <op_expression id="my-id-rule-op" name="monitor" />
                        </rule>
                        <nvpair id="my-id-pair1" name="name1" value="value1" />
                        <nvpair id="my-id-pair2" name="name2" value="value2" />
                    </{tag}>
                """
                )
                self.assertEqual(
                    nvpair_multi.nvset_element_to_dto(xml),
                    CibNvsetDto(
                        "my-id",
                        nvtype,
                        {"score": "150"},
                        CibRuleExpressionDto(
                            "my-id-rule",
                            CibRuleExpressionType.RULE,
                            False,
                            {"boolean-op": "or"},
                            None,
                            None,
                            [
                                CibRuleExpressionDto(
                                    "my-id-rule-op",
                                    CibRuleExpressionType.OP_EXPRESSION,
                                    False,
                                    {"name": "monitor"},
                                    None,
                                    None,
                                    [],
                                    "op monitor",
                                ),
                            ],
                            "op monitor",
                        ),
                        [
                            CibNvpairDto("my-id-pair1", "name1", "value1"),
                            CibNvpairDto("my-id-pair2", "name2", "value2"),
                        ],
                    ),
                )


class FindNvsets(TestCase):
    def test_empty(self):
        xml = etree.fromstring("<parent />")
        self.assertEqual([], nvpair_multi.find_nvsets(xml))

    def test_full(self):
        xml = etree.fromstring(
            """
            <parent>
                <meta_attributes id="set1" />
                <instance_attributes id="set2" />
                <not_an_nvset id="set3" />
            </parent>
        """
        )
        self.assertEqual(
            ["set1", "set2"],
            [el.get("id") for el in nvpair_multi.find_nvsets(xml)],
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
            ["set1", "set2"], [el.get("id") for el in element_list],
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
        )
        assert_report_item_list_equal(
            validator.validate(), [],
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
                    force_code=reports.codes.FORCE_OPTIONS,
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
        )
        assert_report_item_list_equal(
            validator.validate(force_options=True),
            [
                fixture.error(
                    reports.codes.RULE_EXPRESSION_PARSE_ERROR,
                    rule_string="bad rule",
                    reason='Expected "resource"',
                    rule_line="bad rule",
                    line_number=1,
                    column_number=1,
                    position=0,
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
            context_element, id_provider, nvpair_multi.NVSET_META, {}, {}
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

    def test_rule(self):
        context_element = etree.fromstring("""<context id="a" />""")
        id_provider = IdProvider(context_element)
        nvpair_multi.nvset_append_new(
            context_element,
            id_provider,
            nvpair_multi.NVSET_META,
            {},
            {},
            nvset_rule=BoolExpr(
                BOOL_AND,
                [RscExpr("ocf", "pacemaker", "Dummy"), OpExpr("start", None)],
            ),
        )
        assert_xml_equal(
            """
                <context id="a">
                    <meta_attributes id="a-meta_attributes">
                        <rule id="a-meta_attributes-rule"
                            boolean-op="and" score="INFINITY"
                        >
                            <rsc_expression
                                id="a-meta_attributes-rule-rsc-ocf-pacemaker-Dummy"
                                class="ocf" provider="pacemaker" type="Dummy"
                            />
                            <op_expression id="a-meta_attributes-rule-op-start" 
                                name="start"
                            />
                        </rule>
                    </meta_attributes>
                </context>
            """,
            etree_to_str(context_element),
        )

    def test_custom_id(self):
        context_element = etree.fromstring("""<context id="a" />""")
        id_provider = IdProvider(context_element)
        nvpair_multi.nvset_append_new(
            context_element,
            id_provider,
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
