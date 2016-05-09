from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from lxml import etree

from pcs.test.tools.assertions import assert_raise_library_error
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_mock import mock
from pcs.test.tools.xml import get_xml_manipulation_creator_from_file

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severities

from pcs.lib.cib import tools as lib

class CibToolsTest(TestCase):
    def setUp(self):
        self.create_cib = get_xml_manipulation_creator_from_file(rc("cib-empty.xml"))
        self.cib = self.create_cib()

    def fixture_add_primitive_with_id(self, element_id):
        self.cib.append_to_first_tag_name(
            "resources",
            '<primitive id="{0}" class="ocf" provider="heartbeat" type="Dummy"/>'
                .format(element_id)
        )

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
                    "cib": etree.tostring(self.cib.tree)
                },
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
                    "cib": etree.tostring(self.cib.tree)
                },
            ),
        )


class GetAclsTest(CibToolsTest):
    def setUp(self):
        self.create_cib = get_xml_manipulation_creator_from_file(rc("cib-empty-1.2.xml"))
        self.cib = self.create_cib()

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
