from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib import acl as lib
from pcs.lib.cib.tools import get_acls
from pcs.lib.errors import LibraryError

from pcs_test.tools.assertions import (
    ExtendedAssertionsMixin,
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.xml import get_xml_manipulation_creator_from_file


class LibraryAclTest(TestCase):
    def setUp(self):
        self.create_cib = get_xml_manipulation_creator_from_file(
            rc("cib-empty.xml")
        )
        self.cib = self.create_cib()

    @property
    def acls(self):
        return get_acls(self.cib.tree)

    def fixture_add_role(self, role_id):
        self.cib.append_to_first_tag_name(
            "configuration", '<acls><acl_role id="{0}"/></acls>'.format(role_id)
        )

    def assert_cib_equal(self, expected_cib):
        got_xml = str(self.cib)
        expected_xml = str(expected_cib)
        assert_xml_equal(expected_xml, got_xml)


class ValidatePermissionsTest(LibraryAclTest):
    def setUp(self):
        self.xml = """
        <xml>
           <test id="test-id">
               <another id="another-id"/>
               <last id="last-id"/>
           </test>
        </xml>
        """
        self.tree = etree.XML(self.xml)
        self.allowed_permissions = ["read", "write", "deny"]
        self.allowed_scopes = ["xpath", "id"]

    def test_success(self):
        permissions = [
            ("read", "id", "test-id"),
            ("write", "id", "another-id"),
            ("deny", "id", "last-id"),
            ("read", "xpath", "any string"),
            ("write", "xpath", "maybe xpath"),
            ("deny", "xpath", "xpath"),
        ]
        lib.validate_permissions(self.tree, permissions)

    def test_unknown_permission(self):
        permissions = [
            ("read", "id", "test-id"),
            ("unknown", "id", "another-id"),
            ("write", "xpath", "my xpath"),
            ("allow", "xpath", "xpath"),
        ]
        assert_raise_library_error(
            lambda: lib.validate_permissions(self.tree, permissions),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_value": "unknown",
                    "option_name": "permission",
                    "allowed_values": self.allowed_permissions,
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
                None,
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_value": "allow",
                    "option_name": "permission",
                    "allowed_values": self.allowed_permissions,
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
                None,
            ),
        )

    def test_unknown_scope(self):
        permissions = [
            ("read", "id", "test-id"),
            ("write", "not_id", "test-id"),
            ("deny", "not_xpath", "some xpath"),
            ("read", "xpath", "xpath"),
        ]
        assert_raise_library_error(
            lambda: lib.validate_permissions(self.tree, permissions),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_value": "not_id",
                    "option_name": "scope type",
                    "allowed_values": self.allowed_scopes,
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
                None,
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_value": "not_xpath",
                    "option_name": "scope type",
                    "allowed_values": self.allowed_scopes,
                    "cannot_be_empty": False,
                    "forbidden_characters": None,
                },
                None,
            ),
        )

    def test_not_existing_id(self):
        permissions = [
            ("read", "id", "test-id"),
            ("write", "id", "id"),
            ("deny", "id", "last"),
            ("write", "xpath", "maybe xpath"),
        ]
        assert_raise_library_error(
            lambda: lib.validate_permissions(self.tree, permissions),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "id",
                    "expected_types": ["id"],
                    "context_type": "",
                    "context_id": "",
                },
                None,
            ),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "last",
                    "expected_types": ["id"],
                    "context_type": "",
                    "context_id": "",
                },
                None,
            ),
        )


class CreateRoleTest(LibraryAclTest):
    def test_create_for_new_role_id(self):
        role_id = "new-id"
        lib.create_role(self.acls, role_id)

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                '<acls><acl_role id="{0}"/></acls>'.format(role_id),
            )
        )

    def test_refuse_invalid_id(self):
        assert_raise_library_error(
            lambda: lib.create_role(self.cib.tree, "#invalid"),
            (
                severities.ERROR,
                report_codes.INVALID_ID_BAD_CHAR,
                {
                    "id": "#invalid",
                    "id_description": "ACL role",
                    "invalid_character": "#",
                    "is_first_char": True,
                },
            ),
        )

    def test_refuse_existing_non_role_id(self):
        self.cib.append_to_first_tag_name(
            "nodes", '<node id="node-id" uname="node-hostname"/>'
        )

        assert_raise_library_error(
            lambda: lib.create_role(self.cib.tree, "node-id"),
            (
                severities.ERROR,
                report_codes.ID_ALREADY_EXISTS,
                {"id": "node-id"},
            ),
        )


