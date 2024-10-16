# pylint: disable=too-many-lines
from typing import Optional
from unittest import (
    TestCase,
    mock,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common import reports
from pcs.lib.cib import const
from pcs.lib.cib import remove_elements as lib

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.fixture_cib import modify_cib
from pcs_test.tools.fixture_crm_mon import complete_state
from pcs_test.tools.misc import read_test_resource
from pcs_test.tools.xml import etree_to_str


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

EXPECTED_TYPES_FOR_REMOVE = ["constraint", "location rule", "resource"]


def fixture_primitive_to_disable(cib: _Element) -> list[_Element]:
    return [cib.find("./configuration/resources/primitive[@id='A']")]


FIXTURE_GROUP = """
    <group id="G">
        <primitive id="A"/>
        <primitive id="B"/>
    </group>
"""


def fixture_group_to_disable(cib: _Element) -> list[_Element]:
    return [
        cib.find("./configuration/resources/group[@id='G']/primitive[@id='A']"),
        cib.find("./configuration/resources/group[@id='G']/primitive[@id='B']"),
        cib.find("./configuration/resources/group[@id='G']"),
    ]


FIXTURE_CLONE = """
    <clone id="C">
        <primitive id="A"/>
    </clone>
"""


def fixture_clone_to_disable(cib: _Element) -> list[_Element]:
    return [
        cib.find("./configuration/resources/clone[@id='C']/primitive[@id='A']"),
        cib.find("./configuration/resources/clone[@id='C']"),
    ]


class GetCibMixin:
    def get_cib(self, **modifier_shortcuts):
        return etree.fromstring(modify_cib(self.cib, **modifier_shortcuts))


class ElementsToRemoveFindElements(TestCase, GetCibMixin):
    # pylint: disable=too-many-public-methods
    def setUp(self):
        self.cib = read_test_resource("cib-empty.xml")

    def assert_elements_to_remove(
        self,
        elements_to_remove: lib.ElementsToRemove,
        ids_to_remove: set[str],
        resources_to_disable: Optional[list[etree._Element]] = None,
        dependant_elements: lib.DependantElements = lib.DependantElements({}),
        element_references: lib.ElementReferences = lib.ElementReferences(
            {}, {}
        ),
        missing_ids: Optional[set[str]] = None,
        unsupported_elements: lib.UnsupportedElements = lib.UnsupportedElements(
            {}, EXPECTED_TYPES_FOR_REMOVE
        ),
    ):
        self.assertEqual(elements_to_remove.ids_to_remove, ids_to_remove)
        self.assertEqual(
            elements_to_remove.resources_to_disable,
            resources_to_disable or [],
        )
        self.assertEqual(
            elements_to_remove.dependant_elements, dependant_elements
        )
        self.assertEqual(
            elements_to_remove.element_references, element_references
        )
        self.assertEqual(elements_to_remove.missing_ids, missing_ids or set())
        self.assertEqual(
            elements_to_remove.unsupported_elements, unsupported_elements
        )

    def test_location_constraint(self):
        cib = self.get_cib(
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="A" node="node1" score="200"/>
                    <rsc_location id="l2" rsc="A" node="node2" score="100"/>
                </constraints>
            """
        )

        elements_to_remove = lib.ElementsToRemove(cib, ["l1"])
        self.assert_elements_to_remove(elements_to_remove, {"l1"})

    def test_order_constraint(self):
        cib = self.get_cib(
            constraints="""
                <constraints>
                    <rsc_order id="o1" first="A" then="B"/>
                    <rsc_order id="o2" first="A" then="B"/>
                </constraints>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["o2"])
        self.assert_elements_to_remove(elements_to_remove, {"o2"})

    def test_colocation_constraints(self):
        cib = self.get_cib(
            constraints="""
                <constraints>
                    <rsc_colocation id="c1" rsc="A" with-rsc="B" score="100"/>
                    <rsc_colocation id="c2" rsc="A" with-rsc="B" score="100"/>
                </constraints>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["c1", "c2"])
        self.assert_elements_to_remove(elements_to_remove, {"c1", "c2"})

    def test_ticket_constraints(self):
        cib = self.get_cib(
            constraints="""
                <constraints>
                    <rsc_ticket id="t1" ticket="T" rsc="A"/>
                    <rsc_ticket id="t2" ticket="T" rsc="B"/>
                </constraints>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["t1", "t2"])
        self.assert_elements_to_remove(elements_to_remove, {"t1", "t2"})

    def test_location_constraint_with_one_rule_by_id(self):
        cib = self.get_cib(constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES)
        elements_to_remove = lib.ElementsToRemove(cib, ["lr1"])
        self.assert_elements_to_remove(elements_to_remove, {"lr1"})

    def test_location_constraint_with_more_rules_by_id(self):
        cib = self.get_cib(constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES)
        elements_to_remove = lib.ElementsToRemove(cib, ["lr2"])
        self.assert_elements_to_remove(elements_to_remove, {"lr2"})

    def test_one_rule_from_location_constraint_with_one_rule(self):
        cib = self.get_cib(constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES)
        elements_to_remove = lib.ElementsToRemove(cib, ["r1"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"lr1", "r1"},
            dependant_elements=lib.DependantElements(
                {"lr1": const.TAG_CONSTRAINT_LOCATION}
            ),
        )

    def test_one_rule_from_location_constraint_with_two_rules(self):
        cib = self.get_cib(constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES)
        elements_to_remove = lib.ElementsToRemove(cib, ["r2"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"r2"},
            element_references=lib.ElementReferences(
                {"r2": {"lr2"}},
                {
                    "lr2": const.TAG_CONSTRAINT_LOCATION,
                    "r2": const.TAG_RULE,
                },
            ),
        )

    def test_more_location_rules(self):
        cib = self.get_cib(constraints=FIXTURE_TWO_LOC_CONSTRAINTS_WITH_RULES)
        elements_to_remove = lib.ElementsToRemove(cib, ["r1", "r2", "r3"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"r1", "r2", "r3", "lr1", "lr2"},
            dependant_elements=lib.DependantElements(
                {
                    "lr1": const.TAG_CONSTRAINT_LOCATION,
                    "lr2": const.TAG_CONSTRAINT_LOCATION,
                }
            ),
        )

    def test_resource_primitive(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A"},
            resources_to_disable=fixture_primitive_to_disable(cib),
        )

    def test_resource_primitive_in_tag(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """,
            tags="""
                <tags>
                    <tag id="T1">
                        <obj_ref id="A"/>
                        <obj_ref id="B"/>
                    </tag>
                    <tag id="T2">
                        <obj_ref id="A"/>
                    </tag>
                </tags>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A", "T2"},
            resources_to_disable=fixture_primitive_to_disable(cib),
            dependant_elements=lib.DependantElements({"T2": const.TAG_TAG}),
            element_references=lib.ElementReferences(
                {"A": {"T1"}},
                {"A": const.TAG_RESOURCE_PRIMITIVE, "T1": const.TAG_TAG},
            ),
        )

    def test_resource_primitive_constraints(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="A" node="node1" score="200"/>
                    <rsc_order id="o1" first="A" then="B"/>
                    <rsc_colocation id="c1" rsc="A" with-rsc="B" score="100"/>
                    <rsc_ticket id="t1" ticket="T" rsc="A"/>
                    <rsc_location id="l2" rsc="B" node="node1" score="200"/>
                </constraints>
            """,
        )

        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A", "l1", "o1", "c1", "t1"},
            resources_to_disable=fixture_primitive_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {
                    "l1": const.TAG_CONSTRAINT_LOCATION,
                    "o1": const.TAG_CONSTRAINT_ORDER,
                    "c1": const.TAG_CONSTRAINT_COLOCATION,
                    "t1": const.TAG_CONSTRAINT_TICKET,
                }
            ),
        )

    def test_resource_group(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_GROUP}
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["G"])

        self.assert_elements_to_remove(
            elements_to_remove,
            {"G", "A", "B"},
            resources_to_disable=fixture_group_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "B": const.TAG_RESOURCE_PRIMITIVE,
                }
            ),
        )

    def test_resource_group_member(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_GROUP}
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])

        self.assert_elements_to_remove(
            elements_to_remove,
            {"A"},
            resources_to_disable=[
                cib.find("./configuration/resources/group/primitive[@id='A']"),
            ],
            element_references=lib.ElementReferences(
                {"A": {"G"}},
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "G": const.TAG_RESOURCE_GROUP,
                },
            ),
        )

    def test_resource_group_all_members(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_GROUP}
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A", "B"])

        self.assert_elements_to_remove(
            elements_to_remove,
            {"A", "B", "G"},
            resources_to_disable=fixture_group_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {"G": const.TAG_RESOURCE_GROUP}
            ),
        )

    def test_resource_group_constraints(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_GROUP}
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="G" node="node1" score="200"/>
                    <rsc_order id="o1" first="A" then="B"/>
                    <rsc_colocation id="c1" rsc="A" with-rsc="B" score="100"/>
                    <rsc_ticket id="t1" ticket="T" rsc="B"/>
                    <rsc_location id="l2" rsc="X" node="node1" score="200"/>
                </constraints>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["G"])

        self.assert_elements_to_remove(
            elements_to_remove,
            {"G", "A", "B", "l1", "o1", "c1", "t1"},
            resources_to_disable=fixture_group_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "B": const.TAG_RESOURCE_PRIMITIVE,
                    "l1": const.TAG_CONSTRAINT_LOCATION,
                    "o1": const.TAG_CONSTRAINT_ORDER,
                    "c1": const.TAG_CONSTRAINT_COLOCATION,
                    "t1": const.TAG_CONSTRAINT_TICKET,
                }
            ),
        )

    def test_group_in_tag(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_GROUP}
                </resources>
            """,
            tags="""
                <tags>
                    <tag id="T">
                        <obj_ref id="G"/>
                        <obj_ref id="B"/>
                    </tag>
                </tags>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["G"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"G", "A", "B", "T"},
            resources_to_disable=fixture_group_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "B": const.TAG_RESOURCE_PRIMITIVE,
                    "T": const.TAG_TAG,
                }
            ),
        )

    def test_resource_clone(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_CLONE}
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["C"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"C", "A"},
            resources_to_disable=fixture_clone_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {"A": const.TAG_RESOURCE_PRIMITIVE}
            ),
        )

    def test_resource_clone_primitive(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_CLONE}
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])

        self.assert_elements_to_remove(
            elements_to_remove,
            {"C", "A"},
            resources_to_disable=fixture_clone_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {"C": const.TAG_RESOURCE_CLONE}
            ),
        )

    def test_resource_clone_constraints(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_CLONE}
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="C" node="node1" score="100"/>
                    <rsc_location id="l2" rsc="A" node="node2" score="200"/>
                    <rsc_location id="l3" rsc="X" node="node2" score="200"/>
                </constraints>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["C"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"C", "A", "l1", "l2"},
            resources_to_disable=fixture_clone_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "l1": const.TAG_CONSTRAINT_LOCATION,
                    "l2": const.TAG_CONSTRAINT_LOCATION,
                }
            ),
        )

    def test_resource_clone_in_tag(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_CLONE}
                </resources>
            """,
            tags="""
                <tags>
                    <tag id="T">
                        <obj_ref id="C"/>
                        <obj_ref id="A"/>
                    </tag>
                </tags>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["C"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"C", "A", "T"},
            resources_to_disable=fixture_clone_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {"A": const.TAG_RESOURCE_PRIMITIVE, "T": const.TAG_TAG}
            ),
        )

    def test_resource_bundle(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <bundle id="B"/>
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["B"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"B"},
            resources_to_disable=[
                cib.find("./configuration/resources/bundle[@id='B']")
            ],
        )

    def test_resource_bundle_with_primitive(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <bundle id="B">
                        <primitive id="A"/>
                    </bundle>
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["B"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"B", "A"},
            resources_to_disable=[
                cib.find("./configuration/resources/bundle/primitive[@id='A']"),
                cib.find("./configuration/resources/bundle[@id='B']"),
            ],
            dependant_elements=lib.DependantElements(
                {"A": const.TAG_RESOURCE_PRIMITIVE}
            ),
        )

    def test_resource_bundle_primitive(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <bundle id="B">
                        <primitive id="A"/>
                    </bundle>
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A"},
            resources_to_disable=[
                cib.find("./configuration/resources/bundle/primitive[@id='A']")
            ],
            element_references=lib.ElementReferences(
                {"A": {"B"}},
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "B": const.TAG_RESOURCE_BUNDLE,
                },
            ),
        )

    def test_resource_referenced_in_acl(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="vohrablo"/>
                </resources>
            """,
            optional_in_conf="""
                <acls>
                    <acl_role id="zenich">
                        <acl_permission id="ucesat_se1" kind="read" reference="hreben"/>
                        <acl_permission id="ucesat_se2" kind="read" reference="vohrablo"/>
                    </acl_role>
                    <acl_target id="Jirka Kara">
                        <role id="zenich"/>
                    </acl_target>
                </acls>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["vohrablo"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"vohrablo", "ucesat_se2"},
            resources_to_disable=[
                cib.find("./configuration/resources/primitive[@id='vohrablo']")
            ],
            dependant_elements=lib.DependantElements(
                {"ucesat_se2": const.TAG_ACL_PERMISSION}
            ),
            element_references=lib.ElementReferences(
                {"ucesat_se2": {"zenich"}},
                {
                    "ucesat_se2": const.TAG_ACL_PERMISSION,
                    "zenich": const.TAG_ACL_ROLE,
                },
            ),
        )

    def test_resource_referenced_in_acl_indirectly(self):
        cib = self.get_cib(
            resources=f"""
                <resources>
                    {FIXTURE_GROUP}
                </resources>
            """,
            optional_in_conf="""
                <acls>
                    <acl_role id="ROLE">
                        <acl_permission id="PERMISSION" kind="write" reference="A"/>
                    </acl_role>
                    <acl_target id="OtaZnicek">
                        <role id="ROLE"/>
                    </acl_target>
                </acls>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["G"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"G", "A", "B", "PERMISSION"},
            resources_to_disable=fixture_group_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "B": const.TAG_RESOURCE_PRIMITIVE,
                    "PERMISSION": const.TAG_ACL_PERMISSION,
                }
            ),
            element_references=lib.ElementReferences(
                {"PERMISSION": {"ROLE"}},
                {
                    "PERMISSION": const.TAG_ACL_PERMISSION,
                    "ROLE": const.TAG_ACL_ROLE,
                },
            ),
        )

    def test_resource_keep_fencing_level(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """,
            fencing_topology="""
                <fencing-topology>
                    <fencing-level index="2" devices="A,B" target="NODE-A" id="fl"/>
                </fencing-topology>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A"},
            resources_to_disable=fixture_primitive_to_disable(cib),
            element_references=lib.ElementReferences(
                {"A": {"fl"}},
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "fl": const.TAG_FENCING_LEVEL,
                },
            ),
        )

    def test_resource_remove_fencing_level(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """,
            fencing_topology="""
                <fencing-topology>
                    <fencing-level index="1" devices="A" target="NODE-A" id="fl-NODE-A-1"/>
                </fencing-topology>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A", "fl-NODE-A-1"},
            resources_to_disable=fixture_primitive_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {"fl-NODE-A-1": const.TAG_FENCING_LEVEL}
            ),
        )

    def test_resource_in_constraint_set(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_colocation score="-1" id="c1">
                        <resource_set role="Started" id="set1">
                            <resource_ref id="A"/>
                            <resource_ref id="B"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A"},
            resources_to_disable=fixture_primitive_to_disable(cib),
            element_references=lib.ElementReferences(
                {"A": {"set1"}},
                {
                    "A": const.TAG_RESOURCE_PRIMITIVE,
                    "set1": const.TAG_RESOURCE_SET,
                },
            ),
        )

    def test_resource_in_constraint_set_remove_set_keep_constraint(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_colocation score="-1" id="c1">
                        <resource_set role="Started" id="set1">
                            <resource_ref id="A"/>
                        </resource_set>
                        <resource_set sequential="false" id="set2">
                            <resource_ref id="B"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A", "set1"},
            resources_to_disable=fixture_primitive_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {"set1": const.TAG_RESOURCE_SET}
            ),
            element_references=lib.ElementReferences(
                {"set1": {"c1"}},
                {
                    "set1": const.TAG_RESOURCE_SET,
                    "c1": const.TAG_CONSTRAINT_COLOCATION,
                },
            ),
        )

    def test_resource_in_constraint_set_remove_set_remove_constraint(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_colocation score="-1" id="c1">
                        <resource_set role="Started" id="set1">
                            <resource_ref id="A"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A", "set1", "c1"},
            resources_to_disable=fixture_primitive_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {
                    "set1": const.TAG_RESOURCE_SET,
                    "c1": const.TAG_CONSTRAINT_COLOCATION,
                }
            ),
        )

    def test_resource_in_multiple_sets(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_colocation score="-1" id="c1">
                        <resource_set role="Started" id="set1">
                            <resource_ref id="A"/>
                        </resource_set>
                    </rsc_colocation>
                    <rsc_colocation score="1" id="c2">
                        <resource_set role="Started" id="set2">
                            <resource_ref id="A"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A", "set1", "c1", "set2", "c2"},
            resources_to_disable=fixture_primitive_to_disable(cib),
            dependant_elements=lib.DependantElements(
                {
                    "set1": const.TAG_RESOURCE_SET,
                    "c1": const.TAG_CONSTRAINT_COLOCATION,
                    "set2": const.TAG_RESOURCE_SET,
                    "c2": const.TAG_CONSTRAINT_COLOCATION,
                }
            ),
        )

    def test_resource_legacy_promotable_clone(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <master id="MS">
                        <primitive id="A"/>
                    </master>
                </resources>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["MS"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"MS", "A"},
            resources_to_disable=[
                cib.find("./configuration/resources/master/primitive[@id='A']"),
                cib.find("./configuration/resources/master/[@id='MS']"),
            ],
            dependant_elements=lib.DependantElements(
                {"A": const.TAG_RESOURCE_PRIMITIVE}
            ),
        )

    def test_resource_legacy_promotable_clone_inner_element(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <master id="MS">
                        <primitive id="A"/>
                    </master>
                </resources>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A", "MS"},
            resources_to_disable=[
                cib.find("./configuration/resources/master/primitive[@id='A']"),
                cib.find("./configuration/resources/master/[@id='MS']"),
            ],
            dependant_elements=lib.DependantElements({"MS": "master"}),
        )

    def test_missing_elements(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["A", "B", "C", "D"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"A"},
            missing_ids={"B", "C", "D"},
            resources_to_disable=fixture_primitive_to_disable(cib),
        )

    def test_unsupported_id_types(self):
        cib = self.get_cib(
            tags="""
                <tags>
                    <tag id="T">
                        <obj_ref id="A"/>
                    </tag>
                </tags>
            """,
            fencing_topology="""
                <fencing-topology>
                    <fencing-level index="1" devices="A" target="NODE-A" id="fl"/>
                </fencing-topology>
            """,
            optional_in_conf="""
                <acls>
                    <acl_role id="role">
                        <acl_permission id="role-read" kind="read" reference="A"/>
                    </acl_role>
                </acls>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(
            cib, ["T", "fl", "role", "role-read"]
        )
        self.assert_elements_to_remove(
            elements_to_remove,
            set(),
            unsupported_elements=lib.UnsupportedElements(
                {
                    "T": const.TAG_TAG,
                    "fl": const.TAG_FENCING_LEVEL,
                    "role": const.TAG_ACL_ROLE,
                    "role-read": const.TAG_ACL_PERMISSION,
                },
                EXPECTED_TYPES_FOR_REMOVE,
            ),
        )

    def test_remote_guest_node_name_constraint(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="R1">
                        <meta_attributes id="meta">
                            <nvpair id="meta-remote-node" name="remote-node" value="guest"/>
                        </meta_attributes>
                    </primitive>
                    <primitive id="R2" class="ocf" provider="pacemaker" type="remote"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="l1" rsc="C" node="guest" score="100"/>
                    <rsc_location id="l2" rsc="C" node="R2" score="100"/>
                    <rsc_location id="l3" rsc="C" node="node" score="100"/>
                </constraints>
            """,
        )
        elements_to_remove = lib.ElementsToRemove(cib, ["R1", "R2"])
        self.assert_elements_to_remove(
            elements_to_remove,
            {"R1", "R2", "l1", "l2"},
            resources_to_disable=[
                cib.find("./configuration/resources/primitive[@id='R1']"),
                cib.find("./configuration/resources/primitive[@id='R2']"),
            ],
            dependant_elements=lib.DependantElements(
                {"l1": "rsc_location", "l2": "rsc_location"}
            ),
        )


