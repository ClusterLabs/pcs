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

FIXTURE_PRIMITIVE_FOR_CLONE = """
    <primitive class="ocf" id="C" provider="heartbeat" type="Dummy">
        <operations>
            <op id="C-monitor-interval-10s" interval="10s"
                name="monitor" timeout="20s"/>
        </operations>
    </primitive>
"""

FIXTURE_CLONE = f"""<clone id="C-clone">{FIXTURE_PRIMITIVE_FOR_CLONE}</clone>"""

FIXTURE_CLONE_WITH_OPTIONS = f"""
    <clone id="CustomCloneId">
        {FIXTURE_PRIMITIVE_FOR_CLONE}
        <meta_attributes id="CustomCloneId-meta_attributes">
            <nvpair id="CustomCloneId-meta_attributes-a" name="a" value="b"/>
            <nvpair id="CustomCloneId-meta_attributes-c" name="c" value="d"/>
            <nvpair id="CustomCloneId-meta_attributes-globally-unique"
                name="globally-unique" value="true"/>
        </meta_attributes>
    </clone>
"""

FIXTURE_CLONED_GROUP = """
    <clone id="Group-clone">
        <group id="Group">
            <primitive class="ocf" id="G1" provider="heartbeat" type="Dummy">
                <operations>
                    <op id="G1-monitor-interval-10s" interval="10s"
                        name="monitor" timeout="20s"/>
                </operations>
            </primitive>
            <primitive class="ocf" id="G2" provider="heartbeat" type="Dummy">
                <operations>
                    <op id="G2-monitor-interval-10s" interval="10s"
                        name="monitor" timeout="20s"/>
                </operations>
            </primitive>
        </group>
    </clone>
"""

FIXTURE_GROUP_LAST_MEMBER = """
    <group id="Group">
        {}
    </group>
""".format(
    FIXTURE_PRIMITIVE_FOR_CLONE
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

FIXTURE_BUNDLE_RESOURCE = """
    <bundle id="Dummy-bundle">
        <docker image="pcs:test" />
        {}
    </bundle>
""".format(
    FIXTURE_DUMMY
)


def fixture_resources_xml(*resources_xml_list):
    return """
        <resources>
            {0}
        </resources>
    """.format(
        "\n".join(resources_xml_list)
    )


def fixture_clone(clone_id, primitive_id, promotable=False):
    parts = []
    parts.append(f"""<clone id="{clone_id}">""")
    parts.append(
        f"""
        <primitive class="ocf" id="{primitive_id}" provider="heartbeat"
            type="Dummy">
            <operations>
                <op id="{primitive_id}-monitor-interval-10s" interval="10s"
                    name="monitor" timeout="20s"/>
            </operations>
        </primitive>
        """
    )
    if promotable:
        parts.append(
            f"""
            <meta_attributes id="{clone_id}-meta_attributes">
                <nvpair id="{clone_id}-meta_attributes-promotable"
                    name="promotable" value="true">
                </nvpair>
            </meta_attributes>
            """
        )
    parts.append("""</clone>""")
    return "".join(parts)


FIXTURE_CLONE_AND_RESOURCE = fixture_resources_xml(
    fixture_clone("C-clone", "C"), FIXTURE_DUMMY
)


FIXTURE_RESOURCES = fixture_resources_xml(
    FIXTURE_DUMMY, FIXTURE_PRIMITIVE_FOR_CLONE
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
            "resource unclone NonExistentClone".split(),
            "Error: could not find resource: NonExistentClone\n",
        )
        self.assert_resources_xml_in_cib(FIXTURE_CLONE_AND_RESOURCE)
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CONSTRAINTS_CONFIG_XML)

    def test_not_clone_resource(self):
        self.assert_pcs_fail(
            "resource unclone Dummy".split(),
            "Error: 'Dummy' is not a clone resource\n",
        )
        self.assert_resources_xml_in_cib(FIXTURE_CLONE_AND_RESOURCE)
        self.assert_tags_xml(FIXTURE_TAGS_CONFIG_XML)
        self.assert_constraint_xml(FIXTURE_CONSTRAINTS_CONFIG_XML)

    def test_unclone_clone_id(self):
        self.assert_effect(
            "resource unclone C-clone".split(), FIXTURE_RESOURCES
        )
        self.assert_tags_xml(FIXTURE_TAGS_RESULT_XML)
        self.assert_constraint_xml("<constraints/>")

    def test_unclone_resoruce_id(self):
        self.assert_effect("resource unclone C".split(), FIXTURE_RESOURCES)
        self.assert_tags_xml(FIXTURE_TAGS_RESULT_XML)
        self.assert_constraint_xml("<constraints/>")


