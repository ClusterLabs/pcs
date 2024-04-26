from unittest import TestCase

from lxml import etree

from pcs.common import (
    const,
    reports,
)
from pcs.common.pacemaker.types import CibResourceDiscovery
from pcs.common.types import CibRuleExpressionType
from pcs.lib.cib import const as cib_const
from pcs.lib.cib.constraint import location
from pcs.lib.cib.rule import parse_rule
from pcs.lib.cib.tools import IdProvider
from pcs.lib.xml_tools import etree_to_str

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)


class IsLocationConstraint(TestCase):
    def test_location_constraint_true(self):
        self.assertTrue(
            location.is_location_constraint(etree.Element("rsc_location"))
        )

    def test_location_constraint_false(self):
        self.assertFalse(
            location.is_location_constraint(etree.Element("location"))
        )


class IsLocationConstraintWithRule(TestCase):
    def test_location_with_rule(self):
        self.assertTrue(
            location.is_location_constraint_with_rule(
                etree.fromstring("<rsc_location><rule/></rsc_location>")
            )
        )

    def test_location_no_rule(self):
        self.assertFalse(
            location.is_location_constraint_with_rule(
                etree.fromstring("<rsc_location />")
            )
        )

    def test_element_with_rule(self):
        self.assertFalse(
            location.is_location_constraint_with_rule(
                etree.fromstring("<element><rule/></element>")
            )
        )


class IsLocationRule(TestCase):
    def test_location_constraint_true(self):
        self.assertTrue(
            location.is_location_rule(
                etree.SubElement(etree.Element("rsc_location"), "rule")
            )
        )

    def test_location_constraint_false(self):
        for element in (
            etree.Element("rule"),
            etree.SubElement(etree.Element("rsc_order"), "rule"),
            etree.SubElement(
                etree.SubElement(etree.Element("rsc_location"), "rsc_order"),
                "rule",
            ),
        ):
            with self.subTest(element=element):
                self.assertFalse(location.is_location_rule(element))


class DuplicatesCheckerLocationRulePlainTest(TestCase):
    cib = etree.fromstring(
        """
        <constraints>
          <rsc_location id="L1" rsc="R1" node="node1" score="100" />
          <rsc_location id="L2" rsc="R1">
            <rule id="L2-rule" boolean-op="and" score="0">
              <expression id="L2-rule-expr-1"
                  attribute="foo" operation="gt" type="version" value="1.2"
              />
              <expression id="L2-rule-expr"
                  attribute="#uname" operation="eq" value="node3"
              />
            </rule>
            <rule id="L2-rule-1" boolean-op="and" score="0">
              <date_expression id="L2-rule-1-expr" operation="date_spec">
                <date_spec id="L2-rule-1-expr-datespec" weekdays="1-5" />
              </date_expression>
            </rule>
          </rsc_location>
          <rsc_location id="L3" rsc="R1">
            <rule id="L3-rule" boolean-op="and" score="0">
              <expression id="L3-rule-expr"
                  attribute="#uname" operation="eq" type="string" value="node3"
              />
              <expression id="L3-rule-expr-1"
                  attribute="foo" operation="gt" type="version" value="1.2"
              />
            </rule>
          </rsc_location>
          <rsc_location id="L4" rsc="R1">
            <rule id="L4-rule" boolean-op="and" score="0">
              <date_expression id="L4-rule-expr" operation="date_spec">
                <date_spec id="L4-rule-expr-datespec" weekdays="1-5" />
              </date_expression>
            </rule>
          </rsc_location>
          <rsc_location id="L5" rsc="R2">
            <rule id="L5-rule" boolean-op="and" score="0">
              <date_expression id="L5-rule-expr" operation="date_spec">
                <date_spec id="L5-rule-expr-datespec" weekdays="1-5" />
              </date_expression>
            </rule>
          </rsc_location>
          <rsc_location id="L6" rsc-pattern="R*">
            <rule id="L6-rule" boolean-op="and" score="0">
              <expression id="L6-rule-expr"
                  attribute="#uname" operation="eq" value="node3"
              />
            </rule>
          </rsc_location>
          <rsc_location id="L7" rsc-pattern="R*">
            <rule id="L7-rule" boolean-op="and" score="0">
              <expression id="L7-rule-expr"
                  attribute="#uname" operation="eq" type="string" value="node3"
              />
            </rule>
          </rsc_location>
        </constraints>
        """
    )

    def test_success(self):
        duplicates = {
            # L1 has no rules
            # L2 has more than one rule - not compatible with the checker
            "L3": ["L2"],  # rsc matches, the only rule matches when normalized
            "L4": ["L2"],  # rsc matches, the only rule matches
            "L5": [],  # rsc doesn't match, rule matches
            "L6": ["L7"],  # rsc-pattern matches, normalized rule matches
            "L7": ["L6"],  # rsc-pattern matches, normalized rule matches
        }
        checker = location.DuplicatesCheckerLocationRulePlain()
        for id_to_check, id_results in duplicates.items():
            for forced in (False, True):
                with self.subTest(id_to_check=id_to_check, forced=forced):
                    real_reports = checker.check(
                        self.cib,
                        self.cib.xpath(".//*[@id=$id]", id=f"{id_to_check}")[0],
                        force_flags=([reports.codes.FORCE] if forced else []),
                    )
                    expected_reports = []
                    if id_results:
                        if forced:
                            expected_reports = [
                                fixture.warn(
                                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                                    constraint_ids=id_results,
                                )
                            ]
                        else:
                            expected_reports = [
                                fixture.error(
                                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                                    force_code=reports.codes.FORCE,
                                    constraint_ids=id_results,
                                )
                            ]
                    assert_report_item_list_equal(
                        real_reports, expected_reports
                    )


