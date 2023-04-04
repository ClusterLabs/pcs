from functools import partial
from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.common.tools import Version
from pcs.lib.cib import tools as lib

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import get_xml_manipulation_creator_from_file

cib_element_lookup = etree.fromstring(
    """
            <cib>
                <configuration>
                    <resources>
                        <primitive id="R1" />
                        <primitive id="R3" />
                        <primitive id="RX2" />
                        <primitive id="RX2" />
                        <primitive id="RX3" />
                        <primitive id="T" />
                    </resources>
                    <tags>
                        <tag id="T">
                            <obj_ref id="RX1" />
                            <obj_ref id="RX3" />
                        </tag>
                    </tags>
                </configuration>
                <status>
                    <lrm_resource id="R3" />
                    <lrm_resource id="R2" />
                </status>
            </cib>
            """
)


class CibToolsTest(TestCase):
    def setUp(self):
        self.create_cib = get_xml_manipulation_creator_from_file(
            rc("cib-empty.xml")
        )
        self.cib = self.create_cib()

    def fixture_add_primitive_with_id(self, element_id):
        self.cib.append_to_first_tag_name(
            "resources",
            '<primitive id="{0}" class="ocf" provider="heartbeat" type="Dummy"/>'.format(
                element_id
            ),
        )


class IdProviderTest(CibToolsTest):
    def setUp(self):
        super().setUp()
        self.provider = lib.IdProvider(self.cib.tree)

    @staticmethod
    def fixture_report(_id):
        return (
            severities.ERROR,
            report_codes.ID_ALREADY_EXISTS,
            {
                "id": _id,
            },
            None,
        )


class IdProviderBook(IdProviderTest):
    def test_nonexisting_id(self):
        assert_report_item_list_equal(self.provider.book_ids("myId"), [])

    def test_existing_id(self):
        self.fixture_add_primitive_with_id("myId")
        assert_report_item_list_equal(
            self.provider.book_ids("myId"),
            [
                self.fixture_report("myId"),
            ],
        )

    def test_double_book(self):
        assert_report_item_list_equal(self.provider.book_ids("myId"), [])
        assert_report_item_list_equal(
            self.provider.book_ids("myId"),
            [
                self.fixture_report("myId"),
            ],
        )

    def test_more_ids(self):
        assert_report_item_list_equal(
            self.provider.book_ids("myId1", "myId2"), []
        )
        assert_report_item_list_equal(
            self.provider.book_ids("myId1", "myId2"),
            [
                self.fixture_report("myId1"),
                self.fixture_report("myId2"),
            ],
        )

    def test_complex(self):
        # test ids existing in the cib, double booked, available
        # test reports not repeated
        self.fixture_add_primitive_with_id("myId1")
        self.fixture_add_primitive_with_id("myId2")
        assert_report_item_list_equal(
            self.provider.book_ids(
                "myId1", "myId2", "myId3", "myId2", "myId3", "myId4", "myId3"
            ),
            [
                self.fixture_report("myId1"),
                self.fixture_report("myId2"),
                self.fixture_report("myId3"),
            ],
        )


class IdProviderAllocate(IdProviderTest):
    def test_nonexisting_id(self):
        self.assertEqual("myId", self.provider.allocate_id("myId"))

    def test_existing_id(self):
        self.fixture_add_primitive_with_id("myId")
        self.assertEqual("myId-1", self.provider.allocate_id("myId"))

    def test_allocate_books(self):
        self.assertEqual("myId", self.provider.allocate_id("myId"))
        self.assertEqual("myId-1", self.provider.allocate_id("myId"))

    def test_booked_ids(self):
        self.fixture_add_primitive_with_id("myId")
        assert_report_item_list_equal(self.provider.book_ids("myId-1"), [])
        self.assertEqual("myId-2", self.provider.allocate_id("myId"))


