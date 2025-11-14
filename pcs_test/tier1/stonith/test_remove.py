from textwrap import dedent
from unittest import TestCase

from lxml import etree

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.fixture_cib import modify_cib_file
from pcs_test.tools.misc import (
    get_test_resource,
    get_tmp_file,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner


def fixture_stonith_primitive_xml(resource_id: str) -> str:
    return f"""
        <primitive id="{resource_id}" class="stonith" type="fence_pcsmock_minimal"/>
    """


FIXTURE_TAG_XML = """
    <tag id="TAG">
        <obj_ref id="S2"/>
        <obj_ref id="S3"/>
    </tag>
"""
FIXTURE_SET_CONSTRAINT = """
    <rsc_colocation score="10" id="colocation-constraint">
        <resource_set role="Started" id="set1">
            <resource_ref id="S2"/>
            <resource_ref id="S3"/>
        </resource_set>
    </rsc_colocation>
"""
FIXTURE_FENCING_LEVEL_XML = """
    <fencing-level index="3" devices="S2,S3" target="foo" id="fencing-level"/>
"""

ERRORS_HAVE_OCCURRED = (
    "Error: Errors have occurred, therefore pcs is unable to continue\n"
)
NO_STONITH_LEFT_ERROR = (
    "Error: Requested action leaves the cluster with no enabled means to fence "
    "nodes, resulting in the cluster not being able to recover from certain "
    "failure conditions, use --force to override\n"
)
NO_STONITH_LEFT_WARNING = (
    "Warning: Requested action leaves the cluster with no enabled means to fence "
    "nodes, resulting in the cluster not being able to recover from certain "
    "failure conditions\n"
)


class StonithRemoveDeleteBase(
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).find(".//resources"))
    ),
):
    command = ""

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_stonith_remove")
        cib_data = modify_cib_file(
            get_test_resource("cib-empty.xml"),
            resources=f"""
                <resources>
                    {fixture_stonith_primitive_xml("S1")}
                    {fixture_stonith_primitive_xml("S2")}
                    {fixture_stonith_primitive_xml("S3")}
                </resources>
            """,
            constraints=f"""
                <constraints>
                    {FIXTURE_SET_CONSTRAINT}
                </constraints>
            """,
            tags=f"""
                <tags>
                    {FIXTURE_TAG_XML}
                </tags>
            """,
            fencing_topology=f"""
                <fencing-topology>
                    {FIXTURE_FENCING_LEVEL_XML}
                </fencing-topology>
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

    def assert_fencing_topology(self, fencing_xml):
        self.assert_resources_xml_in_cib(
            fencing_xml,
            lambda cib: etree.tostring(
                etree.parse(cib).find(".//fencing-topology")
            ),
        )

    def tearDown(self):
        self.temp_cib.close()

    def test_no_args(self):
        self.assert_pcs_fail(
            ["stonith", self.command],
            stderr_start=f"\nUsage: pcs stonith {self.command}...",
        )

    def test_nonexistent_resource(self):
        self.assert_pcs_fail(
            ["stonith", self.command, "nonexistent"],
            stderr_full="Error: Unable to find stonith resource: 'nonexistent'\n",
        )

    def test_single_resource(self):
        self.assert_effect_single(
            ["stonith", self.command, "S1"],
            f"""
            <resources>
                {fixture_stonith_primitive_xml("S2")}
                {fixture_stonith_primitive_xml("S3")}
            </resources>
            """,
            stderr_full="",
        )
        self.assert_constraints(
            f"""
            <constraints>
                {FIXTURE_SET_CONSTRAINT}
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
        self.assert_fencing_topology(
            f"""
            <fencing-topology>
                {FIXTURE_FENCING_LEVEL_XML}
            </fencing-topology>
            """
        )

    def test_remove_references(self):
        self.assert_effect_single(
            ["stonith", self.command, "S2"],
            f"""
            <resources>
                {fixture_stonith_primitive_xml("S1")}
                {fixture_stonith_primitive_xml("S3")}
            </resources>
            """,
            stderr_full=dedent(
                """\
                Removing references:
                  Resource 'S2' from:
                    Fencing level: 'fencing-level'
                    Resource set: 'set1'
                    Tag: 'TAG'
                """
            ),
        )
        self.assert_constraints(
            """
            <constraints>
                <rsc_colocation score="10" id="colocation-constraint">
                    <resource_set role="Started" id="set1">
                        <resource_ref id="S3"/>
                    </resource_set>
                </rsc_colocation>
            </constraints>
            """
        )
        self.assert_tags(
            """
            <tags>
                <tag id="TAG">
                    <obj_ref id="S3"/>
                </tag>
            </tags>
            """
        )
        self.assert_fencing_topology(
            """
            <fencing-topology>
                <fencing-level index="3" devices="S3" target="foo" id="fencing-level"/>
            </fencing-topology>
            """
        )

    def test_remove_all_resources(self):
        self.assert_pcs_fail(
            ["stonith", self.command, "S1", "S2", "S3"],
            NO_STONITH_LEFT_ERROR + ERRORS_HAVE_OCCURRED,
        )
        self.assert_effect_single(
            ["stonith", self.command, "S1", "S2", "S3", "--force"],
            "<resources/>",
            stderr_full=(
                NO_STONITH_LEFT_WARNING
                + dedent(
                    """\
                    Removing dependant elements:
                      Colocation constraint: 'colocation-constraint'
                      Fencing level: 'fencing-level'
                      Resource set: 'set1'
                      Tag: 'TAG'
                    """
                )
            ),
        )
        self.assert_constraints("<constraints/>")
        self.assert_tags("<tags/>")
        self.assert_fencing_topology("<fencing-topology/>")


class StonithRemove(StonithRemoveDeleteBase, TestCase):
    command = "remove"


class StonithDelete(StonithRemoveDeleteBase, TestCase):
    command = "delete"


class StonithReferencedInAcl(AssertPcsMixin, TestCase):
    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_stonith_remove_referenced_in_acl")
        cib_data = modify_cib_file(
            get_test_resource("cib-empty.xml"),
            resources=f"""
                <resources>
                    {fixture_stonith_primitive_xml("S1")}
                </resources>
            """,
            optional_in_conf="""
                <acls>
                    <acl_role id="ROLE">
                        <acl_permission id="PERMISSION" kind="write" reference="S1"/>
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
        self.assert_pcs_fail(
            ["stonith", "delete", "S1"],
            NO_STONITH_LEFT_ERROR + ERRORS_HAVE_OCCURRED,
        )
        self.assert_pcs_success(
            ["stonith", "delete", "S1", "--force"],
            stderr_full=(
                NO_STONITH_LEFT_WARNING
                + dedent(
                    """\
                    Removing dependant element:
                      Acl permission: 'PERMISSION'
                    Removing references:
                      Acl permission 'PERMISSION' from:
                        Acl role: 'ROLE'
                    """
                )
            ),
        )