class ValidateWithRuleCommonMixin:
    def get_validator(self, id_provider, rule_str, rule_options):
        raise NotImplementedError()

    def test_success_minimal(self):
        validator = self.get_validator(self.id_provider, "#uname eq node1", {})
        assert_report_item_list_equal(validator.validate(), [])

    def test_success_rule_options_1(self):
        validator = self.get_validator(
            self.id_provider,
            "#uname eq node1",
            {
                "id": "ruleid",
                "role": const.PCMK_ROLE_PROMOTED,
                "score": "123",
            },
        )
        assert_report_item_list_equal(validator.validate(), [])

    def test_success_rule_options_2(self):
        validator = self.get_validator(
            self.id_provider,
            "#uname eq node1",
            {
                "id": "ruleid",
                "role": const.PCMK_ROLE_PROMOTED_LEGACY,
                "score-attribute": "something",
            },
        )
        assert_report_item_list_equal(
            validator.validate(),
            [
                fixture.deprecation(
                    reports.codes.DEPRECATED_OPTION_VALUE,
                    option_name="role",
                    deprecated_value=const.PCMK_ROLE_PROMOTED_LEGACY,
                    replaced_by=const.PCMK_ROLE_PROMOTED_PRIMARY,
                ),
            ],
        )

    def test_rule_options_bad(self):
        for force_flags in ({}, {reports.codes.FORCE}):
            with self.subTest(force_flags=force_flags):
                validator = self.get_validator(
                    self.id_provider,
                    "#uname eq node1",
                    {
                        "id": "bad id",
                        "role": "bad role",
                        "score": "bad score",
                        "score-attribute": "something",
                        "bad": "option",
                    },
                )
                assert_report_item_list_equal(
                    validator.validate(force_flags),
                    [
                        fixture.error(
                            reports.codes.INVALID_OPTIONS,
                            option_names=["bad"],
                            allowed=["id", "role", "score", "score-attribute"],
                            option_type="rule",
                            allowed_patterns=[],
                        ),
                        fixture.error(
                            reports.codes.MUTUALLY_EXCLUSIVE_OPTIONS,
                            option_names=["score", "score-attribute"],
                            option_type="rule",
                        ),
                        fixture.error(
                            reports.codes.INVALID_ID_BAD_CHAR,
                            id="bad id",
                            id_description="rule id",
                            invalid_character=" ",
                            is_first_char=False,
                        ),
                        fixture.error(
                            reports.codes.INVALID_SCORE,
                            score="bad score",
                        ),
                        fixture.error(
                            reports.codes.INVALID_OPTION_VALUE,
                            option_name="role",
                            option_value="bad role",
                            allowed_values=(
                                const.PCMK_ROLES_PROMOTED
                                + const.PCMK_ROLES_UNPROMOTED
                            ),
                            cannot_be_empty=False,
                            forbidden_characters=None,
                        ),
                    ],
                )

    def test_rule_not_specified(self):
        for force_flags in ({}, {reports.codes.FORCE}):
            with self.subTest(force_flags=force_flags):
                validator = self.get_validator(self.id_provider, "", {})
                assert_report_item_list_equal(
                    validator.validate(force_flags),
                    [
                        fixture.error(
                            reports.codes.RULE_NO_EXPRESSION_SPECIFIED
                        ),
                    ],
                )

    def test_rule_not_valid(self):
        for force_flags in ({}, {reports.codes.FORCE}):
            with self.subTest(force_flags=force_flags):
                validator = self.get_validator(
                    self.id_provider, "#uname eq", {}
                )
                assert_report_item_list_equal(
                    validator.validate(force_flags),
                    [
                        fixture.error(
                            reports.codes.RULE_EXPRESSION_PARSE_ERROR,
                            rule_string="#uname eq",
                            reason="Expected <attribute value>",
                            rule_line="#uname eq",
                            line_number=1,
                            column_number=10,
                            position=9,
                        ),
                    ],
                )

    def test_rule_with_rsc_expression(self):
        for force_flags in ({}, {reports.codes.FORCE}):
            with self.subTest(force_flags=force_flags):
                validator = self.get_validator(
                    self.id_provider, "#uname eq node1 or resource ocf::", {}
                )
                assert_report_item_list_equal(
                    validator.validate(force_flags),
                    [
                        fixture.error(
                            reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                            expression_type=CibRuleExpressionType.RSC_EXPRESSION,
                        )
                    ],
                )

    def test_rule_with_op_expression(self):
        for force_flags in ({}, {reports.codes.FORCE}):
            with self.subTest(force_flags=force_flags):
                validator = self.get_validator(
                    self.id_provider, "#uname eq node1 or op moonitor", {}
                )
                assert_report_item_list_equal(
                    validator.validate(force_flags),
                    [
                        fixture.error(
                            reports.codes.RULE_EXPRESSION_NOT_ALLOWED,
                            expression_type=CibRuleExpressionType.OP_EXPRESSION,
                        )
                    ],
                )