class DoesIdExistTest(CibToolsTest):
    def test_existing_id(self):
        self.fixture_add_primitive_with_id("myId")
        self.assertTrue(lib.does_id_exist(self.cib.tree, "myId"))

    def test_nonexisting_id(self):
        self.fixture_add_primitive_with_id("myId")
        self.assertFalse(lib.does_id_exist(self.cib.tree, "otherId"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "myid"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, " myId"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "myId "))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "my Id"))

    def test_ignore_status_section(self):
        self.cib.append_to_first_tag_name(
            "status",
            """
            <elem1 id="status-1">
                <elem1a id="status-1a">
                    <elem1aa id="status-1aa"/>
                    <elem1ab id="status-1ab"/>
                </elem1a>
                <elem1b id="status-1b">
                    <elem1ba id="status-1ba"/>
                    <elem1bb id="status-1bb"/>
                </elem1b>
            </elem1>
        """,
        )
        self.assertFalse(lib.does_id_exist(self.cib.tree, "status-1"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "status-1a"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "status-1aa"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "status-1ab"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "status-1b"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "status-1ba"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "status-1bb"))

    def test_ignore_acl_target(self):
        self.cib.append_to_first_tag_name(
            "configuration",
            """
            <acls>
                <acl_target id="target1"/>
            </acls>
            """,
        )
        self.assertFalse(lib.does_id_exist(self.cib.tree, "target1"))

    def test_ignore_acl_role_references(self):
        self.cib.append_to_first_tag_name(
            "configuration",
            """
            <acls>
                <acl_target id="target1">
                    <role id="role1"/>
                    <role id="role2"/>
                </acl_target>
            </acls>
            """,
        )
        self.assertFalse(lib.does_id_exist(self.cib.tree, "role1"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "role2"))

    def test_ignore_sections_directly_under_cib(self):
        # this is side effect of current implementation but is not problem since
        # id attribute is not allowed for elements directly under cib
        tree = etree.fromstring('<cib><direct id="a"/></cib>')
        self.assertFalse(lib.does_id_exist(tree, "a"))

    def test_find_id_when_cib_is_not_root_element(self):
        # for example we have only part of xml
        tree = etree.fromstring('<root><direct id="a"/></root>')
        self.assertTrue(lib.does_id_exist(tree, "a"))

    def test_find_remote_node_pacemaker_internal_id(self):
        tree = etree.fromstring(
            """
            <cib>
                <configuration>
                    <resources>
                        <primitive id="b">
                            <meta_attributes>
                                <nvpair name="remote-node" value="a"/>
                            </meta_attributes>
                        </primitive>
                    </resources>
                </configuration>
            </cib>
        """
        )
        self.assertTrue(lib.does_id_exist(tree, "a"))


class FindUniqueIdTest(CibToolsTest):
    def test_already_unique(self):
        self.fixture_add_primitive_with_id("myId")
        self.assertEqual("other", lib.find_unique_id(self.cib.tree, "other"))

    def test_add_suffix(self):
        self.fixture_add_primitive_with_id("myId")
        self.assertEqual("myId-1", lib.find_unique_id(self.cib.tree, "myId"))

        self.fixture_add_primitive_with_id("myId-1")
        self.assertEqual("myId-2", lib.find_unique_id(self.cib.tree, "myId"))

    def test_suffix_not_needed(self):
        self.fixture_add_primitive_with_id("myId-1")
        self.assertEqual("myId", lib.find_unique_id(self.cib.tree, "myId"))

    def test_add_first_available_suffix(self):
        self.fixture_add_primitive_with_id("myId")
        self.fixture_add_primitive_with_id("myId-1")
        self.fixture_add_primitive_with_id("myId-3")
        self.assertEqual("myId-2", lib.find_unique_id(self.cib.tree, "myId"))

    def test_reserved_ids(self):
        self.fixture_add_primitive_with_id("myId-1")
        self.assertEqual(
            "myId-3",
            lib.find_unique_id(self.cib.tree, "myId", ["myId", "myId-2"]),
        )


class CreateSubelementId(TestCase):
    def test_create_plain_id_when_no_conflicting_id_there(self):
        context = etree.fromstring('<cib><a id="b"/></cib>')
        self.assertEqual(
            "b-name",
            lib.create_subelement_id(
                context.find(".//a"), "name", lib.IdProvider(context)
            ),
        )

    def test_create_decorated_id_when_conflicting_id_there(self):
        context = etree.fromstring('<cib><a id="b"><c id="b-name"/></a></cib>')
        self.assertEqual(
            "b-name-1",
            lib.create_subelement_id(
                context.find(".//a"), "name", lib.IdProvider(context)
            ),
        )

    def test_parent_has_no_id(self):
        context = etree.fromstring("<cib><a/></cib>")
        self.assertEqual(
            "a-name",
            lib.create_subelement_id(
                context.find(".//a"), "name", lib.IdProvider(context)
            ),
        )


