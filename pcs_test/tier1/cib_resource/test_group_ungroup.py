from unittest import TestCase
from lxml import etree

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import (
    get_test_resource as rc,
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
        group_id=group_id, group_resources="\n".join(primitive_xml_list),
    )


def fixture_clone_xml(clone_id, clone_resource_xml):
    return """
        <clone id="{clone_id}">
            {clone_resource}
        </clone>
    """.format(
        clone_id=clone_id, clone_resource=clone_resource_xml,
    )


FIXTURE_AGROUP_XML = fixture_group_xml(
    "AGroup",
    [
        fixture_primitive_xml("A1"),
        fixture_primitive_xml("A2"),
        fixture_primitive_xml("A3"),
    ],
)


class TestGroupMixin(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_cib_resource_group_ungroup")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name("resources", FIXTURE_AGROUP_XML)
        xml_manip.append_to_first_tag_name(
            "configuration",
            """
            <tags>
                <tag id="T1">
                    <obj_ref id="AGroup"/>
                </tag>
                <tag id="T2">
                    <obj_ref id="AGroup"/>
                </tag>
            </tags>
            """,
        )
        xml_manip.append_to_first_tag_name(
            "constraints",
            """
            <rsc_location id="location-AGroup-rh7-1-INFINITY" node="rh7-1"
                rsc="AGroup" score="INFINITY"/>
            """,
            """
            <rsc_location id="location-T1-rh7-1-INFINITY" node="rh7-1" rsc="T1"
                score="INFINITY"/>
            """,
        )
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def tearDown(self):
        # pylint: disable=invalid-name
        self.temp_cib.close()


class GroupDeleteRemoveUngroupBase(TestGroupMixin):
    command = None

    def test_nonexistent_group(self):
        self.assert_pcs_fail(
            f"resource {self.command} NonExistentGroup",
            "Error: Group 'NonExistentGroup' does not exist\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml([FIXTURE_AGROUP_XML]),
        )

    def test_not_a_group_id(self):
        self.assert_pcs_fail(
            f"resource {self.command} A1", "Error: Group 'A1' does not exist\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml([FIXTURE_AGROUP_XML]),
        )

    def test_whole_group(self):
        self.assert_effect(
            f"resource {self.command} AGroup",
            fixture_resources_xml(
                [
                    fixture_primitive_xml("A1"),
                    fixture_primitive_xml("A2"),
                    fixture_primitive_xml("A3"),
                ],
            ),
            output=(
                "Removing Constraint - location-T1-rh7-1-INFINITY\n"
                "Removing Constraint - location-AGroup-rh7-1-INFINITY\n"
            ),
        )

    def test_specified_resources(self):
        self.assert_effect(
            f"resource {self.command} AGroup A1 A3",
            fixture_resources_xml(
                [
                    fixture_group_xml(
                        "AGroup", [fixture_primitive_xml("A2"),],
                    ),
                    fixture_primitive_xml("A1"),
                    fixture_primitive_xml("A3"),
                ],
            ),
        )

    def test_cloned_group(self):
        self.assert_pcs_success("resource clone AGroup")
        self.assert_pcs_fail(
            f"resource {self.command} AGroup",
            "Error: Cannot remove all resources from a cloned group\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(
                [fixture_clone_xml("AGroup-clone", FIXTURE_AGROUP_XML)],
            )
        )

    def test_cloned_group_all_resorces_specified(self):
        self.assert_pcs_success("resource clone AGroup")
        self.assert_pcs_fail(
            f"resource {self.command} AGroup A1 A2 A3",
            "Error: Cannot remove all resources from a cloned group\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(
                [fixture_clone_xml("AGroup-clone", FIXTURE_AGROUP_XML)],
            )
        )

    def test_cloned_group_with_one_resource(self):
        self.assert_pcs_success("resource clone AGroup")
        self.assert_pcs_success("resource ungroup AGroup A1 A2")
        self.assert_effect(
            f"resource {self.command} AGroup",
            fixture_resources_xml(
                [
                    fixture_clone_xml(
                        "AGroup-clone", fixture_primitive_xml("A3"),
                    ),
                    fixture_primitive_xml("A1"),
                    fixture_primitive_xml("A2"),
                ],
            ),
            output="Removing Constraint - location-T1-rh7-1-INFINITY\n",
        )


class ResourceUngroup(GroupDeleteRemoveUngroupBase, TestCase):
    command = "ungroup"


class GroupDelete(GroupDeleteRemoveUngroupBase, TestCase):
    command = "group delete"


class GroupRemove(GroupDeleteRemoveUngroupBase, TestCase):
    command = "group remove"