class ValidateCreatePlainWithRuleCommonMixin(ValidateWithRuleCommonMixin):
    def setUp(self):
        self.cib = etree.fromstring(
            """
            <cib>
              <configuration>
                <resources>
                  <primitive id="R1" class="ocf" provider="pacemaker" type="Dummy">
                    <operations>
                      <op id="R1-monitor" name="monitor" interval="60s" />
                    </operations>
                  </primitive>
                  <clone id="C1">
                    <primitive id="C1R1" class="ocf" provider="pacemaker" type="Dummy" />
                  </clone>
                </resources>
                <constraints />
              </configuration>
            </cib>
            """
        )
        self.resource = self.cib.xpath(".//primitive[@id='R1']")[0]
        self.id_provider = IdProvider(self.cib)

    def get_validator(
        self,
        id_provider,
        rule_str,
        rule_options,
        constraint_options=None,
        constrained_el=None,
    ):
        return location.ValidateCreatePlainWithRule(
            id_provider,
            rule_str,
            rule_options,
            constraint_options or {},
            constrained_el if constrained_el is not None else self.resource,
        )

    def test_success_constraint_options(self):
        validator = location.ValidateCreatePlainWithRule(
            self.id_provider,
            "#uname eq node1",
            {},
            {"id": "location-1", "resource-discovery": "always"},
            self.resource,
        )
        assert_report_item_list_equal(validator.validate(), [])

    def test_constraint_id_already_exists(self):
        test_id = "location-1"
        self.id_provider.book_ids(test_id)
        for force_flags in ({}, {reports.codes.FORCE}):
            with self.subTest(force_flags=force_flags):
                validator = location.ValidateCreatePlainWithRule(
                    self.id_provider,
                    "#uname eq node1",
                    {},
                    {"id": test_id},
                    self.resource,
                )
                assert_report_item_list_equal(
                    validator.validate(force_flags),
                    [
                        fixture.error(
                            reports.codes.ID_ALREADY_EXISTS,
                            id=test_id,
                        )
                    ],
                )

    def test_resource_discovery_invalid(self):
        validator = location.ValidateCreatePlainWithRule(
            self.id_provider,
            "#uname eq node1",
            {},
            {"resource-discovery": "bad value"},
            self.resource,
        )
        assert_report_item_list_equal(
            validator.validate(),
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    force_code=reports.codes.FORCE,
                    option_name="resource-discovery",
                    option_value="bad value",
                    allowed_values=[
                        CibResourceDiscovery.ALWAYS,
                        CibResourceDiscovery.EXCLUSIVE,
                        CibResourceDiscovery.NEVER,
                    ],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )

    def test_resource_discovery_invalid_forced(self):
        validator = location.ValidateCreatePlainWithRule(
            self.id_provider,
            "#uname eq node1",
            {},
            {"resource-discovery": "bad value"},
            self.resource,
        )
        assert_report_item_list_equal(
            validator.validate({reports.codes.FORCE}),
            [
                fixture.warn(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="resource-discovery",
                    option_value="bad value",
                    allowed_values=[
                        CibResourceDiscovery.ALWAYS,
                        CibResourceDiscovery.EXCLUSIVE,
                        CibResourceDiscovery.NEVER,
                    ],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
            ],
        )


class ValidateCreatePlainWithRuleWithResource(
    ValidateCreatePlainWithRuleCommonMixin, TestCase
):
    def setUp(self):
        super().setUp()
        self.resource_in_clone = self.cib.xpath(".//primitive[@id='C1R1']")[0]

    def test_resource_in_clone(self):
        validator = location.ValidateCreatePlainWithRule(
            self.id_provider,
            "#uname eq node1",
            {},
            {},
            self.resource_in_clone,
        )
        assert_report_item_list_equal(
            validator.validate(),
            [
                fixture.error(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    force_code=reports.codes.FORCE,
                    resource_id="C1R1",
                    parent_type="clone",
                    parent_id="C1",
                )
            ],
        )

    def test_resource_in_clone_forced(self):
        validator = location.ValidateCreatePlainWithRule(
            self.id_provider,
            "#uname eq node1",
            {},
            {},
            self.resource_in_clone,
        )
        assert_report_item_list_equal(
            validator.validate({reports.codes.FORCE}),
            [
                fixture.warn(
                    reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                    resource_id="C1R1",
                    parent_type="clone",
                    parent_id="C1",
                )
            ],
        )

    def test_not_resource(self):
        element = self.cib.xpath(".//*[@id='R1-monitor']")[0]
        validator = location.ValidateCreatePlainWithRule(
            self.id_provider, "#uname eq node1", {}, {}, element
        )
        assert_report_item_list_equal(
            validator.validate(),
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R1-monitor",
                    expected_types=sorted(cib_const.TAG_LIST_CONSTRAINABLE),
                    current_type="op",
                )
            ],
        )