class RemoveRoleTest(LibraryAclTest, ExtendedAssertionsMixin):
    def setUp(self):
        self.xml = """
        <cib>
            <configuration>
                <acls>
                    <acl_role id="role-id"/>
                    <acl_target>
                        <role id="role-id"/>
                    </acl_target>
                    <acl_group>
                        <role id="some-role"/>
                        <role id="role-id"/>
                    </acl_group>
                </acls>
            </configuration>
        </cib>
        """
        self.tree = etree.XML(self.xml)

    def test_success(self):
        expected_xml = """
        <cib>
            <configuration>
                <acls>
                    <acl_target/>
                    <acl_group>
                        <role id="some-role"/>
                    </acl_group>
                </acls>
            </configuration>
        </cib>
        """
        lib.remove_role(self.tree, "role-id")
        assert_xml_equal(expected_xml, etree.tostring(self.tree).decode())

    def test_autodelete(self):
        expected_xml = """
        <cib>
            <configuration>
                <acls>
                    <acl_group>
                        <role id="some-role"/>
                    </acl_group>
                </acls>
            </configuration>
        </cib>
        """
        lib.remove_role(self.tree, "role-id", autodelete_users_groups=True)
        assert_xml_equal(expected_xml, etree.tostring(self.tree).decode())

    def test_id_not_exists(self):
        assert_raise_library_error(
            lambda: lib.remove_role(self.tree.find(".//acls"), "id-of-role"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "context_type": "acls",
                    "context_id": "",
                    "expected_types": ["acl_role"],
                    "id": "id-of-role",
                },
            ),
        )


class AssignRoleTest(LibraryAclTest):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.cib.append_to_first_tag_name(
            "configuration",
            """
                <acls>
                    <acl_role id="role1"/>
                    <acl_role id="role2"/>
                    <acl_target id="target1">
                        <role id="role2"/>
                    </acl_target>
                    <acl_group id="group1"/>
                </acls>
            """,
        )

    def test_success_target(self):
        target = self.cib.tree.find(".//acl_target[@id='target1']")
        lib.assign_role(self.cib.tree, "role1", target)
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
                <acls>
                    <acl_role id="role1"/>
                    <acl_role id="role2"/>
                    <acl_target id="target1">
                        <role id="role2"/>
                        <role id="role1"/>
                    </acl_target>
                    <acl_group id="group1"/>
                </acls>
            """,
            )
        )

    def test_success_group(self):
        group = self.cib.tree.find(".//acl_group[@id='group1']")
        lib.assign_role(self.cib.tree, "role1", group)
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
                <acls>
                    <acl_role id="role1"/>
                    <acl_role id="role2"/>
                    <acl_target id="target1">
                        <role id="role2"/>
                    </acl_target>
                    <acl_group id="group1">
                        <role id="role1"/>
                    </acl_group>
                </acls>
            """,
            )
        )

    def test_role_already_assigned(self):
        target = self.cib.tree.find(".//acl_target[@id='target1']")
        assert_raise_library_error(
            lambda: lib.assign_role(self.cib.tree, "role2", target),
            (
                severities.ERROR,
                report_codes.CIB_ACL_ROLE_IS_ALREADY_ASSIGNED_TO_TARGET,
                {
                    "role_id": "role2",
                    "target_id": "target1",
                },
            ),
        )


@mock.patch("pcs.lib.cib.acl._assign_role")
class AssignAllRoles(TestCase):
    def test_success(self, assign_role):
        # pylint: disable=no-self-use
        assign_role.return_value = []
        lib.assign_all_roles("acl_section", ["1", "2", "3"], "element")
        assign_role.assert_has_calls(
            [
                mock.call("acl_section", "1", "element"),
                mock.call("acl_section", "2", "element"),
                mock.call("acl_section", "3", "element"),
            ],
            any_order=True,
        )

    def test_fail_on_error_report(self, assign_role):
        assign_role.return_value = ["report"]
        self.assertRaises(
            LibraryError,
            lambda: lib.assign_all_roles(
                "acl_section", ["1", "2", "3"], "element"
            ),
        )


