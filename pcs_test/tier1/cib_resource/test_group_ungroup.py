from unittest import TestCase

from lxml import etree

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import XmlManipulation


def fixture_resources_xml(resources_xml_list):
    return """
        <resources>
            {0}
        </resources>
    """.format(
        "\n".join(resources_xml_list)
    )


def fixture_primitive_xml(primitive_id):
    return f"""
        <primitive class="ocf" id="{primitive_id}" provider="heartbeat"
            type="Dummy"
        >
            <operations>
                <op id="{primitive_id}-monitor-interval-10s" interval="10s"
                    name="monitor" timeout="20s"/>
            </operations>
        </primitive>
    """


def fixture_group_xml(group_id, primitive_xml_list):
    return """
        <group id="{group_id}">
            {group_resources}
        </group>
    """.format(
        group_id=group_id,
        group_resources="\n".join(primitive_xml_list),
    )


def fixture_clone_xml(clone_id, clone_resource_xml):
    return """
        <clone id="{clone_id}">
            {clone_resource}
        </clone>
    """.format(
        clone_id=clone_id,
        clone_resource=clone_resource_xml,
    )


FIXTURE_AGROUP_XML = fixture_group_xml(
    "AGroup",
    [
        fixture_primitive_xml("A1"),
        fixture_primitive_xml("A2"),
        fixture_primitive_xml("A3"),
    ],
)


FIXTURE_CONSTRAINTS_CONFIG_XML = """
    <constraints>
        <rsc_location id="location-AGroup-rh7-1-INFINITY" node="rh7-1"
            rsc="AGroup" score="INFINITY"/>
        <rsc_location id="location-TagGroupOnly-rh7-1-INFINITY"
            node="rh7-1" rsc="TagGroupOnly" score="INFINITY"/>
    </constraints>
"""

FIXTURE_CLONE_TAG_CONSTRAINTS = """
    <constraints>
        <rsc_location id="location-AGroup-rh7-1-INFINITY" node="rh7-1"
            rsc="AGroup-clone" score="INFINITY"
        />
        <rsc_location id="location-TagGroupOnly-rh7-1-INFINITY"
            node="rh7-1" rsc="TagGroupOnly" score="INFINITY"
        />
    </constraints>
"""


FIXTURE_CLONE_CONSTRAINT = """
    <constraints>
        <rsc_location id="location-AGroup-rh7-1-INFINITY" node="rh7-1"
            rsc="AGroup-clone" score="INFINITY"
        />
    </constraints>
"""


FIXTURE_TAGS_CONFIG_XML = """
    <tags>
        <tag id="TagGroupOnly">
            <obj_ref id="AGroup"/>
        </tag>
        <tag id="TagNotGroupOnly">
            <obj_ref id="AGroup"/>
            <obj_ref id="A1"/>
            <obj_ref id="A2"/>
            <obj_ref id="A3"/>
        </tag>
    </tags>
"""


FIXTURE_TAGS_RESULT_XML = """
    <tags>
        <tag id="TagNotGroupOnly">
            <obj_ref id="A1"/>
            <obj_ref id="A2"/>
            <obj_ref id="A3"/>
        </tag>
    </tags>
"""


class TestGroupMixin:
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_cib_resource_group_ungroup")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name("resources", FIXTURE_AGROUP_XML)
        xml_manip.append_to_first_tag_name(
            "configuration",
            FIXTURE_TAGS_CONFIG_XML,
        )
        xml_manip.append_to_first_tag_name(
            "constraints",
            """
            <rsc_location id="location-AGroup-rh7-1-INFINITY" node="rh7-1"
                rsc="AGroup" score="INFINITY"/>
            """,
            """
            <rsc_location id="location-TagGroupOnly-rh7-1-INFINITY"
                node="rh7-1" rsc="TagGroupOnly" score="INFINITY"/>
            """,
        )
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def tearDown(self):
        self.temp_cib.close()