class ValidateCreatePlainWithRuleWithoutResource(
    ValidateCreatePlainWithRuleCommonMixin, TestCase
):
    def setUp(self):
        super().setUp()
        self.resource = None


class ValidateAddRuleToConstraintTest(ValidateWithRuleCommonMixin, TestCase):
    def setUp(self):
        self.cib = etree.fromstring(
            """
            <cib>
              <configuration>
                <resources>
                  <primitive id="R1" class="ocf" provider="pacemaker" type="Dummy">
                    <operations>
                      <op id="R1-monitor" name="monitor" interval="60s" />
                    </operations>
                  </primitive>
                </resources>
                <constraints>
                  <rsc_location id="L1" rsc="R1" node="node1" score="123" />
                  <rsc_location id="L2" rsc="R1">
                    <rule id="L2-rule" boolean-op="and" score="0">
                      <expression id="L2-rule-expr"
                          attribute="#uname" operation="eq" value="node3"
                      />
                    </rule>
                  </rsc_location>
                </constraints>
              </configuration>
            </cib>
            """
        )
        self.constraint = self.cib.xpath(".//rsc_location[@id='L1']")[0]
        self.rule_constraint = self.cib.xpath(".//rsc_location[@id='L2']")[0]
        self.id_provider = IdProvider(self.cib)

    def get_validator(
        self,
        id_provider,
        rule_str,
        rule_options,
        constraint_el=None,
    ):
        return location.ValidateAddRuleToConstraint(
            id_provider,
            rule_str,
            rule_options,
            constraint_el if constraint_el is not None else self.constraint,
        )

    def test_add_to_location_constraint(self):
        validator = self.get_validator(
            self.id_provider, "#uname eq node1", {}, self.constraint
        )
        assert_report_item_list_equal(validator.validate(), [])

    def test_add_to_location_constraint_with_rule(self):
        validator = self.get_validator(
            self.id_provider, "#uname eq node1", {}, self.rule_constraint
        )
        assert_report_item_list_equal(validator.validate(), [])

    def test_add_to_element(self):
        element = self.cib.xpath(".//*[@id='R1-monitor']")[0]
        for force_flags in ({}, {reports.codes.FORCE}):
            with self.subTest(force_flags=force_flags):
                validator = self.get_validator(
                    self.id_provider, "#uname eq node1", {}, element
                )
                assert_report_item_list_equal(
                    validator.validate(force_flags),
                    [
                        fixture.error(
                            reports.codes.CANNOT_ADD_RULE_TO_CONSTRAINT_WRONG_TYPE,
                            element_id="R1-monitor",
                            element_type="op",
                        )
                    ],
                )