class RemoveSpecifiedElements(TestCase, GetCibMixin):
    def setUp(self):
        self.elements_to_remove_mock = mock.Mock()
        self.elements_to_remove_mock.ids_to_remove = set()
        self.elements_to_remove_mock.element_references = lib.ElementReferences(
            {}, {}
        )
        self.cib = read_test_resource("cib-empty.xml")

    def test_remove_nothing_to_remove(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <clone id="C">
                        <primitive id="C-1"/>
                    </clone>
                    <primitive id="X"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="B"/>
                    <rsc_location id="Y"/>
                </constraints>
            """,
            tags="""
                <tags>
                    <tag id="D"/>
                    <tag id="Z"/>
                </tags>
            """,
        )

        initial_cib = etree_to_str(cib)

        lib.remove_specified_elements(cib, self.elements_to_remove_mock)

        assert_xml_equal(initial_cib, etree_to_str(cib))

    def test_remove_only_by_id(self):
        self.elements_to_remove_mock.ids_to_remove = {"A", "B", "C", "D"}

        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <clone id="C">
                        <primitive id="C-1"/>
                    </clone>
                    <primitive id="X"/>
                </resources>
            """,
            constraints="""
                <constraints>
                    <rsc_location id="B"/>
                    <rsc_location id="Y"/>
                </constraints>
            """,
            tags="""
                <tags>
                    <tag id="D"/>
                    <tag id="Z"/>
                </tags>
            """,
        )

        lib.remove_specified_elements(cib, self.elements_to_remove_mock)

        assert_xml_equal(
            modify_cib(
                self.cib,
                resources="""
                    <resources>
                        <primitive id="X"/>
                    </resources>
                """,
                constraints="""
                    <constraints>
                        <rsc_location id="Y"/>
                    </constraints>
                """,
                tags="""
                    <tags>
                        <tag id="Z"/>
                    </tags>
                """,
            ),
            etree_to_str(cib),
        )

    def test_remove_reference_from_tag(self):
        self.elements_to_remove_mock.element_references = lib.ElementReferences(
            {"A": {"T1"}},
            {"A": const.TAG_RESOURCE_PRIMITIVE, "T1": const.TAG_TAG},
        )

        cib = self.get_cib(
            tags="""
                <tags>
                    <tag id="T1">
                        <obj_ref id="A"/>
                        <obj_ref id="B"/>
                    </tag>
                    <tag id="T2">
                        <obj_ref id="A"/>
                        <obj_ref id="B"/>
                    </tag>
                </tags>
            """,
        )

        lib.remove_specified_elements(cib, self.elements_to_remove_mock)

        assert_xml_equal(
            modify_cib(
                self.cib,
                tags="""
                    <tags>
                        <tag id="T1">
                            <obj_ref id="B"/>
                        </tag>
                        <tag id="T2">
                            <obj_ref id="A"/>
                            <obj_ref id="B"/>
                        </tag>
                    </tags>
                """,
            ),
            etree_to_str(cib),
        )

    def test_remove_reference_from_resource_set(self):
        self.elements_to_remove_mock.element_references = lib.ElementReferences(
            {"A": {"set1"}},
            {
                "A": const.TAG_RESOURCE_PRIMITIVE,
                "set1": const.TAG_RESOURCE_SET,
            },
        )

        cib = self.get_cib(
            constraints="""
                <constraints>
                    <rsc_colocation score="-1" id="c1">
                        <resource_set role="Started" id="set1">
                            <resource_ref id="A"/>
                            <resource_ref id="B"/>
                        </resource_set>
                    </rsc_colocation>
                    <rsc_colocation score="1" id="c2">
                        <resource_set role="Started" id="set2">
                            <resource_ref id="A"/>
                            <resource_ref id="B"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """,
        )

        lib.remove_specified_elements(cib, self.elements_to_remove_mock)

        assert_xml_equal(
            modify_cib(
                self.cib,
                constraints="""
                    <constraints>
                        <rsc_colocation score="-1" id="c1">
                            <resource_set role="Started" id="set1">
                                <resource_ref id="B"/>
                            </resource_set>
                        </rsc_colocation>
                        <rsc_colocation score="1" id="c2">
                            <resource_set role="Started" id="set2">
                                <resource_ref id="A"/>
                                <resource_ref id="B"/>
                            </resource_set>
                        </rsc_colocation>
                    </constraints>
                """,
            ),
            etree_to_str(cib),
        )

    def test_remove_references_from_fencing_level(self):
        self.elements_to_remove_mock.element_references = lib.ElementReferences(
            {"A": {"FL1"}},
            {"A": const.TAG_RESOURCE_PRIMITIVE, "FL1": const.TAG_FENCING_LEVEL},
        )

        cib = self.get_cib(
            fencing_topology="""
                <fencing-topology>
                    <fencing-level index="1" devices="A,B" target="NODE-A" id="FL1"/>
                    <fencing-level index="2" devices="A,B" target="NODE-A" id="FL2"/>
                </fencing-topology>
            """,
        )

        lib.remove_specified_elements(cib, self.elements_to_remove_mock)

        assert_xml_equal(
            modify_cib(
                self.cib,
                fencing_topology="""
                    <fencing-topology>
                        <fencing-level index="1" devices="B" target="NODE-A" id="FL1"/>
                        <fencing-level index="2" devices="A,B" target="NODE-A" id="FL2"/>
                    </fencing-topology>
                """,
            ),
            etree_to_str(cib),
        )

    def test_remove_references_from_ignored_type(self):
        self.elements_to_remove_mock.element_references = lib.ElementReferences(
            {"A": {"G"}},
            {"A": const.TAG_RESOURCE_PRIMITIVE, "G": const.TAG_RESOURCE_GROUP},
        )

        cib = self.get_cib(
            resources="""
                <resources>
                    <group id="G">
                        <primitive id="A"/>
                    </group>
                </resources>
            """,
        )

        initial_cib = etree_to_str(cib)

        lib.remove_specified_elements(cib, self.elements_to_remove_mock)

        assert_xml_equal(initial_cib, etree_to_str(cib))