class Clone(
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
        self.temp_cib = get_tmp_file("tier1_cib_resource_clone_unclone_clone")
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        self.set_cib_file(FIXTURE_PRIMITIVE_FOR_CLONE)

    def tearDown(self):
        self.temp_cib.close()

    def set_cib_file(self, *xml_string_list):
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name("resources", *xml_string_list)
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def test_clone(self):
        self.assert_effect(
            "resource clone C".split(),
            fixture_resources_xml(fixture_clone("C-clone", "C")),
        )

    def test_clone_custom_id(self):
        self.assert_effect(
            "resource clone C CustomCloneId".split(),
            fixture_resources_xml(fixture_clone("CustomCloneId", "C")),
        )

    def test_clone_id_increment(self):
        self.set_cib_file(
            fixture_clone("C-clone", "Dummy"), FIXTURE_PRIMITIVE_FOR_CLONE,
        )
        self.assert_effect(
            "resource clone C".split(),
            fixture_resources_xml(
                fixture_clone("C-clone", "Dummy"),
                fixture_clone("C-clone-1", "C"),
            ),
        )

    def test_promotable_clone(self):
        self.assert_effect(
            "resource promotable C".split(),
            fixture_resources_xml(
                fixture_clone("C-clone", "C", promotable=True)
            ),
        )

    def test_promotable_clone_custom_id(self):
        self.assert_effect(
            "resource promotable C CustomPromotableId".split(),
            fixture_resources_xml(
                fixture_clone("CustomPromotableId", "C", promotable=True)
            ),
        )

    def test_promotable_keyword_and_option(self):
        self.assert_pcs_fail(
            "resource promotable C CustomCloneId promotable=false".split(),
            (
                "Error: you cannot specify both promotable option and "
                "promotable keyword\n"
            ),
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(FIXTURE_PRIMITIVE_FOR_CLONE)
        )

    def test_clone_with_options(self):
        self.assert_effect(
            (
                "resource clone C CustomCloneId globally-unique=true meta a=b "
                "c=d"
            ).split(),
            fixture_resources_xml(FIXTURE_CLONE_WITH_OPTIONS),
        )

    def test_group_last_member(self):
        self.set_cib_file(FIXTURE_GROUP_LAST_MEMBER)
        self.assert_effect(
            "resource clone C".split(),
            fixture_resources_xml(fixture_clone("C-clone", "C")),
        )

    def test_nonexistent_resource(self):
        self.assert_pcs_fail(
            "resource clone NonExistentClone".split(),
            "Error: unable to find group or resource: NonExistentClone\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(FIXTURE_PRIMITIVE_FOR_CLONE)
        )

    def test_invalid_clone_id(self):
        self.assert_pcs_fail(
            "resource clone C 1invalid".split(),
            "Error: invalid id '1invalid'\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(FIXTURE_PRIMITIVE_FOR_CLONE)
        )

    def test_clone_id_already_exist(self):
        self.assert_pcs_fail(
            "resource clone C C".split(), "Error: id 'C' already exists\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(FIXTURE_PRIMITIVE_FOR_CLONE)
        )

    def test_group_already_cloned(self):
        self.set_cib_file(FIXTURE_CLONED_GROUP)
        self.assert_pcs_fail(
            "resource clone Group".split(),
            "Error: cannot clone a group that has already been cloned\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(FIXTURE_CLONED_GROUP)
        )

    def test_already_a_clone_resource(self):
        self.set_cib_file(FIXTURE_CLONED_GROUP)
        self.assert_pcs_fail(
            "resource clone G1".split(),
            "Error: G1 is already a clone resource\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(FIXTURE_CLONED_GROUP)
        )

    def test_bundle_resource(self):
        self.set_cib_file(FIXTURE_BUNDLE_RESOURCE)
        self.assert_pcs_fail(
            "resource clone Dummy".split(),
            "Error: cannot clone bundle resource\n",
        )
        self.assert_resources_xml_in_cib(
            fixture_resources_xml(FIXTURE_BUNDLE_RESOURCE)
        )