class CreatePlainWithRule(TestCase):
    @staticmethod
    def fixture_cib(constraint=""):
        return f"""
            <cib>
              <resources>
                <primitive id="R1" class="ocf" provider="pacemaker" type="Dummy" />
              </resources>
              <constraints>{constraint}</constraints>
            </cib>
        """

    @staticmethod
    def run_create_constraint(
        cib,
        resource_id_type,
        resource_id,
        rule_options,
        constraint_options,
        rule="#uname eq node1",
    ):
        element = cib.xpath(".//constraints")[0]
        id_provider = IdProvider(cib)
        rule_tree = parse_rule(rule)
        location.create_plain_with_rule(
            element,
            id_provider,
            const.PCMK_NEW_ROLES_CIB_VERSION,
            resource_id_type,
            resource_id,
            rule_tree,
            rule_options,
            constraint_options,
        )

    def test_minimal_resource(self):
        cib = etree.fromstring(self.fixture_cib())
        cib_expected = self.fixture_cib(
            """
                <rsc_location id="location-R1" rsc="R1">
                  <rule id="location-R1-rule" boolean-op="and" score="INFINITY">
                    <expression id="location-R1-rule-expr"
                        attribute="#uname" operation="eq" value="node1"
                    />
                  </rule>
                </rsc_location>
            """
        )
        self.run_create_constraint(
            cib, const.RESOURCE_ID_TYPE_PLAIN, "R1", {}, {}
        )
        assert_xml_equal(cib_expected, etree_to_str(cib))

    def test_minimal_resource_pattern(self):
        cib = etree.fromstring(self.fixture_cib())
        cib_expected = self.fixture_cib(
            """
                <rsc_location id="location-Rd" rsc-pattern="R\\d+">
                  <rule id="location-Rd-rule" boolean-op="and" score="INFINITY">
                    <expression id="location-Rd-rule-expr"
                        attribute="#uname" operation="eq" value="node1"
                    />
                  </rule>
                </rsc_location>
            """
        )
        self.run_create_constraint(
            cib, const.RESOURCE_ID_TYPE_REGEXP, "R\\d+", {}, {}
        )
        assert_xml_equal(cib_expected, etree_to_str(cib))

    def test_options(self):
        cib = etree.fromstring(self.fixture_cib())
        cib_expected = self.fixture_cib(
            f"""
                <rsc_location id="L1" rsc="R1" resource-discovery="exclusive">
                  <rule id="X1" boolean-op="and" score="123"
                      role="{const.PCMK_ROLE_UNPROMOTED}"
                  >
                    <expression id="X1-expr"
                        attribute="#uname" operation="eq" value="node1"
                    />
                  </rule>
                </rsc_location>
            """
        )
        self.run_create_constraint(
            cib,
            const.RESOURCE_ID_TYPE_PLAIN,
            "R1",
            {"id": "X1", "score": "123", "role": const.PCMK_ROLE_UNPROMOTED},
            {"id": "L1", "resource-discovery": CibResourceDiscovery.EXCLUSIVE},
        )
        assert_xml_equal(cib_expected, etree_to_str(cib))