class UnassignRoleTest(LibraryAclTest):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.cib.append_to_first_tag_name(
            "configuration",
            """
                <acls>
                    <acl_role id="role1"/>
                    <acl_role id="role2"/>
                    <acl_target id="target1">
                        <role id="role3"/>
                        <role id="role2"/>
                    </acl_target>
                    <acl_group id="group1">
                        <role id="role1"/>
                    </acl_group>
                </acls>
            """,
        )

    def test_success_target(self):
        target = self.cib.tree.find(
            ".//acl_target[@id='{0}']".format("target1")
        )
        lib.unassign_role(target, "role2")
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
                <acls>
                    <acl_role id="role1"/>
                    <acl_role id="role2"/>
                    <acl_target id="target1">
                        <role id="role3"/>
                    </acl_target>
                    <acl_group id="group1">
                        <role id="role1"/>
                    </acl_group>
                </acls>
            """,
            )
        )

    def test_success_group(self):
        group = self.cib.tree.find(".//acl_group[@id='{0}']".format("group1"))
        lib.unassign_role(group, "role1")
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
                <acls>
                    <acl_role id="role1"/>
                    <acl_role id="role2"/>
                    <acl_target id="target1">
                        <role id="role3"/>
                        <role id="role2"/>
                    </acl_target>
                    <acl_group id="group1"/>
                </acls>
            """,
            )
        )

    def test_not_existing_role(self):
        target = self.cib.tree.find(
            ".//acl_target[@id='{0}']".format("target1")
        )
        lib.unassign_role(target, "role3")
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
                <acls>
                    <acl_role id="role1"/>
                    <acl_role id="role2"/>
                    <acl_target id="target1">
                        <role id="role2"/>
                    </acl_target>
                    <acl_group id="group1">
                        <role id="role1"/>
                    </acl_group>
                </acls>
            """,
            )
        )

    def test_role_not_assigned(self):
        target = self.cib.tree.find(
            ".//acl_target[@id='{0}']".format("target1")
        )
        assert_raise_library_error(
            lambda: lib.unassign_role(target, "role1"),
            (
                severities.ERROR,
                report_codes.CIB_ACL_ROLE_IS_NOT_ASSIGNED_TO_TARGET,
                {
                    "role_id": "role1",
                    "target_id": "target1",
                },
            ),
        )

    def test_autodelete(self):
        target = self.cib.tree.find(".//acl_group[@id='{0}']".format("group1"))
        lib.unassign_role(target, "role1", True)
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
                <acls>
                    <acl_role id="role1"/>
                    <acl_role id="role2"/>
                    <acl_target id="target1">
                        <role id="role3"/>
                        <role id="role2"/>
                    </acl_target>
                </acls>
            """,
            )
        )