class GetConfigurationTest(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual(
            "configuration", lib.get_configuration(self.cib.tree).tag
        )

    def test_raise_if_missing(self):
        for conf in self.cib.tree.findall(".//configuration"):
            conf.getparent().remove(conf)
        assert_raise_library_error(
            lambda: lib.get_configuration(self.cib.tree),
            (
                severities.ERROR,
                report_codes.CIB_CANNOT_FIND_MANDATORY_SECTION,
                {
                    "section": "configuration",
                },
            ),
        )


class GetConstraintsTest(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual("constraints", lib.get_constraints(self.cib.tree).tag)

    def test_raise_if_missing(self):
        for section in self.cib.tree.findall(".//configuration/constraints"):
            section.getparent().remove(section)
        assert_raise_library_error(
            lambda: lib.get_constraints(self.cib.tree),
            (
                severities.ERROR,
                report_codes.CIB_CANNOT_FIND_MANDATORY_SECTION,
                {
                    "section": "configuration/constraints",
                },
            ),
        )


class GetCrmConfig(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual("crm_config", lib.get_crm_config(self.cib.tree).tag)

    def test_raise_if_missing(self):
        for section in self.cib.tree.findall(".//configuration/crm_config"):
            section.getparent().remove(section)
        assert_raise_library_error(
            lambda: lib.get_crm_config(self.cib.tree),
            fixture.error(
                report_codes.CIB_CANNOT_FIND_MANDATORY_SECTION,
                section="configuration/crm_config",
            ),
        )


class GetResourcesTest(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual("resources", lib.get_resources(self.cib.tree).tag)

    def test_raise_if_missing(self):
        for section in self.cib.tree.findall(".//configuration/resources"):
            section.getparent().remove(section)
        assert_raise_library_error(
            lambda: lib.get_resources(self.cib.tree),
            (
                severities.ERROR,
                report_codes.CIB_CANNOT_FIND_MANDATORY_SECTION,
                {
                    "section": "configuration/resources",
                },
            ),
        )


class GetNodes(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual("nodes", lib.get_nodes(self.cib.tree).tag)

    def test_raise_if_missing(self):
        for section in self.cib.tree.findall(".//configuration/nodes"):
            section.getparent().remove(section)
        assert_raise_library_error(
            lambda: lib.get_nodes(self.cib.tree),
            (
                severities.ERROR,
                report_codes.CIB_CANNOT_FIND_MANDATORY_SECTION,
                {
                    "section": "configuration/nodes",
                },
                None,
            ),
        )


class GetAclsTest(CibToolsTest):
    def test_success_if_exists(self):
        self.cib.append_to_first_tag_name(
            "configuration", '<acls><acl_role id="test_role" /></acls>'
        )
        self.assertEqual("test_role", lib.get_acls(self.cib.tree)[0].get("id"))

    def test_success_if_missing(self):
        acls = lib.get_acls(self.cib.tree)
        self.assertEqual("acls", acls.tag)
        self.assertEqual("configuration", acls.getparent().tag)


class GetFencingTopology(CibToolsTest):
    def test_success_if_exists(self):
        self.cib.append_to_first_tag_name(
            "configuration", "<fencing-topology />"
        )
        self.assertEqual(
            "fencing-topology", lib.get_fencing_topology(self.cib.tree).tag
        )

    def test_success_if_missing(self):
        ft_el = lib.get_fencing_topology(self.cib.tree)
        self.assertEqual("fencing-topology", ft_el.tag)
        self.assertEqual("configuration", ft_el.getparent().tag)


class GetTagsTest(CibToolsTest):
    def test_success_if_exists(self):
        self.cib.append_to_first_tag_name("configuration", "<tags/>")
        self.assertEqual("tags", lib.get_tags(self.cib.tree).tag)

    def test_success_if_missing(self):
        tags_el = lib.get_tags(self.cib.tree)
        self.assertEqual("tags", tags_el.tag)
        self.assertEqual("configuration", tags_el.getparent().tag)


@mock.patch("pcs.lib.cib.tools.does_id_exist")
class ValidateIdDoesNotExistsTest(TestCase):
    def test_success_when_id_does_not_exists(self, does_id_exists):
        # pylint: disable=no-self-use
        does_id_exists.return_value = False
        lib.validate_id_does_not_exist("tree", "some-id")
        does_id_exists.assert_called_once_with("tree", "some-id")

    def test_raises_when_id_exists(self, does_id_exists):
        # pylint: disable=no-self-use
        does_id_exists.return_value = True
        assert_raise_library_error(
            lambda: lib.validate_id_does_not_exist("tree", "some-id"),
            (
                severities.ERROR,
                report_codes.ID_ALREADY_EXISTS,
                {"id": "some-id"},
            ),
        )
        does_id_exists.assert_called_once_with("tree", "some-id")


class GetPacemakerVersionByWhichCibWasValidatedTest(TestCase):
    def test_missing_attribute(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML("<cib/>")
            ),
            (
                severities.ERROR,
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                {
                    "reason": "the attribute 'validate-with' of the element"
                    " 'cib' is missing"
                },
            ),
        )

    def test_invalid_version(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML('<cib validate-with="something-1.2.3"/>')
            ),
            (
                severities.ERROR,
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                {
                    "reason": "the attribute 'validate-with' of the element"
                    " 'cib' has an invalid value: 'something-1.2.3'"
                },
            ),
        )

    def test_invalid_version_at_end(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML('<cib validate-with="pacemaker-1.2.3x"/>')
            ),
            (
                severities.ERROR,
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                {
                    "reason": "the attribute 'validate-with' of the element"
                    " 'cib' has an invalid value: 'pacemaker-1.2.3x'"
                },
            ),
        )

    def test_no_revision(self):
        self.assertEqual(
            Version(1, 2),
            lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML('<cib validate-with="pacemaker-1.2"/>')
            ),
        )

    def test_with_revision(self):
        self.assertEqual(
            Version(1, 2, 3),
            lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML('<cib validate-with="pacemaker-1.2.3"/>')
            ),
        )


