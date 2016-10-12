from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from os.path import join
from lxml import etree

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.pcs_unittest import mock
from pcs.test.tools.xml import get_xml_manipulation_creator_from_file

from pcs import settings
from pcs.common import report_codes
from pcs.lib.external import CommandRunner
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

    def test_ignore_status_section(self):
        self.cib.append_to_first_tag_name(
            "status",
            """\
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
"""
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


class GetSubElementTest(TestCase):
    def setUp(self):
        self.root = etree.Element("root")
        self.sub = etree.SubElement(self.root, "sub_element")

    def test_sub_element_exists(self):
        self.assertEqual(
            self.sub, lib.get_sub_element(self.root, "sub_element")
        )

    def test_new_no_id(self):
        assert_xml_equal(
            '<new_element/>',
            etree.tostring(
                lib.get_sub_element(self.root, "new_element")
            ).decode()
        )
        assert_xml_equal(
            """
            <root>
                <sub_element/>
                <new_element/>
            </root>
            """,
            etree.tostring(self.root).decode()
        )

    def test_new_with_id(self):
        assert_xml_equal(
            '<new_element id="new_id"/>',
            etree.tostring(
                lib.get_sub_element(self.root, "new_element", "new_id")
            ).decode()
        )
        assert_xml_equal(
            """
            <root>
                <sub_element/>
                <new_element id="new_id"/>
            </root>
            """,
            etree.tostring(self.root).decode()
        )

    def test_new_first(self):
        lib.get_sub_element(self.root, "new_element", "new_id", 0)
        assert_xml_equal(
            """
            <root>
                <new_element id="new_id"/>
                <sub_element/>
            </root>
            """,
            etree.tostring(self.root).decode()
        )

    def test_new_last(self):
        lib.get_sub_element(self.root, "new_element", "new_id", None)
        assert_xml_equal(
            """
            <root>
                <sub_element/>
                <new_element id="new_id"/>
            </root>
            """,
            etree.tostring(self.root).decode()
        )


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


@mock.patch("pcs.lib.cib.tools.upgrade_cib")
class EnsureCibVersionTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)
        self.cib = etree.XML('<cib validate-with="pacemaker-2.3.4"/>')

    def test_same_version(self, mock_upgrade_cib):
        self.assertTrue(
            lib.ensure_cib_version(
                self.mock_runner, self.cib, (2, 3, 4)
            ) is None
        )
        self.assertEqual(0, mock_upgrade_cib.run.call_count)

    def test_higher_version(self, mock_upgrade_cib):
        self.assertTrue(
            lib.ensure_cib_version(
                self.mock_runner, self.cib, (2, 3, 3)
            ) is None
        )
        self.assertEqual(0, mock_upgrade_cib.call_count)

    def test_upgraded_same_version(self, mock_upgrade_cib):
        upgraded_cib = etree.XML('<cib validate-with="pacemaker-2.3.5"/>')
        mock_upgrade_cib.return_value = upgraded_cib
        self.assertEqual(
            upgraded_cib,
            lib.ensure_cib_version(
                self.mock_runner, self.cib, (2, 3, 5)
            )
        )
        mock_upgrade_cib.assert_called_once_with(self.cib, self.mock_runner)

    def test_upgraded_higher_version(self, mock_upgrade_cib):
        upgraded_cib = etree.XML('<cib validate-with="pacemaker-2.3.6"/>')
        mock_upgrade_cib.return_value = upgraded_cib
        self.assertEqual(
            upgraded_cib,
            lib.ensure_cib_version(
                self.mock_runner, self.cib, (2, 3, 5)
            )
        )
        mock_upgrade_cib.assert_called_once_with(self.cib, self.mock_runner)

    def test_upgraded_lower_version(self, mock_upgrade_cib):
        mock_upgrade_cib.return_value = self.cib
        assert_raise_library_error(
            lambda: lib.ensure_cib_version(
                self.mock_runner, self.cib, (2, 3, 5)
            ),
            (
                severities.ERROR,
                report_codes.CIB_UPGRADE_FAILED_TO_MINIMAL_REQUIRED_VERSION,
                {
                    "required_version": "2.3.5",
                    "current_version": "2.3.4"
                }
            )
        )
        mock_upgrade_cib.assert_called_once_with(self.cib, self.mock_runner)