class AddPermissionsToRoleTest(LibraryAclTest):
    def test_add_for_correct_permissions(self):
        role_id = "role1"
        self.fixture_add_role(role_id)

        lib.add_permissions_to_role(
            self.cib.tree.find(".//acl_role[@id='{0}']".format(role_id)),
            [("read", "xpath", "/whatever")],
        )

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
              <acls>
                <acl_role id="{0}">
                  <acl_permission id="{0}-read" kind="read" xpath="/whatever"/>
                </acl_role>
              </acls>
            """.format(
                    role_id
                ),
            )
        )


class ProvideRoleTest(LibraryAclTest):
    def test_add_role_for_nonexisting_id(self):
        role_id = "new-id"
        lib.provide_role(self.acls, role_id)

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
              <acls>
                <acl_role id="{0}"/>
              </acls>
            """.format(
                    role_id
                ),
            )
        )

    def test_add_role_for_nonexisting_role_id(self):
        self.fixture_add_role("role1")

        role_id = "role1"
        lib.provide_role(self.cib.tree, role_id)

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
              <acls>
                <acl_role id="{0}"/>
              </acls>
            """.format(
                    role_id
                ),
            )
        )


class CreateTargetTest(LibraryAclTest):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.fixture_add_role("target3")
        self.cib.append_to_first_tag_name("acls", '<acl_target id="target2"/>')

    def test_success(self):
        lib.create_target(self.acls, "target1")
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
            <acls>
                <acl_role id="target3"/>
                <acl_target id="target2"/>
                <acl_target id="target1"/>
            </acls>
            """,
            )
        )

    def test_target_id_is_not_unique_id(self):
        lib.create_target(self.acls, "target3")
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
            <acls>
                <acl_role id="target3"/>
                <acl_target id="target2"/>
                <acl_target id="target3"/>
            </acls>
            """,
            )
        )

    def test_target_id_is_not_unique_target_id(self):
        assert_raise_library_error(
            lambda: lib.create_target(self.acls, "target2"),
            (
                severities.ERROR,
                report_codes.CIB_ACL_TARGET_ALREADY_EXISTS,
                {"target_id": "target2"},
            ),
        )


class CreateGroupTest(LibraryAclTest):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.fixture_add_role("group2")

    def test_success(self):
        lib.create_group(self.acls, "group1")
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
            <acls>
                <acl_role id="group2"/>
                <acl_group id="group1"/>
            </acls>
            """,
            )
        )

    def test_existing_id(self):
        assert_raise_library_error(
            lambda: lib.create_group(self.acls, "group2"),
            (
                severities.ERROR,
                report_codes.ID_ALREADY_EXISTS,
                {"id": "group2"},
            ),
        )


class RemoveTargetTest(LibraryAclTest, ExtendedAssertionsMixin):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.fixture_add_role("target2")
        self.cib.append_to_first_tag_name("acls", '<acl_target id="target1"/>')

    def test_success(self):
        lib.remove_target(self.cib.tree, "target1")
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
            <acls>
                <acl_role id="target2"/>
            </acls>
            """,
            )
        )

    def test_not_existing(self):
        assert_raise_library_error(
            lambda: lib.remove_target(self.acls, "target2"),
            (
                severities.ERROR,
                report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                {
                    "id": "target2",
                    "expected_types": ["acl_target"],
                    "current_type": "acl_role",
                },
            ),
        )


class RemoveGroupTest(LibraryAclTest, ExtendedAssertionsMixin):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.fixture_add_role("group2")
        self.cib.append_to_first_tag_name("acls", '<acl_group id="group1"/>')

    def test_success(self):
        lib.remove_group(self.cib.tree, "group1")
        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
            <acls>
                <acl_role id="group2"/>
            </acls>
            """,
            )
        )

    def test_not_existing(self):
        assert_raise_library_error(
            lambda: lib.remove_group(self.cib.tree, "group2"),
            (
                severities.ERROR,
                report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                {
                    "id": "group2",
                    "expected_types": ["acl_group"],
                    "current_type": "acl_role",
                },
            ),
        )


class RemovePermissionForReferenceTest(LibraryAclTest):
    def test_has_no_effect_when_id_not_referenced(self):
        lib.remove_permissions_referencing(self.cib.tree, "dummy")
        self.assert_cib_equal(self.create_cib())

    def test_remove_all_references(self):
        self.cib.append_to_first_tag_name(
            "configuration",
            """
            <acls>
              <acl_role id="role1">
                <acl_permission id="role1-read" kind="read" reference="dummy"/>
                <acl_permission id="role1-read" kind="read" reference="dummy2"/>
              </acl_role>
              <acl_role id="role2">
                <acl_permission id="role2-read" kind="read" reference="dummy"/>
              </acl_role>
            </acls>
        """,
        )

        lib.remove_permissions_referencing(self.cib.tree, "dummy")

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                "configuration",
                """
              <acls>
                <acl_role id="role1">
                  <acl_permission
                    id="role1-read"
                    kind="read"
                    reference="dummy2"
                  />
                </acl_role>
                <acl_role id="role2"/>
              </acls>
            """,
            )
        )