class GetCibCrmFeatureSet(TestCase):
    def test_success(self):
        self.assertEqual(
            Version(3, 0, 9),
            lib.get_cib_crm_feature_set(
                etree.XML('<cib crm_feature_set="3.0.9" />')
            ),
        )

    def test_success_no_revision(self):
        self.assertEqual(
            Version(3, 1),
            lib.get_cib_crm_feature_set(
                etree.XML('<cib crm_feature_set="3.1" />')
            ),
        )

    def test_missing_attribute(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: lib.get_cib_crm_feature_set(etree.XML("<cib />")),
            fixture.error(
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                reason=(
                    "the attribute 'crm_feature_set' of the element 'cib' is "
                    "missing"
                ),
            ),
        )

    def test_invalid_version(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: lib.get_cib_crm_feature_set(
                etree.XML('<cib crm_feature_set="3" />')
            ),
            fixture.error(
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                reason=(
                    "the attribute 'crm_feature_set' of the element 'cib' has "
                    "an invalid value: '3'"
                ),
            ),
        )

    def test_invalid_version_at_end(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: lib.get_cib_crm_feature_set(
                etree.XML('<cib crm_feature_set="3.0.9x" />')
            ),
            fixture.error(
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                reason=(
                    "the attribute 'crm_feature_set' of the element 'cib' has "
                    "an invalid value: '3.0.9x'"
                ),
            ),
        )


find_group = partial(lib.find_element_by_tag_and_id, "group")