class WarnResourcesUnmanaged(TestCase):
    def setUp(self):
        self.state = read_test_resource("crm_mon.minimal.xml")

    def test_no_reports(self):
        state = complete_state(
            self.state,
            resources_xml="""
                <resources>
                    <resource id="A" managed="true" role="Stopped"/>
                    <resource id="B" managed="true" role="Stopped"/>
                    <resource id="C" managed="true" role="Stopped"/>
                    <resource id="D" managed="false" role="Stopped"/>
                </resources>
            """,
        )

        assert_report_item_list_equal(
            lib.warn_resource_unmanaged(state, ["A", "B", "C"]), []
        )

    def test_unmanaged(self):
        state = complete_state(
            self.state,
            resources_xml="""
                <resources>
                    <resource id="A" managed="true" role="Stopped"/>
                    <resource id="B" managed="false" role="Stopped"/>
                    <resource id="C" managed="false" role="Stopped"/>
                    <resource id="D" managed="false" role="Stopped"/>
                </resources>
            """,
        )

        assert_report_item_list_equal(
            lib.warn_resource_unmanaged(state, ["A", "B", "C"]),
            [
                fixture.warn(
                    reports.codes.RESOURCE_IS_UNMANAGED, resource_id="B"
                ),
                fixture.warn(
                    reports.codes.RESOURCE_IS_UNMANAGED, resource_id="C"
                ),
            ],
        )

    def test_works_with_bundle_in_status(self):
        state = complete_state(
            self.state,
            resources_xml="""
            <resources>
                <bundle id="BUNDLE" type="podman" image="localhost/pcmktest:http" unique="false" maintenance="false" managed="true" failed="false">
                    <replica id="0">
                        <resource id="BUNDLE-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Stopped"/>
                        <resource id="A" role="Stopped"/>
                        <resource id="BUNDLE-podman-0" resource_agent="ocf:heartbeat:podman" role="Stopped"/>
                        <resource id="BUNDLE-0" resource_agent="ocf:pacemaker:remote" role="Stopped"/>
                    </replica>
                </bundle>
                <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                    <resource id="B" role="Stopped" managed="true"/>
                </clone>
            </resources>
        """,
        )

        assert_report_item_list_equal(
            lib.warn_resource_unmanaged(state, ["A", "B"]), []
        )


