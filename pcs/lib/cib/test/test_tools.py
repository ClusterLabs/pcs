from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from lxml import etree

from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
)
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.xml import get_xml_manipulation_creator_from_file

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severities

from pcs.lib.cib import tools as lib

class CibToolsTest(TestCase):
    def setUp(self):
        self.create_cib = get_xml_manipulation_creator_from_file(
            rc("cib-empty.xml")
        )
        self.cib = self.create_cib()

    def fixture_add_primitive_with_id(self, element_id):
        self.cib.append_to_first_tag_name(
            "resources",
            '<primitive id="{0}" class="ocf" provider="heartbeat" type="Dummy"/>'
                .format(element_id)
        )


class IdProviderTest(CibToolsTest):
    def setUp(self):
        super(IdProviderTest, self).setUp()
        self.provider = lib.IdProvider(self.cib.tree)

    def fixture_report(self, id):
        return (
            severities.ERROR,
            report_codes.ID_ALREADY_EXISTS,
            {
                "id": id,
            },
            None
        )


class IdProviderBook(IdProviderTest):
    def test_nonexisting_id(self):
        assert_report_item_list_equal(
            self.provider.book_ids("myId"),
            []
        )

    def test_existing_id(self):
        self.fixture_add_primitive_with_id("myId")
        assert_report_item_list_equal(
            self.provider.book_ids("myId"),
            [
                self.fixture_report("myId"),
            ]
        )

    def test_double_book(self):
        assert_report_item_list_equal(
            self.provider.book_ids("myId"),
            []
        )
        assert_report_item_list_equal(
            self.provider.book_ids("myId"),
            [
                self.fixture_report("myId"),
            ]
        )

    def test_more_ids(self):
        assert_report_item_list_equal(
            self.provider.book_ids("myId1", "myId2"),
            []
        )
        assert_report_item_list_equal(
            self.provider.book_ids("myId1", "myId2"),
            [
                self.fixture_report("myId1"),
                self.fixture_report("myId2"),
            ]
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
            ]
        )


class IdProviderAllocate(IdProviderTest):
    def test_nonexisting_id(self):
        self.assertEqual("myId",  self.provider.allocate_id("myId"))

    def test_existing_id(self):
        self.fixture_add_primitive_with_id("myId")
        self.assertEqual("myId-1",  self.provider.allocate_id("myId"))

    def test_allocate_books(self):
        self.assertEqual("myId",  self.provider.allocate_id("myId"))
        self.assertEqual("myId-1",  self.provider.allocate_id("myId"))

    def test_booked_ids(self):
        self.fixture_add_primitive_with_id("myId")
        assert_report_item_list_equal(
            self.provider.book_ids("myId-1"),
            []
        )
        self.assertEqual("myId-2",  self.provider.allocate_id("myId"))


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
        self.cib.append_to_first_tag_name("status", """
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
        """)
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
            """
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
            """
        )
        self.assertFalse(lib.does_id_exist(self.cib.tree, "role1"))
        self.assertFalse(lib.does_id_exist(self.cib.tree, "role2"))

    def test_ignore_sections_directly_under_cib(self):
        #this is side effect of current implementation but is not problem since
        #id attribute is not allowed for elements directly under cib
        tree = etree.fromstring('<cib><direct id="a"/></cib>')
        self.assertFalse(lib.does_id_exist(tree, "a"))

    def test_find_id_when_cib_is_not_root_element(self):
        #for example we have only part of xml
        tree = etree.fromstring('<root><direct id="a"/></root>')
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
            lib.find_unique_id(self.cib.tree, "myId", ["myId", "myId-2"])
        )

class CreateNvsetIdTest(TestCase):
    def test_create_plain_id_when_no_confilicting_id_there(self):
        context = etree.fromstring('<cib><a id="b"/></cib>')
        self.assertEqual(
            "b-name",
            lib.create_subelement_id(context.find(".//a"), "name")
        )

    def test_create_decorated_id_when_conflicting_id_there(self):
        context = etree.fromstring(
            '<cib><a id="b"><c id="b-name"/></a></cib>'
        )
        self.assertEqual(
            "b-name-1",
            lib.create_subelement_id(context.find(".//a"), "name")
        )

class GetConfigurationTest(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual(
            "configuration",
            lib.get_configuration(self.cib.tree).tag
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
                }
            ),
        )

class GetConstraintsTest(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual(
            "constraints",
            lib.get_constraints(self.cib.tree).tag
        )

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
                }
            ),
        )