class FindTagWithId(TestCase):
    def test_returns_element_when_exists(self):
        tree = etree.fromstring(
            '<cib><resources><group id="a"/></resources></cib>'
        )
        element = find_group(tree.find(".//resources"), "a")
        self.assertEqual("group", element.tag)
        self.assertEqual("a", element.attrib["id"])

    def test_returns_element_when_exists_one_of_tags(self):
        tree = etree.fromstring(
            """
            <cib>
                <resources>
                    <group id="a"/>
                    <primitive id="b"/>
                </resources>
            </cib>
        """
        )
        element = lib.find_element_by_tag_and_id(
            ["group", "primitive"], tree.find(".//resources"), "a"
        )
        self.assertEqual("group", element.tag)
        self.assertEqual("a", element.attrib["id"])

    def test_raises_when_is_under_another_tag(self):
        # pylint: disable=no-self-use
        tree = etree.fromstring(
            '<cib><resources><primitive id="a"/></resources></cib>'
        )

        assert_raise_library_error(
            lambda: find_group(tree.find(".//resources"), "a"),
            (
                severities.ERROR,
                report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                {
                    "id": "a",
                    "expected_types": ["group"],
                    "current_type": "primitive",
                },
            ),
        )

    def test_raises_when_is_under_another_context(self):
        # pylint: disable=no-self-use
        tree = etree.fromstring(
            """
            <cib>
                <resources>
                    <group id="g1"><primitive id="a"/></group>
                    <group id="g2"><primitive id="b"/></group>
                </resources>
            </cib>
        """
        )
        assert_raise_library_error(
            lambda: lib.find_element_by_tag_and_id(
                "primitive", tree.find('.//resources/group[@id="g2"]'), "a"
            ),
            (
                severities.ERROR,
                report_codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT,
                {
                    "object_type": "primitive",
                    "object_id": "a",
                    "expected_context_type": "group",
                    "expected_context_id": "g2",
                },
            ),
        )

    def test_raises_when_id_does_not_exists(self):
        # pylint: disable=no-self-use
        tree = etree.fromstring("<cib><resources/></cib>")
        assert_raise_library_error(
            lambda: find_group(tree.find(".//resources"), "a"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "a",
                    "expected_types": ["group"],
                    "context_type": "resources",
                    "context_id": "",
                },
                None,
            ),
        )
        assert_raise_library_error(
            lambda: find_group(
                tree.find(".//resources"), "a", id_types=["resource group"]
            ),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "a",
                    "expected_types": ["resource group"],
                    "context_type": "resources",
                    "context_id": "",
                },
                None,
            ),
        )

    def test_returns_none_if_id_do_not_exists(self):
        tree = etree.fromstring("<cib><resources/></cib>")
        self.assertIsNone(
            find_group(tree.find(".//resources"), "a", none_if_id_unused=True)
        )


