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


FIXTURE_DUMMY = """
    <primitive class="ocf" id="Dummy" provider="heartbeat" type="Dummy">
        <operations>
            <op id="Dummy-monitor-interval-10s" interval="10s"
                name="monitor" timeout="20s"/>
        </operations>
    </primitive>
"""

FIXTURE_CLONE = """
    <clone id="C-clone">
        <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
            <operations>
                <op id="C-monitor-interval-10s" interval="10s"
                    name="monitor" timeout="20s"/>
            </operations>
        </primitive>
    </clone>
"""

FIXTURE_CLONE_AND_RESOURCE = """
    <resources>
        {0}
        {1}
    </resources>
""".format(
    FIXTURE_CLONE, FIXTURE_DUMMY
)

FIXTURE_RESOURCES = """
    <resources>
        {0}
        <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
            <operations>
                <op id="C-monitor-interval-10s" interval="10s" name="monitor"
                    timeout="20s"/>
            </operations>
        </primitive>
    </resources>
""".format(
    FIXTURE_DUMMY
)


FIXTURE_CONSTRAINTS_CONFIG_XML = """
    <constraints>
        <rsc_location id="location-C-clone-rh7-1-INFINITY" node="rh7-1"
            rsc="C-clone" score="INFINITY"/>
        <rsc_location id="location-TagCloneOnly-rh7-1-INFINITY"
            node="rh7-1" rsc="TagCloneOnly" score="INFINITY"/>
    </constraints>
"""


FIXTURE_TAGS_CONFIG_XML = """
    <tags>
        <tag id="TagCloneOnly">
            <obj_ref id="C-clone"/>
        </tag>
        <tag id="TagNotCloneOnly">
            <obj_ref id="C-clone"/>
            <obj_ref id="Dummy"/>
        </tag>
    </tags>
"""


FIXTURE_TAGS_RESULT_XML = """
    <tags>
        <tag id="TagNotCloneOnly">
            <obj_ref id="Dummy"/>
        </tag>
    </tags>
"""


class Unclone(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(
            # pylint:disable=undefined-variable
            etree.parse(cib).findall(".//resources")[0]
        )
    ),
):
    empty_cib = rc("cib-empty.xml")

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

    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_cib_resource_group_ungroup")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name(
            "resources", FIXTURE_CLONE, FIXTURE_DUMMY,
        )
        xml_manip.append_to_first_tag_name(
            "configuration", FIXTURE_TAGS_CONFIG_XML,
        )
        xml_manip.append_to_first_tag_name(
            "constraints",
            """
            <rsc_location id="location-C-clone-rh7-1-INFINITY" node="rh7-1"
                rsc="C-clone" score="INFINITY"/>
            """,
            """
            <rsc_location id="location-TagCloneOnly-rh7-1-INFINITY"
                node="rh7-1" rsc="TagCloneOnly" score="INFINITY"/>
            """,
        )
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def tearDown(self):
        # pylint: disable=invalid-name
        self.temp_cib.close()

    def test_nonexistent_clone(self):
        self.assert_pcs_fail(
            "resource unclone NonExistentClone",
            "Error: could not find resource: NonExistentClone\n",
        )
        self.assert_resources_xml_in_cib(FIXTURE_CLONE_AND_RESOURCE)
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CONSTRAINTS_CONFIG_XML)

    def test_not_clone_resource(self):
        self.assert_pcs_fail(
            "resource unclone Dummy",
            "Error: 'Dummy' is not a clone resource\n",
        )
        self.assert_resources_xml_in_cib(FIXTURE_CLONE_AND_RESOURCE)
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CONSTRAINTS_CONFIG_XML)

    def test_unclone_clone_id(self):
        self.assert_effect("resource unclone C-clone", FIXTURE_RESOURCES)
        self.assert_tags_xml(FIXTURE_TAGS_RESULT_XML)
        self.assert_constraint_xml("<constraints/>")

    def test_unclone_resoruce_id(self):
        self.assert_effect("resource unclone C", FIXTURE_RESOURCES)
        self.assert_tags_xml(FIXTURE_TAGS_RESULT_XML)
        self.assert_constraint_xml("<constraints/>")