class GroupDeleteRemoveUngroupBase(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
    ),
    TestGroupMixin,
):
    command = None

    def assert_tags_xml(self, expected_xml):
        self.assert_resources_xml_in_cib(
            expected_xml,
            get_cib_part_func=lambda cib: etree.tostring(
                etree.parse(cib).findall(".//tags")[0],
            ),
        )

    def assert_constraint_xml(self, expected_xml):
        self.assert_resources_xml_in_cib(
            expected_xml,
            get_cib_part_func=lambda cib: etree.tostring(
                etree.parse(cib).findall(".//constraints")[0],
            ),
        )

    def test_nonexistent_group(self):
        self.assert_pcs_fail(
            ["resource"] + self.command + ["NonExistentGroup"],
            "Error: Group 'NonExistentGroup' does not exist\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml([FIXTURE_AGROUP_XML]),
        )
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CONSTRAINTS_CONFIG_XML)

    def test_not_a_group_id(self):
        self.assert_pcs_fail(
            ["resource"] + self.command + ["A1"],
            "Error: Group 'A1' does not exist\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml([FIXTURE_AGROUP_XML]),
        )
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CONSTRAINTS_CONFIG_XML)

    def test_whole_group(self):
        self.assert_effect(
            ["resource"] + self.command + ["AGroup"],
            fixture_resources_xml(
                [
                    fixture_primitive_xml("A1"),
                    fixture_primitive_xml("A2"),
                    fixture_primitive_xml("A3"),
                ],
            ),
            stderr_full=(
                "Removing Constraint - location-TagGroupOnly-rh7-1-INFINITY\n"
                "Removing Constraint - location-AGroup-rh7-1-INFINITY\n"
            ),
        )
        self.assert_tags_xml(FIXTURE_TAGS_RESULT_XML)
        self.assert_constraint_xml("<constraints/>")

    def test_specified_resources(self):
        self.assert_effect(
            ["resource"] + self.command + ["AGroup", "A1", "A3"],
            fixture_resources_xml(
                [
                    fixture_group_xml(
                        "AGroup",
                        [
                            fixture_primitive_xml("A2"),
                        ],
                    ),
                    fixture_primitive_xml("A1"),
                    fixture_primitive_xml("A3"),
                ],
            ),
        )
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CONSTRAINTS_CONFIG_XML)

    def test_all_resources(self):
        self.assert_effect(
            ["resource"] + self.command + ["AGroup", "A1", "A2", "A3"],
            fixture_resources_xml(
                [
                    fixture_primitive_xml("A1"),
                    fixture_primitive_xml("A2"),
                    fixture_primitive_xml("A3"),
                ],
            ),
            stderr_full=(
                "Removing Constraint - location-TagGroupOnly-rh7-1-INFINITY\n"
                "Removing Constraint - location-AGroup-rh7-1-INFINITY\n"
            ),
        )
        self.assert_tags_xml(FIXTURE_TAGS_RESULT_XML)
        self.assert_constraint_xml("<constraints/>")

    def test_cloned_group(self):
        self.assert_pcs_success("resource clone AGroup".split())
        self.assert_pcs_fail(
            ["resource"] + self.command + ["AGroup"],
            "Error: Cannot remove all resources from a cloned group\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(
                [fixture_clone_xml("AGroup-clone", FIXTURE_AGROUP_XML)],
            )
        )
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CLONE_TAG_CONSTRAINTS)

    def test_cloned_group_all_resources_specified(self):
        self.assert_pcs_success("resource clone AGroup".split())
        self.assert_pcs_fail(
            ["resource"] + self.command + ["AGroup", "A1", "A2", "A3"],
            "Error: Cannot remove all resources from a cloned group\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(
                [fixture_clone_xml("AGroup-clone", FIXTURE_AGROUP_XML)],
            )
        )
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CLONE_TAG_CONSTRAINTS)

    def test_cloned_group_with_one_resource(self):
        self.assert_pcs_success("resource clone AGroup".split())
        self.assert_pcs_success("resource ungroup AGroup A1 A2".split())
        self.assert_effect(
            ["resource"] + self.command + ["AGroup"],
            fixture_resources_xml(
                [
                    fixture_clone_xml(
                        "AGroup-clone",
                        fixture_primitive_xml("A3"),
                    ),
                    fixture_primitive_xml("A1"),
                    fixture_primitive_xml("A2"),
                ],
            ),
            stderr_full="Removing Constraint - location-TagGroupOnly-rh7-1-INFINITY\n",
        )
        self.assert_tags_xml(FIXTURE_TAGS_RESULT_XML)
        self.assert_constraint_xml(FIXTURE_CLONE_CONSTRAINT)


class ResourceUngroup(GroupDeleteRemoveUngroupBase, TestCase):
    command = ["ungroup"]


class GroupDelete(GroupDeleteRemoveUngroupBase, TestCase):
    command = ["group", "delete"]


class GroupRemove(GroupDeleteRemoveUngroupBase, TestCase):
    command = ["group", "remove"]