class ElementSearcher(TestCase):
    def assert_get_errors_raises(self, searcher):
        with self.assertRaises(AssertionError) as cm:
            searcher.get_errors()
        self.assertEqual(
            str(cm.exception),
            "Improper usage: cannot report errors when there are none",
        )

    def test_element_exists(self):
        tree = etree.fromstring(
            '<cib><resources><group id="a"/></resources></cib>'
        )
        searcher = lib.ElementSearcher("group", "a", tree.find(".//resources"))
        self.assertTrue(searcher.element_found())
        self.assertEqual("a", searcher.get_element().attrib["id"])
        self.assert_get_errors_raises(searcher)

    def test_element_exists_multiple_tags(self):
        tree = etree.fromstring(
            """
            <cib>
                <resources>
                    <group id="a"/>
                    <primitive id="b"/>
                </resources>
            </cib>
        """
        )
        searcher = lib.ElementSearcher(
            ["primitive", "group"], "a", tree.find(".//resources")
        )
        self.assertTrue(searcher.element_found())
        self.assertEqual("a", searcher.get_element().attrib["id"])
        self.assert_get_errors_raises(searcher)

    def test_id_found_for_another_tag(self):
        tree = etree.fromstring(
            '<cib><resources><primitive id="a"/></resources></cib>'
        )
        searcher = lib.ElementSearcher("group", "a", tree.find(".//resources"))
        self.assertFalse(searcher.element_found())
        self.assertIsNone(searcher.get_element())
        assert_report_item_list_equal(
            searcher.get_errors(),
            [
                fixture.error(
                    report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="a",
                    expected_types=["group"],
                    current_type="primitive",
                ),
            ],
        )

    def test_element_exists_in_another_context(self):
        tree = etree.fromstring(
            """
            <cib>
                <resources>
                    <group id="g1"><primitive id="a"/></group>
                    <group id="g2"><primitive id="b"/></group>
                </resources>
            </cib>
        """
        )
        searcher = lib.ElementSearcher(
            "primitive",
            "a",
            tree.find('.//resources/group[@id="g2"]'),
        )
        self.assertFalse(searcher.element_found())
        self.assertIsNone(searcher.get_element())
        assert_report_item_list_equal(
            searcher.get_errors(),
            [
                fixture.error(
                    report_codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT,
                    object_id="a",
                    object_type="primitive",
                    expected_context_type="group",
                    expected_context_id="g2",
                ),
            ],
        )

    def assert_id_does_not_exists(self, element_type_desc, expected_types):
        tree = etree.fromstring("<cib><resources/></cib>")
        searcher = lib.ElementSearcher(
            "group",
            "a",
            tree.find(".//resources"),
            element_type_desc=element_type_desc,
        )
        self.assertFalse(searcher.element_found())
        self.assertIsNone(searcher.get_element())
        assert_report_item_list_equal(
            searcher.get_errors(),
            [
                fixture.error(
                    report_codes.ID_NOT_FOUND,
                    id="a",
                    expected_types=expected_types,
                    context_type="resources",
                    context_id="",
                ),
            ],
        )

    def test_id_does_not_exists(self):
        self.assert_id_does_not_exists(None, ["group"])

    def test_id_does_not_exists_custom_description_string(self):
        self.assert_id_does_not_exists("resource group", ["resource group"])

    def test_id_does_not_exists_custom_description_list(self):
        self.assert_id_does_not_exists(
            ["resource", "group"], ["group", "resource"]
        )

    def test_book_available_valid_id(self):
        tree = etree.fromstring(
            '<cib><resources><group id="b"/></resources></cib>'
        )
        id_provider = lib.IdProvider(tree)
        searcher = lib.ElementSearcher("group", "a", tree.find(".//resources"))
        self.assertFalse(searcher.element_found())
        self.assertTrue(searcher.validate_book_id(id_provider))
        self.assert_get_errors_raises(searcher)

    def test_book_valid_id_used_in_cib(self):
        tree = etree.fromstring(
            '<cib><resources><group id="a"/></resources></cib>'
        )
        id_provider = lib.IdProvider(tree)
        searcher = lib.ElementSearcher("group", "a", tree.find(".//resources"))
        self.assertTrue(searcher.element_found())
        self.assertFalse(searcher.validate_book_id(id_provider))
        # does not report book errors  - the element has been found,
        # validate_book_id should have not been called
        self.assert_get_errors_raises(searcher)

    def test_book_valid_id_used_in_id_provider(self):
        tree = etree.fromstring(
            '<cib><resources><group id="b"/></resources></cib>'
        )
        id_provider = lib.IdProvider(tree)
        self.assertEqual([], id_provider.book_ids("a"))
        searcher = lib.ElementSearcher("group", "a", tree.find(".//resources"))
        self.assertFalse(searcher.element_found())
        self.assertFalse(searcher.validate_book_id(id_provider))
        assert_report_item_list_equal(
            searcher.get_errors(),
            [
                fixture.error(
                    report_codes.ID_ALREADY_EXISTS,
                    id="a",
                ),
            ],
        )

    def test_book_not_valid_id(self):
        tree = etree.fromstring(
            '<cib><resources><group id="b"/></resources></cib>'
        )
        id_provider = lib.IdProvider(tree)
        searcher = lib.ElementSearcher("group", "1a", tree.find(".//resources"))
        self.assertFalse(searcher.element_found())
        self.assertFalse(searcher.validate_book_id(id_provider, "group name"))
        assert_report_item_list_equal(
            searcher.get_errors(),
            [
                fixture.error(
                    report_codes.INVALID_ID_BAD_CHAR,
                    id="1a",
                    id_description="group name",
                    is_first_char=True,
                    invalid_character="1",
                ),
            ],
        )


class GetElementById(TestCase):
    def test_one_match(self):
        found_element = lib.get_element_by_id(cib_element_lookup, "R1")
        self.assertEqual(
            found_element,
            cib_element_lookup.find('.//resources/primitive[@id="R1"]'),
        )

    def test_one_match_ignore_reference(self):
        found_element = lib.get_element_by_id(cib_element_lookup, "R3")
        self.assertEqual(
            found_element,
            cib_element_lookup.find('.//resources/primitive[@id="R3"]'),
        )

    def test_duplicate_ids(self):
        with self.assertRaises(AssertionError):
            lib.get_element_by_id(cib_element_lookup, "RX2")

    def test_tag_id_same_as_resource_id(self):
        with self.assertRaises(AssertionError):
            lib.get_element_by_id(cib_element_lookup, "T")

    def test_id_not_in_cib(self):
        with self.assertRaises(lib.ElementNotFound):
            lib.get_element_by_id(cib_element_lookup, "X")

    def test_no_match_in_status(self):
        with self.assertRaises(lib.ElementNotFound):
            lib.get_element_by_id(cib_element_lookup, "R2")

    def test_no_match_in_obj_ref(self):
        with self.assertRaises(lib.ElementNotFound):
            lib.get_element_by_id(cib_element_lookup, "RX1")


