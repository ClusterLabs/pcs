from textwrap import dedent
from unittest import TestCase

from lxml import etree

from pcs.common.str_tools import format_list, format_plural

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.fixture_cib import modify_cib_file
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


def fixture_primitive_xml(resource_id: str) -> str:
    return f"""
        <primitive id="{resource_id}" class="ocf" provider="pcsmock" type="minimal"/>
    """


FIXTURE_CLONED_GROUP_XML = f"""
    <clone id="R2-clone">
        <group id="R2-group">
            {fixture_primitive_xml("R2")}
        </group>
    </clone>
"""
FIXTURE_GROUP_XML = f"""
    <group id="R3R4-group">
        {fixture_primitive_xml("R3")}
        {fixture_primitive_xml("R4")}
    </group>
"""
FIXTURE_TAG_XML = """
    <tag id="TAG">
        <obj_ref id="R3"/>
        <obj_ref id="R4"/>
    </tag>
"""
FIXTURE_LOCATION_CONSTRAINT1 = """
    <rsc_location id="location-constraint1" rsc="R2" node="foo" score="INFINITY"/>
"""
FIXTURE_LOCATION_CONSTRAINT2 = """
    <rsc_location id="location-constraint2" rsc="R2-group" node="foo" score="INFINITY"/>
"""
FIXTURE_LOCATION_CONSTRAINT3 = """
    <rsc_location id="location-constraint3" rsc="R2-clone" node="foo" score="INFINITY"/>
"""
FIXTURE_ALL_LOCATION_CONSTRAINTS = f"""
    {FIXTURE_LOCATION_CONSTRAINT1}
    {FIXTURE_LOCATION_CONSTRAINT2}
    {FIXTURE_LOCATION_CONSTRAINT3}
"""
FIXTURE_SET_CONSTRAINT = """
    <rsc_colocation score="10" id="colocation-constraint">
        <resource_set role="Started" id="set1">
            <resource_ref id="R3"/>
            <resource_ref id="R4"/>
        </resource_set>
    </rsc_colocation>
"""
FIXTURE_ALL_CONSTRAINTS_XML = f"""
    {FIXTURE_ALL_LOCATION_CONSTRAINTS}
    {FIXTURE_SET_CONSTRAINT}
"""


def fixture_message_not_deleting_resources_not_live(resource_ids):
    resources = format_plural(resource_ids, "resource")
    are = format_plural(resource_ids, "is")
    return (
        "Warning: Resources are not going to be stopped before deletion "
        "because the command does not run on a live cluster\n"
        f"Warning: Not checking if {resources} {format_list(resource_ids)} "
        f"{are} stopped before deletion because the command does not run on a "
        "live cluster. Deleting unstopped resources may result in orphaned "
        "resources being present in the cluster.\n"
    )


