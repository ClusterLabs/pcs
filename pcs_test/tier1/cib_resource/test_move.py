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

fixture_primitive = """
    <primitive class="ocf" id="A" provider="heartbeat" type="Dummy" />
"""

fixture_constraints = [
    """
    <rsc_location id="cli-ban-A-on-node1" rsc="A" role="Started" node="node1"
        score="-INFINITY"/>
    """,
    """
    <rsc_location id="location-A-node1--INFINITY" rsc="A" node="node1"
        score="-INFINITY"/>
    """,
]

fixture_nodes = [
    """<node id="1" uname="node1"/>""",
    """<node id="2" uname="node2"/>""",
    """<node id="3" uname="node3"/>""",
]


class Move(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
    ),
):
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file("tier1_cib_resource_move")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name("resources", fixture_primitive)
        xml_manip.append_to_first_tag_name(
            "constraints",
            *fixture_constraints,
        )
        xml_manip.append_to_first_tag_name(
            "nodes",
            *fixture_nodes,
        )
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def tearDown(self):
        self.temp_cib.close()

    def test_move_to_node_with_existing_ban_constraints(self):
        self.assert_effect(
            "resource move-with-constraint A node1".split(),
            f"<resources>{fixture_primitive}</resources>",
            stderr_full=(
                "Warning: A move constraint has been created and the resource "
                "'A' may or may not move depending on other configuration\n"
            ),
        )
        self.assert_resources_xml_in_cib(
            """
            <constraints>
                <rsc_location id="location-A-node1--INFINITY" rsc="A"
                    node="node1" score="-INFINITY"
                />
                <rsc_location id="cli-prefer-A" rsc="A" role="Started"
                    node="node1" score="INFINITY"
                />
            </constraints>
            """,
            get_cib_part_func=lambda cib: etree.tostring(
                etree.parse(cib).findall(".//constraints")[0]
            ),
        )

    def test_move_stopped_with_existing_constraints(self):
        self.assert_pcs_fail(
            "resource move-with-constraint A".split(),
            (
                "Error: You must specify a node when moving/banning a stopped "
                "resource\n"
            ),
        )

    def test_nonexistent_resource(self):
        self.assert_pcs_fail(
            "resource move-with-constraint NonExistent".split(),
            (
                "Error: bundle/clone/group/resource 'NonExistent' does not "
                "exist\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )

    def test_wait_not_supported_with_file(self):
        self.assert_pcs_fail(
            "resource move-with-constraint A --wait".split(),
            (
                "Deprecation Warning: Using '--wait' is deprecated. Instead, "
                "use the 'pcs status wait' command to wait for the cluster to "
                "settle into stable state. Use the 'pcs status query resource' "
                "commands to verify that the resource is in the expected state "
                "after the wait.\n"
                "Error: Cannot use '-f' together with '--wait'\n"
            ),
        )

    def test_move_autoclean_not_supported_with_file(self):
        self.assert_pcs_fail(
            "resource move A".split(),
            "Error: Specified option '-f' is not supported in this command\n",
        )