class GetResourcesTest(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual(
            "resources",
            lib.get_resources(self.cib.tree).tag
        )

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
                }
            ),
        )

class GetNodes(CibToolsTest):
    def test_success_if_exists(self):
        self.assertEqual(
            "nodes",
            lib.get_nodes(self.cib.tree).tag
        )

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
                None
            ),
        )

class GetAclsTest(CibToolsTest):
    def test_success_if_exists(self):
        self.cib.append_to_first_tag_name(
            "configuration",
            '<acls><acl_role id="test_role" /></acls>'
        )
        self.assertEqual(
            "test_role",
            lib.get_acls(self.cib.tree)[0].get("id")
        )

    def test_success_if_missing(self):
        acls = lib.get_acls(self.cib.tree)
        self.assertEqual("acls", acls.tag)
        self.assertEqual("configuration", acls.getparent().tag)

class GetFencingTopology(CibToolsTest):
    def test_success_if_exists(self):
        self.cib.append_to_first_tag_name(
            "configuration",
            "<fencing-topology />"
        )
        self.assertEqual(
            "fencing-topology",
            lib.get_fencing_topology(self.cib.tree).tag
        )

    def test_success_if_missing(self):
        ft = lib.get_fencing_topology(self.cib.tree)
        self.assertEqual("fencing-topology", ft.tag)
        self.assertEqual("configuration", ft.getparent().tag)


@mock.patch('pcs.lib.cib.tools.does_id_exist')
class ValidateIdDoesNotExistsTest(TestCase):
    def test_success_when_id_does_not_exists(self, does_id_exists):
        does_id_exists.return_value = False
        lib.validate_id_does_not_exist("tree", "some-id")
        does_id_exists.assert_called_once_with("tree", "some-id")

    def test_raises_whne_id_exists(self, does_id_exists):
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
        assert_raise_library_error(
            lambda: lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML("<cib/>")
            ),
            (
                severities.ERROR,
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                {}
            )
        )

    def test_invalid_version(self):
        assert_raise_library_error(
            lambda: lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML('<cib validate-with="something-1.2.3"/>')
            ),
            (
                severities.ERROR,
                report_codes.CIB_LOAD_ERROR_BAD_FORMAT,
                {}
            )
        )

    def test_no_revision(self):
        self.assertEqual(
            (1, 2, 0),
            lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML('<cib validate-with="pacemaker-1.2"/>')
            )
        )

    def test_with_revision(self):
        self.assertEqual(
            (1, 2, 3),
            lib.get_pacemaker_version_by_which_cib_was_validated(
                etree.XML('<cib validate-with="pacemaker-1.2.3"/>')
            )
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
        tree = etree.fromstring("""
            <cib>
                <resources>
                    <group id="a"/>
                    <primitive id="b"/>
                </resources>
            </cib>
        """)
        element = lib.find_element_by_tag_and_id(
            ["group", "primitive"],
            tree.find(".//resources"),
            "a"
        )
        self.assertEqual("group", element.tag)
        self.assertEqual("a", element.attrib["id"])

    def test_raises_when_is_under_another_tag(self):
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
        tree = etree.fromstring("""
            <cib>
                <resources>
                    <group id="g1"><primitive id="a"/></group>
                    <group id="g2"><primitive id="b"/></group>
                </resources>
            </cib>
        """)
        assert_raise_library_error(
            lambda: lib.find_element_by_tag_and_id(
                "primitive",
                tree.find('.//resources/group[@id="g2"]'),
                "a"
            ),
            (
                severities.ERROR,
                report_codes.OBJECT_WITH_ID_IN_UNEXPECTED_CONTEXT,
                {
                    "type": "primitive",
                    "id": "a",
                    "expected_context_type": "group",
                    "expected_context_id": "g2",
                },
            ),
        )

    def test_raises_when_id_does_not_exists(self):
        tree = etree.fromstring('<cib><resources/></cib>')
        assert_raise_library_error(
            lambda: find_group(tree.find('.//resources'), "a"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "a",
                    "id_description": "group",
                    "context_type": "resources",
                    "context_id": "",
                },
            ),
        )
        assert_raise_library_error(
            lambda: find_group(
                tree.find('.//resources'),
                "a",
                id_description="resource group"
            ),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "a",
                    "id_description": "resource group",
                },
            ),
        )

    def test_returns_none_if_id_do_not_exists(self):
        tree = etree.fromstring('<cib><resources/></cib>')
        self.assertIsNone(find_group(
            tree.find('.//resources'),
            "a",
            none_if_id_unused=True
        ))
