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

    def setUp(self):
        # pylint: disable=invalid-name
        self.temp_cib = get_tmp_file("tier1_cib_resource_group_ungroup")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name(
            "resources", FIXTURE_CLONE, FIXTURE_DUMMY,
        )
        xml_manip.append_to_first_tag_name(
            "configuration",
            """
            <tags>
                <tag id="T1">
                    <obj_ref id="C-clone"/>
                    <obj_ref id="Dummy"/>
                </tag>
                <tag id="T2">
                    <obj_ref id="C-clone"/>
                </tag>
            </tags>
            """,
        )
        xml_manip.append_to_first_tag_name(
            "constraints",
            """
            <rsc_location id="location-C-clone-rh7-1-INFINITY" node="rh7-1"
                rsc="C-clone" score="INFINITY"/>
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

    def test_nonexistent_clone(self):
        self.assert_pcs_fail(
            "resource unclone NonExistentClone",
            "Error: could not find resource: NonExistentClone\n",
        )
        self.assert_resources_xml_in_cib(FIXTURE_CLONE_AND_RESOURCE)

    def test_not_clone_resource(self):
        self.assert_pcs_fail(
            "resource unclone Dummy",
            "Error: 'Dummy' is not a clone resource\n",
        )
        self.assert_resources_xml_in_cib(FIXTURE_CLONE_AND_RESOURCE)

    def test_unclone_clone_id(self):
        self.assert_effect("resource unclone C-clone", FIXTURE_RESOURCES)

    def test_unclone_resoruce_id(self):
        self.assert_effect("resource unclone C", FIXTURE_RESOURCES)
