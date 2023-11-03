from unittest import TestCase

from lxml import etree

from pcs.lib.commands import cib as lib

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


def _constraints(*argv):
    return f"<constraints>{''.join(argv)}</constraints>"


FIXTURE_LOC_CONSTRAINT_WITH_1_RULE = """
    <rsc_location id="lr1" rsc="A">
        <rule id="r1" boolean-op="and" score="100">
            <expression id="r1e1" operation="eq"
                attribute="#uname" value="node1"/>
            <date_expression id="r1e2" operation="gt"
                start="1970-01-01"/>
        </rule>
    </rsc_location>
"""

FIXTURE_LOC_CONSTRAINT_WITH_2_RULES = """
    <rsc_location id="lr2" rsc="B">
        <rule id="r2" score="-INFINITY" >
            <expression id="r2e1" attribute="pingd"
                operation="lt" value="3000"/>
        </rule>
        <rule id="r3" score-attribute="pingd" >
            <expression id="r3e1" attribute="pingd"
                operation="defined"/>
        </rule>
    </rsc_location>
"""

FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES = _constraints(
    FIXTURE_LOC_CONSTRAINT_WITH_1_RULE,
    FIXTURE_LOC_CONSTRAINT_WITH_2_RULES,
)

EXPECTED_TYPES_FOR_REMOVE = ["constraint", "location rule"]