@mock.patch("tempfile.NamedTemporaryFile")
class UpgradeCibTest(TestCase):
    def setUp(self):
        self.mock_runner = mock.MagicMock(spec_set=CommandRunner)

    def test_success(self, mock_named_file):
        mock_file = mock.MagicMock()
        mock_file.name = "mock_file_name"
        mock_file.read.return_value = "<cib/>"
        mock_named_file.return_value = mock_file
        self.mock_runner.run.return_value = ("", "", 0)
        assert_xml_equal(
            "<cib/>",
            etree.tostring(
                lib.upgrade_cib(etree.XML("<old_cib/>"), self.mock_runner)
            ).decode()
        )
        mock_named_file.assert_called_once_with("w+", suffix=".pcs")
        mock_file.write.assert_called_once_with("<old_cib/>")
        mock_file.flush.assert_called_once_with()
        self.mock_runner.run.assert_called_once_with(
            [
                join(settings.pacemaker_binaries, "cibadmin"),
                "--upgrade",
                "--force"
            ],
            env_extend={"CIB_file": "mock_file_name"}
        )
        mock_file.seek.assert_called_once_with(0)
        mock_file.read.assert_called_once_with()

    def test_upgrade_failed(self, mock_named_file):
        mock_file = mock.MagicMock()
        mock_file.name = "mock_file_name"
        mock_named_file.return_value = mock_file
        self.mock_runner.run.return_value = ("some info", "some error", 1)
        assert_raise_library_error(
            lambda: lib.upgrade_cib(etree.XML("<old_cib/>"), self.mock_runner),
            (
                severities.ERROR,
                report_codes.CIB_UPGRADE_FAILED,
                {
                    "reason": "some error\nsome info",
                }
            )
        )
        mock_named_file.assert_called_once_with("w+", suffix=".pcs")
        mock_file.write.assert_called_once_with("<old_cib/>")
        mock_file.flush.assert_called_once_with()
        self.mock_runner.run.assert_called_once_with(
            [
                join(settings.pacemaker_binaries, "cibadmin"),
                "--upgrade",
                "--force"
            ],
            env_extend={"CIB_file": "mock_file_name"}
        )

    def test_unable_to_parse_upgraded_cib(self, mock_named_file):
        mock_file = mock.MagicMock()
        mock_file.name = "mock_file_name"
        mock_file.read.return_value = "not xml"
        mock_named_file.return_value = mock_file
        self.mock_runner.run.return_value = ("", "", 0)
        assert_raise_library_error(
            lambda: lib.upgrade_cib(etree.XML("<old_cib/>"), self.mock_runner),
            (
                severities.ERROR,
                report_codes.CIB_UPGRADE_FAILED,
                {
                    "reason":
                        "Start tag expected, '<' not found, line 1, column 1",
                }
            )
        )
        mock_named_file.assert_called_once_with("w+", suffix=".pcs")
        mock_file.write.assert_called_once_with("<old_cib/>")
        mock_file.flush.assert_called_once_with()
        self.mock_runner.run.assert_called_once_with(
            [
                join(settings.pacemaker_binaries, "cibadmin"),
                "--upgrade",
                "--force"
            ],
            env_extend={"CIB_file": "mock_file_name"}
        )
        mock_file.seek.assert_called_once_with(0)
        mock_file.read.assert_called_once_with()


class EtreeElementAttributesToDictTest(TestCase):
    def setUp(self):
        self.el = etree.Element(
            "test_element",
            {
                "id": "test_id",
                "description": "some description",
                "attribute": "value",
            }
        )

    def test_only_existing(self):
        self.assertEqual(
            {
                "id": "test_id",
                "attribute": "value",
            },
            lib.etree_element_attibutes_to_dict(self.el, ["id", "attribute"])
        )

    def test_only_not_existing(self):
        self.assertEqual(
            {
                "_id": None,
                "not_existing": None,
            },
            lib.etree_element_attibutes_to_dict(
                self.el, ["_id", "not_existing"]
            )
        )

    def test_mix(self):
        self.assertEqual(
            {
                "id": "test_id",
                "attribute": "value",
                "not_existing": None,
            },
            lib.etree_element_attibutes_to_dict(
                self.el, ["id", "not_existing", "attribute"]
            )
        )