class ResourceRemoveDeleteBase(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).find(".//resources"))
    ),
):
    command = ""

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_remove")
        cib_data = modify_cib_file(
            get_test_resource("cib-empty.xml"),
            resources=f"""
                <resources>
                    {fixture_primitive_xml("R1")}
                    {FIXTURE_GROUP_XML}
                    {FIXTURE_CLONED_GROUP_XML}
                </resources>
            """,
            constraints=f"""
                <constraints>
                    {FIXTURE_ALL_CONSTRAINTS_XML}
                </constraints>
            """,
            tags=f"""
                <tags>
                    {FIXTURE_TAG_XML}
                </tags>
            """,
        )
        write_data_to_tmpfile(cib_data, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def assert_constraints(self, constraints_xml):
        self.assert_resources_xml_in_cib(
            constraints_xml,
            lambda cib: etree.tostring(etree.parse(cib).find(".//constraints")),
        )

    def assert_tags(self, tags_xml):
        self.assert_resources_xml_in_cib(
            tags_xml,
            lambda cib: etree.tostring(etree.parse(cib).find(".//tags")),
        )

    def tearDown(self):
        self.temp_cib.close()

    def test_no_args(self):
        self.assert_pcs_fail(
            ["resource", self.command],
            stderr_start=f"\nUsage: pcs resource {self.command}...",
        )

    def test_nonexistent_resource(self):
        self.assert_pcs_fail(
            ["resource", self.command, "nonexistent"],
            stderr_full="Error: Unable to find resource: 'nonexistent'\n",
        )

    def test_primitive(self):
        self.assert_effect_single(
            ["resource", self.command, "R1"],
            f"""
            <resources>
                {FIXTURE_GROUP_XML}
                {FIXTURE_CLONED_GROUP_XML}
            </resources>
            """,
            stderr_full=fixture_message_not_deleting_resources_not_live(["R1"]),
        )
        self.assert_constraints(
            f"""
                <constraints>
                    {FIXTURE_ALL_CONSTRAINTS_XML}
                </constraints>
            """
        )
        self.assert_tags(
            f"""
                <tags>
                    {FIXTURE_TAG_XML}
                </tags>
            """
        )

    def test_remove_dependencies(self):
        self.assert_effect_single(
            ["resource", self.command, "R2"],
            f"""
            <resources>
                {fixture_primitive_xml("R1")}
                {FIXTURE_GROUP_XML}
            </resources>
            """,
            stderr_full=fixture_message_not_deleting_resources_not_live(
                ["R2", "R2-clone", "R2-group"]
            )
            + dedent(
                """\
                Removing dependant elements:
                  Clone: 'R2-clone'
                  Group: 'R2-group'
                  Location constraints: 'location-constraint1', 'location-constraint2', 'location-constraint3'
                """
            ),
        )
        self.assert_constraints(
            f"""
            <constraints>
                {FIXTURE_SET_CONSTRAINT}
            </constraints>
            """
        )

    def test_remove_references(self):
        self.assert_effect_single(
            ["resource", self.command, "R3"],
            f"""
            <resources>
                {fixture_primitive_xml("R1")}
                <group id="R3R4-group">
                    {fixture_primitive_xml("R4")}
                </group>
                {FIXTURE_CLONED_GROUP_XML}
            </resources>
            """,
            stderr_full=fixture_message_not_deleting_resources_not_live(["R3"])
            + dedent(
                """\
                Removing references:
                  Resource 'R3' from:
                    Group: 'R3R4-group'
                    Resource set: 'set1'
                    Tag: 'TAG'
                """
            ),
        )
        self.assert_constraints(
            f"""
                <constraints>
                    {FIXTURE_ALL_LOCATION_CONSTRAINTS}
                    <rsc_colocation score="10" id="colocation-constraint">
                        <resource_set role="Started" id="set1">
                            <resource_ref id="R4"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
            """
        )
        self.assert_tags(
            """
                <tags>
                    <tag id="TAG">
                        <obj_ref id="R4"/>
                    </tag>
                </tags>
            """
        )

    def test_remove_all_resources(self):
        self.assert_effect_single(
            ["resource", self.command, "R1", "R2", "R3", "R4"],
            "<resources/>",
            stderr_full=fixture_message_not_deleting_resources_not_live(
                ["R1", "R2", "R3", "R4", "R2-clone", "R2-group", "R3R4-group"]
            )
            + dedent(
                """\
                Removing dependant elements:
                  Clone: 'R2-clone'
                  Colocation constraint: 'colocation-constraint'
                  Groups: 'R2-group', 'R3R4-group'
                  Location constraints: 'location-constraint1', 'location-constraint2', 'location-constraint3'
                  Resource set: 'set1'
                  Tag: 'TAG'
                """
            ),
        )
        self.assert_constraints("<constraints/>")
        self.assert_tags("<tags/>")


class ResourceRemove(ResourceRemoveDeleteBase, TestCase):
    command = "remove"


class ResourceDelete(ResourceRemoveDeleteBase, TestCase):
    command = "delete"


class ResourceReferencedInAcl(AssertPcsMixin, TestCase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_resource_remove_referenced_in_acl")
        cib_data = modify_cib_file(
            get_test_resource("cib-empty.xml"),
            resources=f"""
                <resources>
                    {fixture_primitive_xml("R1")}
                </resources>
            """,
            optional_in_conf="""
                <acls>
                    <acl_role id="ROLE">
                        <acl_permission id="PERMISSION" kind="write" reference="R1"/>
                    </acl_role>
                    <acl_target id="TARGET">
                        <role id="ROLE"/>
                    </acl_target>
                </acls>
            """,
        )
        write_data_to_tmpfile(cib_data, self.temp_cib)
        self.pcs_runner = PcsRunner(self.temp_cib.name)

    def tearDown(self):
        self.temp_cib.close()

    def test_remove_primitive(self):
        self.assert_pcs_success(
            ["resource", "delete", "R1"],
            stderr_full=fixture_message_not_deleting_resources_not_live(["R1"])
            + dedent(
                """\
                Removing dependant element:
                  Acl permission: 'PERMISSION'
                Removing references:
                  Acl permission 'PERMISSION' from:
                    Acl role: 'ROLE'
                """
            ),
        )