class RemoveElements(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_ids_not_found(self):
        self.config.runner.cib.load()
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(),
                ["missing-id1", "missing-id2"],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_not_found(
                    _id, expected_types=["configuration element"]
                )
                for _id in ["missing-id1", "missing-id2"]
            ]
        )

    def test_not_constraints_ids(self):
        self.config.runner.cib.load(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <clone id="B">
                        <primitive id="C"/>
                    </clone>
                </resources>
            """,
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["A", "B", "C"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_unexpected_element(
                    "A", "primitive", EXPECTED_TYPES_FOR_REMOVE
                ),
                fixture.report_unexpected_element(
                    "B", "clone", EXPECTED_TYPES_FOR_REMOVE
                ),
                fixture.report_unexpected_element(
                    "C", "primitive", EXPECTED_TYPES_FOR_REMOVE
                ),
            ]
        )

    def test_duplicate_ids_specified(self):
        self.config.runner.cib.load(
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="A" node="node1" score="200"/>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                </constraints>
            """
        )
        self.config.env.push_cib(
            constraints="""
                <constraints>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                </constraints>
            """
        )
        lib.remove_elements(self.env_assist.get_env(), ["l1", "l1"])

    def test_remove_location_constraint(self):
        self.config.runner.cib.load(
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="A" node="node1" score="200"/>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                </constraints>
            """
        )
        self.config.env.push_cib(
            constraints="""
                <constraints>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                </constraints>
            """
        )
        lib.remove_elements(self.env_assist.get_env(), ["l1"])

    def test_remove_order_constraint(self):
        self.config.runner.cib.load(
            constraints="""
                <constraints>
                    <rsc_order id="o1" first="A" then="B"/>
                    <rsc_order id="o2" first="A" then="B"/>
                </constraints>
            """
        )
        self.config.env.push_cib(
            constraints="""
                <constraints>
                    <rsc_order id="o1" first="A" then="B"/>
                </constraints>
            """
        )
        lib.remove_elements(self.env_assist.get_env(), ["o2"])

    def test_remove_colocation_constraints(self):
        self.config.runner.cib.load(
            constraints="""
                <constraints>
                    <rsc_colocation id="c1" rsc="A" with-rsc="B" score="100"/>
                    <rsc_colocation id="c2" rsc="A" with-rsc="B" score="100"/>
                </constraints>
            """
        )
        self.config.env.push_cib(constraints="<constraints/>")
        lib.remove_elements(self.env_assist.get_env(), ["c1", "c2"])

    def test_remove_ticket_constraints(self):
        self.config.runner.cib.load(
            constraints="""
                <constraints>
                    <rsc_ticket id="t1" ticket="T" rsc="A"/>
                    <rsc_ticket id="t2" ticket="T" rsc="B"/>
                </constraints>
            """
        )
        self.config.env.push_cib(constraints="<constraints/>")
        lib.remove_elements(self.env_assist.get_env(), ["t1", "t2"])

    def test_remove_location_constraint_with_one_rule_by_id(self):
        self.config.runner.cib.load(
            constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES
        )
        self.config.env.push_cib(
            constraints=_constraints(FIXTURE_LOC_CONSTRAINT_WITH_2_RULES)
        )
        lib.remove_elements(self.env_assist.get_env(), ["lr1"])

    def test_remove_location_constraint_with_more_rules_by_id(self):
        self.config.runner.cib.load(
            constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES
        )
        self.config.env.push_cib(
            constraints=_constraints(FIXTURE_LOC_CONSTRAINT_WITH_1_RULE)
        )
        lib.remove_elements(self.env_assist.get_env(), ["lr2"])

    def test_remove_one_rule_from_location_constraint_with_one_rule(self):
        self.config.runner.cib.load(
            constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES
        )
        self.config.env.push_cib(
            constraints=_constraints(FIXTURE_LOC_CONSTRAINT_WITH_2_RULES)
        )
        lib.remove_elements(self.env_assist.get_env(), ["r1"])

    def test_remove_one_rule_from_location_constraint_with_two_rules(self):
        self.config.runner.cib.load(
            constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES
        )
        self.config.env.push_cib(
            constraints="""
                <constraints>
                    <rsc_location id="lr1" rsc="A">
                        <rule id="r1" boolean-op="and" score="100">
                            <expression id="r1e1" operation="eq"
                                attribute="#uname" value="node1"/>
                            <date_expression id="r1e2" operation="gt"
                                start="1970-01-01"/>
                        </rule>
                    </rsc_location>
                    <rsc_location id="lr2" rsc="B">
                        <rule id="r3" score-attribute="pingd" >
                            <expression id="r3e1" attribute="pingd"
                                operation="defined"/>
                        </rule>
                    </rsc_location>
                </constraints>
            """
        )
        lib.remove_elements(self.env_assist.get_env(), ["r2"])

    def test_remove_more_location_rules(self):
        self.config.runner.cib.load(
            constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES
        )
        self.config.env.push_cib(constraints="<constraints/>")
        lib.remove_elements(self.env_assist.get_env(), ["r1", "r2", "r3"])

    def test_remove_location_rule_expressions(self):
        self.config.runner.cib.load(
            constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES
        )
        self.env_assist.assert_raise_library_error(
            lambda: lib.remove_elements(
                self.env_assist.get_env(), ["r1e1", "r1e2"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.report_unexpected_element(
                    "r1e1", "expression", EXPECTED_TYPES_FOR_REMOVE
                ),
                fixture.report_unexpected_element(
                    "r1e2", "date_expression", EXPECTED_TYPES_FOR_REMOVE
                ),
            ]
        )


class GetInnerReferences(TestCase):
    # pylint: disable=protected-access
    def test_no_inner_references(self):
        self.assertEqual(
            [], lib._get_inner_references(etree.fromstring("<A/>"))
        )

    def test_inner_references(self):
        element = etree.fromstring(
            """
            <A>
                <a id="1">
                    <a id="11"/>
                    <a id="12"/>
                </a>
                <b id="2"/>
                <c/>
            </A>
            """
        )
        expected_elements = [
            element.find("./a[@id='1']"),
            element.find("./b[@id='2']"),
        ]
        self.assertEqual(expected_elements, lib._get_inner_references(element))


class IsLastElement(TestCase):
    # pylint: disable=protected-access
    def test_last_element_true(self):
        for element, tag in (
            (etree.fromstring("<A><a/></A>"), "a"),
            (etree.fromstring("<A><a/><b/><c/></A>"), "a"),
        ):
            with self.subTest(element=element, tag=tag):
                self.assertTrue(lib._is_last_element(element, tag))

    def test_last_element_false(self):
        for element, tag in (
            (etree.fromstring("<A/>"), "a"),
            (etree.fromstring("<A> <a/> <a/> </A>"), "a"),
            (etree.fromstring("<A><A> <a/> </A></A>"), "a"),
        ):
            with self.subTest(element=element, tag=tag):
                self.assertFalse(lib._is_last_element(element, tag))


class IsEmptyAfterInnerElRemoval(TestCase):
    # pylint: disable=protected-access
    def test_last_element_true(self):
        for parent in (
            etree.fromstring("<bundle/>"),
            etree.fromstring("<bundle><primitive/></bundle>"),
            etree.fromstring("<clone/>"),
            etree.fromstring("<clone><primitive/></clone>"),
            etree.fromstring("<group><primitive/></group>"),
            etree.fromstring("<tag><obj_ref/></tag>"),
            etree.fromstring("<resource_set><resource_ref/></resource_set>"),
            etree.fromstring("<element><resource_set/></element>"),
            etree.fromstring("<rsc_location><rule/></rsc_location>"),
        ):
            with self.subTest(parent=parent):
                self.assertTrue(lib._is_empty_after_inner_el_removal(parent))

    def test_last_element_false(self):
        for parent in (
            etree.fromstring("<primitive/>"),
            etree.fromstring("<group/>"),
            etree.fromstring("<group><primitive/><primitive/></group>"),
            etree.fromstring("<tag/>"),
            etree.fromstring("<tag><obj_ref/><obj_ref/></tag>"),
            etree.fromstring(
                """
                <resource_set>
                    <resource_ref/>
                    <resource_ref/>
                </resource_set>
               """
            ),
            etree.fromstring("<resource_set/>"),
            etree.fromstring(
                "<element><resource_set/><resource_set/></element>"
            ),
            etree.fromstring(
                """
                <element>
                    <resource_set/>
                    <resource_set/>"
                </element>
                """
            ),
            etree.fromstring("<rsc_location><rule/><rule/></rsc_location>"),
            etree.fromstring("<rsc_location/>"),
        ):
            with self.subTest(parent=parent):
                self.assertFalse(lib._is_empty_after_inner_el_removal(parent))