class RemovePermissionTest(LibraryAclTest):
    def setUp(self):
        self.xml = """
        <cib>
            <configuration>
                <acls>
                    <acl_role id="role-id">
                        <acl_permission id="role-permission"/>
                        <acl_permission id="permission-id"/>
                    </acl_role>
                </acls>
            </configuration>
        </cib>
        """
        self.tree = etree.XML(self.xml)

    def test_success(self):
        expected_xml = """
        <cib>
            <configuration>
                <acls>
                    <acl_role id="role-id">
                        <acl_permission id="role-permission"/>
                    </acl_role>
                </acls>
            </configuration>
        </cib>
        """
        lib.remove_permission(self.tree, "permission-id")
        assert_xml_equal(expected_xml, etree.tostring(self.tree).decode())

    def test_not_existing_id(self):
        assert_raise_library_error(
            lambda: lib.remove_permission(self.tree, "role-id"),
            (
                severities.ERROR,
                report_codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                {
                    "id": "role-id",
                    "expected_types": ["acl_permission"],
                    "current_type": "acl_role",
                },
            ),
        )


class GetRoleListTest(LibraryAclTest):
    def test_success(self):
        self.cib.append_to_first_tag_name(
            "configuration",
            """
            <acls>
                <acl_role id="role1" description="desc1">
                    <acl_permission id="role1-perm1" kind="read" xpath="XPATH"/>
                    <acl_permission
                        id="role1-perm2"
                        description="desc"
                        kind="write"
                        reference="id"
                    />
                    <acl_permission
                        id="role1-perm3"
                        kind="deny"
                        object-type="type"
                        attribute="attr"
                    />
                </acl_role>
                <acl_target id="target1"/>
                <acl_role id="role2"/>
            </acls>
            """,
        )
        expected = [
            {
                "id": "role1",
                "description": "desc1",
                "permission_list": [
                    {
                        "id": "role1-perm1",
                        "description": None,
                        "kind": "read",
                        "xpath": "XPATH",
                        "reference": None,
                        "object-type": None,
                        "attribute": None,
                    },
                    {
                        "id": "role1-perm2",
                        "description": "desc",
                        "kind": "write",
                        "xpath": None,
                        "reference": "id",
                        "object-type": None,
                        "attribute": None,
                    },
                    {
                        "id": "role1-perm3",
                        "description": None,
                        "kind": "deny",
                        "xpath": None,
                        "reference": None,
                        "object-type": "type",
                        "attribute": "attr",
                    },
                ],
            },
            {
                "id": "role2",
                "description": None,
                "permission_list": [],
            },
        ]
        self.assertEqual(expected, lib.get_role_list(self.acls))


class GetPermissionListTest(LibraryAclTest):
    def test_success(self):
        role_el = etree.Element("acl_role")
        etree.SubElement(
            role_el,
            "acl_permission",
            {
                "id": "role1-perm1",
                "kind": "read",
                "xpath": "XPATH",
            },
        )
        etree.SubElement(
            role_el,
            "acl_permission",
            {
                "id": "role1-perm2",
                "description": "desc",
                "kind": "write",
                "reference": "id",
            },
        )
        etree.SubElement(
            role_el,
            "acl_permission",
            {
                "id": "role1-perm3",
                "kind": "deny",
                "object-type": "type",
                "attribute": "attr",
            },
        )
        expected = [
            {
                "id": "role1-perm1",
                "description": None,
                "kind": "read",
                "xpath": "XPATH",
                "reference": None,
                "object-type": None,
                "attribute": None,
            },
            {
                "id": "role1-perm2",
                "description": "desc",
                "kind": "write",
                "xpath": None,
                "reference": "id",
                "object-type": None,
                "attribute": None,
            },
            {
                "id": "role1-perm3",
                "description": None,
                "kind": "deny",
                "xpath": None,
                "reference": None,
                "object-type": "type",
                "attribute": "attr",
            },
        ]
        # pylint: disable=protected-access
        self.assertEqual(expected, lib._get_permission_list(role_el))


@mock.patch("pcs.lib.cib.acl.get_target_like_list")
class GetTargetListTest(TestCase):
    def test_success(self, mock_fn):
        mock_fn.return_value = "returned data"
        self.assertEqual("returned data", lib.get_target_list("tree"))
        mock_fn.assert_called_once_with("tree", "acl_target")