class StopResources(TestCase, GetCibMixin):
    def setUp(self):
        self.cib = read_test_resource("cib-empty.xml")

    def test_nothing_to_stop(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                </resources>
            """
        )
        initial_cib = etree_to_str(cib)

        lib.stop_resources(cib, [])
        assert_xml_equal(initial_cib, etree_to_str(cib))

    def test_one_resource(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                </resources>
            """
        )

        lib.stop_resources(
            cib, [cib.find("./configuration/resources/primitive[@id='A']")]
        )

        assert_xml_equal(
            modify_cib(
                self.cib,
                resources="""
                    <resources>
                        <primitive id="A">
                            <meta_attributes id="A-meta_attributes">
                                <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                        </primitive>
                        <primitive id="B"/>
                    </resources>
                """,
            ),
            etree_to_str(cib),
        )

    def test_multiple_resources(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <primitive id="A"/>
                    <primitive id="B"/>
                    <primitive id="C"/>
                </resources>
            """
        )

        lib.stop_resources(
            cib,
            [
                cib.find("./configuration/resources/primitive[@id='A']"),
                cib.find("./configuration/resources/primitive[@id='B']"),
            ],
        )

        assert_xml_equal(
            modify_cib(
                self.cib,
                resources="""
                    <resources>
                        <primitive id="A">
                            <meta_attributes id="A-meta_attributes">
                                <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                        </primitive>
                        <primitive id="B">
                            <meta_attributes id="B-meta_attributes">
                                <nvpair id="B-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                        </primitive>
                        <primitive id="C"/>
                    </resources>
                """,
            ),
            etree_to_str(cib),
        )

    def test_stop_elements_in_subtree(self):
        cib = self.get_cib(
            resources="""
                <resources>
                    <clone id="C">
                        <group id="G">
                            <primitive id="A"/>
                            <primitive id="B"/>
                        </group>
                    </clone>
                </resources>
            """
        )

        lib.stop_resources(
            cib,
            [
                cib.find(
                    "./configuration/resources/clone/group/primitive[@id='A']"
                ),
                cib.find("./configuration/resources/clone/group[@id='G']"),
            ],
        )
        assert_xml_equal(
            modify_cib(
                self.cib,
                resources="""
                <resources>
                    <clone id="C">
                        <group id="G">
                            <meta_attributes id="G-meta_attributes">
                                <nvpair id="G-meta_attributes-target-role" name="target-role" value="Stopped"/>
                            </meta_attributes>
                            <primitive id="A">
                                <meta_attributes id="A-meta_attributes">
                                    <nvpair id="A-meta_attributes-target-role" name="target-role" value="Stopped"/>
                                </meta_attributes>
                            </primitive>
                            <primitive id="B"/>
                        </group>
                    </clone>
                </resources>
            """,
            ),
            etree_to_str(cib),
        )


class EnsureStoppedAfterDisable(TestCase):
    def setUp(self):
        self.state_xml = read_test_resource("crm_mon.minimal.xml")

    def test_ok(self):
        state = complete_state(
            self.state_xml,
            """
                <resources>
                    <resource id="A" managed="true" role="Stopped"/>
                    <group id="B" number_resources="1" maintenance="false" managed="true" disabled="false">
                        <resource id="1" role="Stopped" managed="true"/>
                    </group>
                    <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <resource id="2" role="Stopped" managed="true"/>
                    </clone>
                </resources>
            """,
        )

        report_list = lib.ensure_resources_stopped(state, ["A", "B", "C"])
        self.assertEqual(report_list, [])

    def test_some_not_stopped(self):
        state = complete_state(
            self.state_xml,
            """
                <resources>
                    <resource id="A" managed="true" role="Stopped"/>
                    <group id="B" number_resources="1" maintenance="false" managed="true" disabled="false">
                        <resource id="1" role="Started" managed="true"/>
                    </group>
                    <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <resource id="2" role="Stopped" managed="true"/>
                    </clone>
                </resources>
            """,
        )

        report_list = lib.ensure_resources_stopped(state, ["A", "B", "C"])
        self.assertEqual(
            report_list,
            [
                reports.ReportItem.error(
                    reports.messages.CannotStopResourcesBeforeDeleting(["B"]),
                    force_code=reports.codes.FORCE,
                )
            ],
        )

    def test_multiinstance_some_not_stopped_clone_id(self):
        state = complete_state(
            self.state_xml,
            """
                <resources>
                    <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <resource id="2" role="Stopped" managed="true"/>
                        <resource id="2" role="Started" managed="true"/>
                    </clone>
                </resources>
            """,
        )

        report_list = lib.ensure_resources_stopped(state, ["C"])
        self.assertEqual(
            report_list,
            [
                reports.ReportItem.error(
                    reports.messages.CannotStopResourcesBeforeDeleting(["C"]),
                    force_code=reports.codes.FORCE,
                )
            ],
        )

    def test_multiinstance_some_not_stopped_primitive_id(self):
        state = complete_state(
            self.state_xml,
            """
                <resources>
                    <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                        <resource id="A" role="Stopped" managed="true"/>
                        <resource id="A" role="Started" managed="true"/>
                    </clone>
                </resources>
            """,
        )

        report_list = lib.ensure_resources_stopped(state, ["A"])
        self.assertEqual(
            report_list,
            [
                reports.ReportItem.error(
                    reports.messages.CannotStopResourcesBeforeDeleting(["A"]),
                    force_code=reports.codes.FORCE,
                )
            ],
        )

    def test_works_with_clones_and_bundle_in_status(self):
        state = complete_state(
            self.state_xml,
            """
            <resources>
                <bundle id="BUNDLE" type="podman" image="localhost/pcmktest:http" unique="false" maintenance="false" managed="true" failed="false">
                    <replica id="0">
                        <resource id="BUNDLE-ip-192.168.122.250" resource_agent="ocf:heartbeat:IPaddr2" role="Stopped"/>
                        <resource id="A" role="Stopped"/>
                        <resource id="BUNDLE-podman-0" resource_agent="ocf:heartbeat:podman" role="Stopped"/>
                        <resource id="BUNDLE-0" resource_agent="ocf:pacemaker:remote" role="Stopped"/>
                    </replica>
                </bundle>
                <clone id="C" multi_state="false" unique="false" maintenance="false" managed="true" disabled="false" failed="false" failure_ignored="false">
                    <resource id="2" role="Stopped" managed="true"/>
                </clone>
            </resources>
        """,
        )

        report_list = lib.ensure_resources_stopped(state, ["C"])
        self.assertEqual(report_list, [])


class DependantElementsToReports(TestCase):
    # pylint: disable=no-self-use
    def test_no_reports(self):
        elements = lib.DependantElements({})
        assert_report_item_list_equal(elements.to_reports(), [])

    def test_reports(self):
        elements = lib.DependantElements(
            {"A": const.TAG_RESOURCE_PRIMITIVE, "B": const.TAG_TAG}
        )
        assert_report_item_list_equal(
            elements.to_reports(),
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_DEPENDANT_ELEMENTS,
                    id_tag_map={
                        "A": const.TAG_RESOURCE_PRIMITIVE,
                        "B": const.TAG_TAG,
                    },
                )
            ],
        )


class ElementReferencesToReports(TestCase):
    # pylint: disable=no-self-use
    def test_no_reports(self):
        elements = lib.ElementReferences({}, {})
        assert_report_item_list_equal(elements.to_reports(), [])

    def test_reports(self):
        elements = lib.ElementReferences(
            {"A": {"B"}, "C": {"B"}},
            {
                "A": const.TAG_RESOURCE_PRIMITIVE,
                "B": const.TAG_TAG,
                "C": const.TAG_RESOURCE_PRIMITIVE,
            },
        )
        assert_report_item_list_equal(
            elements.to_reports(),
            [
                fixture.info(
                    reports.codes.CIB_REMOVE_REFERENCES,
                    removing_references_from={"A": {"B"}, "C": {"B"}},
                    id_tag_map={
                        "A": const.TAG_RESOURCE_PRIMITIVE,
                        "B": const.TAG_TAG,
                        "C": const.TAG_RESOURCE_PRIMITIVE,
                    },
                )
            ],
        )


class GetInnerReferences(TestCase):
    # pylint: disable=protected-access
    def test_no_inner_references(self):
        self.assertEqual(
            [], lib._get_inner_references(etree.fromstring("<A/>"))
        )

    def test_not_supported_inner_references(self):
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
        self.assertEqual([], lib._get_inner_references(element))

    def test_resource_primitive(self):
        primitive = etree.fromstring('<primitive id="A"/>')
        self.assertEqual([], lib._get_inner_references(primitive))

    def test_resource_group(self):
        element = etree.fromstring('<group id="G"/>')
        child1 = etree.SubElement(element, "primitive", id="A")
        child2 = etree.SubElement(element, "primitive", id="B")

        self.assertEqual([child1, child2], lib._get_inner_references(element))

    def test_resource_clone(self):
        element = etree.fromstring('<clone id="C"/>')
        child = etree.SubElement(element, "primitive", id="A")

        self.assertEqual([child], lib._get_inner_references(element))

    def test_resource_bundle(self):
        element = etree.fromstring('<bundle id="B"/>')
        child = etree.SubElement(element, "primitive", id="A")

        self.assertEqual([child], lib._get_inner_references(element))

    def test_resource_bundle_no_primitive(self):
        element = etree.fromstring('<bundle id="B"/>')

        self.assertEqual([], lib._get_inner_references(element))


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
            etree.fromstring("<clone/>"),
            etree.fromstring("<clone><primitive/></clone>"),
            etree.fromstring("<group><primitive/></group>"),
            etree.fromstring("<tag><obj_ref/></tag>"),
            etree.fromstring("<resource_set><resource_ref/></resource_set>"),
            etree.fromstring("<rsc_order><resource_set/></rsc_order>"),
            etree.fromstring("<rsc_location><rule/></rsc_location>"),
        ):
            with self.subTest(parent=parent.tag):
                self.assertTrue(lib._is_empty_after_inner_el_removal(parent))

    def test_last_element_false(self):
        for parent in (
            etree.fromstring("<bundle/>"),
            etree.fromstring("<bundle><primitive/></bundle>"),
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