class GetElementsById(TestCase):
    def assert_result(self, found_id_list, unmatched_id_list):
        found_elements, unmatched_ids = lib.get_elements_by_ids(
            cib_element_lookup, found_id_list + unmatched_id_list
        )
        self.assertListEqual(
            found_elements,
            [
                cib_element_lookup.find(
                    f'.//resources/primitive[@id="{found_id}"]'
                )
                for found_id in found_id_list
            ],
        )
        self.assertListEqual(unmatched_ids, unmatched_id_list)

    def test_one_match(self):
        self.assert_result(["R1"], [])

    def test_one_match_ignore_reference(self):
        self.assert_result(["R3"], [])

    def test_duplicate_ids(self):
        with self.assertRaises(AssertionError):
            lib.get_elements_by_ids(cib_element_lookup, ["RX2"])

    def test_tag_id_same_as_resource_id(self):
        with self.assertRaises(AssertionError):
            lib.get_elements_by_ids(cib_element_lookup, ["T"])

    def test_id_not_in_cib(self):
        self.assert_result(["R1"], ["X1", "X2"])

    def test_no_match_in_status(self):
        self.assert_result([], ["R2"])

    def test_no_match_in_obj_ref(self):
        self.assert_result([], ["RX1"])


def _configuration_fixture(configuration_content):
    return f"""
    <cib>
      <configuration>
      {configuration_content}
      </configuration>
      <status>
      {configuration_content}
      </status>
      {configuration_content}
    </cib>
    """


class FindElementsWithoutIdReferencingId(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        pass

    def test_constraint_set_reference(self):
        cib = etree.fromstring(
            _configuration_fixture(
                """
                <constraints>
                    <rsc_location>
                        <resource_set>
                            <resource_ref id="A"/>
                            <resource_ref id="B"/>
                        </resource_set>
                        <resource_ref id="A" invalid="position"/>
                    </rsc_location>
                    <resource_ref id="A" invalid="position"/>
                    <rsc_colocation>
                        <resource_set>
                            <resource_ref id="C"/>
                            <resource_ref id="A"/>
                        </resource_set>
                    </rsc_colocation>
                </constraints>
                <resource_ref id="A" invalid="position"/>
                """
            )
        )
        self.assertEqual(
            [
                cib.find(
                    "./configuration/constraints/rsc_location/resource_set/resource_ref[@id='A']"
                ),
                cib.find(
                    "./configuration/constraints/rsc_colocation/resource_set/resource_ref[@id='A']"
                ),
            ],
            list(lib._find_elements_without_id_referencing_id(cib, "A")),
        )

    def test_tag_reference(self):
        cib = etree.fromstring(
            _configuration_fixture(
                """
                <tags>
                    <tag id="X">
                        <obj_ref id="A"/>
                    </tag>
                    <obj_ref id="A" invalid="position"/>
                    <tag id="Y">
                        <obj_ref id="C"/>
                        <obj_ref id="A"/>
                        <obj_ref id="D"/>
                    </tag>
                    <tag id="Z">
                        <obj_ref id="C"/>
                    </tag>
                </tags>
                <obj_ref id="A" invalid="position"/>
                """
            )
        )
        self.assertEqual(
            [
                cib.find("./configuration/tags/tag[@id='X']/obj_ref[@id='A']"),
                cib.find("./configuration/tags/tag[@id='Y']/obj_ref[@id='A']"),
            ],
            list(lib._find_elements_without_id_referencing_id(cib, "A")),
        )

    def test_acl_reference(self):
        cib = etree.fromstring(
            _configuration_fixture(
                """
                <acls>
                    <acl_target>
                        <role id="A"/>
                        <role id="B"/>
                    </acl_target>
                    <role id="A" invalid="position"/>
                    <acl_group>
                        <role id="D"/>
                        <role id="A"/>
                        <role id="C"/>
                    </acl_group>
                </acls>
                <role id="A" invalid="position"/>
                """
            )
        )
        self.assertEqual(
            [
                cib.find("./configuration/acls/acl_target/role[@id='A']"),
                cib.find("./configuration/acls/acl_group/role[@id='A']"),
            ],
            list(lib._find_elements_without_id_referencing_id(cib, "A")),
        )

    def test_all_references_types(self):
        pass


class RemoveElementById(TestCase):
    def setUp(self):
        pass

    def test_element_found(self):
        pass

    def test_element_not_found(self):
        pass