class AddRuleToConstraint(TestCase):
    @staticmethod
    def fixture_cib_rule_constraint(second_rule=""):
        return f"""
            <constraints>
              <rsc_location id="L1" rsc="R1">
                <rule id="L1-rule" boolean-op="and" score="INFINITY">
                  <expression id="L1-rule-expr"
                    attribute="#uname" operation="eq" value="node1"
                  />
                </rule>{second_rule}
              </rsc_location>
            </constraints>
        """

    @staticmethod
    def fixture_cib_constraint():
        return """
            <constraints>
              <rsc_location id="L1" rsc="R1" node="node1" score="123" />
            </constraints>
        """

    @staticmethod
    def run_add_rule(cib, constraint_id, rule_options, rule="#uname eq node2"):
        element = cib.xpath(".//rsc_location[@id=$id]", id=constraint_id)[0]
        id_provider = IdProvider(cib)
        rule_tree = parse_rule(rule)
        location.add_rule_to_constraint(
            element,
            id_provider,
            const.PCMK_NEW_ROLES_CIB_VERSION,
            rule_tree,
            rule_options,
        )

    def test_minimal(self):
        cib = etree.fromstring(self.fixture_cib_rule_constraint())
        cib_expected = self.fixture_cib_rule_constraint(
            """
                <rule id="L1-rule-1" boolean-op="and" score="INFINITY">
                  <expression id="L1-rule-1-expr"
                      attribute="#uname" operation="eq" value="node2"
                  />
                </rule>
            """
        )
        self.run_add_rule(cib, "L1", {})
        assert_xml_equal(cib_expected, etree_to_str(cib))

    def test_score(self):
        cib = etree.fromstring(self.fixture_cib_rule_constraint())
        cib_expected = self.fixture_cib_rule_constraint(
            """
                <rule id="L1-rule-1" boolean-op="and" score="321">
                  <expression id="L1-rule-1-expr"
                      attribute="#uname" operation="eq" value="node2"
                  />
                </rule>
            """
        )
        self.run_add_rule(cib, "L1", {"score": "321"})
        assert_xml_equal(cib_expected, etree_to_str(cib))

    def test_score_attribute(self):
        cib = etree.fromstring(self.fixture_cib_rule_constraint())
        cib_expected = self.fixture_cib_rule_constraint(
            """
                <rule id="L1-rule-1" boolean-op="and" score-attribute="something">
                  <expression id="L1-rule-1-expr"
                      attribute="#uname" operation="eq" value="node2"
                  />
                </rule>
            """
        )
        self.run_add_rule(cib, "L1", {"score-attribute": "something"})
        assert_xml_equal(cib_expected, etree_to_str(cib))

    def test_role(self):
        cib = etree.fromstring(self.fixture_cib_rule_constraint())
        cib_expected = self.fixture_cib_rule_constraint(
            f"""
                <rule id="L1-rule-1" boolean-op="and" score="INFINITY"
                    role="{const.PCMK_ROLE_PROMOTED}"
                >
                  <expression id="L1-rule-1-expr"
                      attribute="#uname" operation="eq" value="node2"
                  />
                </rule>
            """
        )
        self.run_add_rule(cib, "L1", {"role": const.PCMK_ROLE_PROMOTED})
        assert_xml_equal(cib_expected, etree_to_str(cib))

    def test_custom_id(self):
        cib = etree.fromstring(self.fixture_cib_rule_constraint())
        cib_expected = self.fixture_cib_rule_constraint(
            """
                <rule id="id1" boolean-op="and" score="INFINITY">
                  <expression id="id1-expr"
                      attribute="#uname" operation="eq" value="node2"
                  />
                </rule>
            """
        )
        self.run_add_rule(cib, "L1", {"id": "id1"})
        assert_xml_equal(cib_expected, etree_to_str(cib))

    def test_replace_node_score(self):
        cib = etree.fromstring(self.fixture_cib_constraint())
        cib_expected = self.fixture_cib_rule_constraint()
        self.run_add_rule(cib, "L1", {}, "#uname eq node1")
        assert_xml_equal(cib_expected, etree_to_str(cib))