@mock.patch("pcs.lib.cib.acl.get_target_like_list")
class GetGroupListTest(TestCase):
    def test_success(self, mock_fn):
        mock_fn.return_value = "returned data"
        self.assertEqual("returned data", lib.get_group_list("tree"))
        mock_fn.assert_called_once_with("tree", "acl_group")


class GetTargetLikeListWithTagTest(LibraryAclTest):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.cib.append_to_first_tag_name(
            "configuration",
            """
                <acls>
                    <acl_target id="target1"/>
                    <acl_group id="group1">
                        <role id="role1"/>
                    </acl_group>
                    <acl_target id="target2">
                        <role id="role1"/>
                        <role id="role2"/>
                        <role id="role3"/>
                    </acl_target>
                    <acl_group id="group2"/>
                </acls>
            """,
        )

    def test_success_targets(self):
        self.assertEqual(
            [
                {
                    "id": "target1",
                    "role_list": [],
                },
                {
                    "id": "target2",
                    "role_list": ["role1", "role2", "role3"],
                },
            ],
            lib.get_target_like_list(self.acls, "acl_target"),
        )

    def test_success_groups(self):
        self.assertEqual(
            [
                {
                    "id": "group1",
                    "role_list": ["role1"],
                },
                {
                    "id": "group2",
                    "role_list": [],
                },
            ],
            lib.get_target_like_list(self.acls, "acl_group"),
        )


class GetRoleListOfTargetTest(LibraryAclTest):
    def test_success(self):
        target_el = etree.Element("target")
        etree.SubElement(target_el, "role", {"id": "role1"})
        etree.SubElement(target_el, "role", {"id": "role2"})
        etree.SubElement(target_el, "role")
        etree.SubElement(target_el, "role", {"id": "role3"})
        self.assertEqual(
            # pylint: disable=protected-access
            ["role1", "role2", "role3"],
            lib._get_role_list_of_target(target_el),
        )


@mock.patch("pcs.lib.cib.acl.find_group")
@mock.patch("pcs.lib.cib.acl.find_target")
class FindTargetOrGroup(TestCase):
    def test_returns_target(self, find_target, find_group):
        del find_group
        find_target.return_value = "target_element"
        self.assertEqual(
            lib.find_target_or_group("acl_section", "target_id"),
            "target_element",
        )
        find_target.assert_called_once_with(
            "acl_section", "target_id", none_if_id_unused=True
        )

    def test_returns_group_if_target_is_none(self, find_target, find_group):
        find_target.return_value = None
        find_group.return_value = "group_element"
        self.assertEqual(
            lib.find_target_or_group("acl_section", "group_id"), "group_element"
        )
        find_target.assert_called_once_with(
            "acl_section", "group_id", none_if_id_unused=True
        )
        find_group.assert_called_once_with(
            "acl_section", "group_id", id_types=["acl_group", "acl_target"]
        )


class Find(TestCase):
    @mock.patch("pcs.lib.cib.acl.find_element_by_tag_and_id")
    def test_map_well_to_common_finder(self, common_finder):
        common_finder.return_value = "element"
        self.assertEqual(
            "element",
            # pylint: disable=protected-access
            lib._find(
                lib.TAG_GROUP,
                "acl_section",
                "group_id",
                none_if_id_unused=True,
                id_types=["some", "types"],
            ),
        )
        common_finder.assert_called_once_with(
            lib.TAG_GROUP,
            "acl_section",
            "group_id",
            none_if_id_unused=True,
            id_types=["some", "types"],
        )

    @mock.patch("pcs.lib.cib.acl.find_element_by_tag_and_id")
    def test_map_well_to_common_finder_with_automatic_desc(self, common_finder):
        common_finder.return_value = "element"
        # pylint: disable=protected-access
        self.assertEqual(
            "element",
            lib._find(
                lib.TAG_GROUP, "acl_section", "group_id", none_if_id_unused=True
            ),
        )
        common_finder.assert_called_once_with(
            lib.TAG_GROUP,
            "acl_section",
            "group_id",
            none_if_id_unused=True,
            id_types=None,
        )
