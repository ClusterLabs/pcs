from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_equal,
    assert_xml_equal,
    ExtendedAssertionsMixin,
)
from pcs.test.tools.misc import get_test_resource as rc
from pcs.test.tools.xml import get_xml_manipulation_creator_from_file
from pcs.test.tools.pcs_unittest import mock, TestCase

from pcs.common import report_codes
from pcs.lib.cib import acl as lib
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity as severities,
)

class LibraryAclTest(TestCase):
    def setUp(self):
        self.create_cib = get_xml_manipulation_creator_from_file(
            rc("cib-empty.xml")
        )
        self.cib = self.create_cib()

    def fixture_add_role(self, role_id):
        self.cib.append_to_first_tag_name(
            'configuration',
            '<acls><acl_role id="{0}"/></acls>'.format(role_id)
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
            ("deny", "xpath", "xpath")
        ]
        lib.validate_permissions(self.tree, permissions)

    def test_unknown_permission(self):
        permissions = [
            ("read", "id", "test-id"),
            ("unknown", "id", "another-id"),
            ("write", "xpath", "my xpath"),
            ("allow", "xpath", "xpath")
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
                },
                None
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_value": "allow",
                    "option_name": "permission",
                    "allowed_values": self.allowed_permissions,
                },
                None
            )
        )

    def test_unknown_scope(self):
        permissions = [
            ("read", "id", "test-id"),
            ("write", "not_id", "test-id"),
            ("deny", "not_xpath", "some xpath"),
            ("read", "xpath", "xpath")
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
                },
                None
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTION_VALUE,
                {
                    "option_value": "not_xpath",
                    "option_name": "scope type",
                    "allowed_values": self.allowed_scopes,
                },
                None
            )
        )

    def test_not_existing_id(self):
        permissions = [
            ("read", "id", "test-id"),
            ("write", "id", "id"),
            ("deny", "id", "last"),
            ("write", "xpath", "maybe xpath")
        ]
        assert_raise_library_error(
            lambda: lib.validate_permissions(self.tree, permissions),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "id",
                    "id_description": "id",
                }
            ),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "last",
                    "id_description": "id",
                }
            )
        )


class FindRoleTest(LibraryAclTest, ExtendedAssertionsMixin):
    def test_success(self):
        xml = """
        <xml>
            <acl_role id="role-id"/>
            <role id="role-id"/>
        </xml>
        """
        assert_xml_equal(
            '<acl_role id="role-id"/>',
            etree.tostring(lib.find_role(etree.XML(xml), "role-id")).decode()
        )

    def test_not_exist(self):
        xml = """
        <xml>
            <role id="role-id"/>
        </xml>
        """
        self.assert_raises(
            lib.AclRoleNotFound,
            lambda: lib.find_role(etree.XML(xml), "role-id"),
            {"role_id": "role-id"}
        )


class FindPermissionTest(LibraryAclTest):
    def test_success(self):
        xml = """
        <cib>
            <acls>
                <acl_permission id="permission-id"/>
                <acl_permission id="permission-id2"/>
            </acls>
        </cib>
        """
        assert_xml_equal(
            '<acl_permission id="permission-id"/>',
            etree.tostring(lib._find_permission(
                etree.XML(xml), "permission-id")
            ).decode()
        )

    def test_not_exist(self):
        xml = """
        <cib>
            <acls>
                <acl_permission id="permission-id2"/>
            </acls>
        </cib>
        """
        assert_raise_library_error(
            lambda: lib._find_permission(etree.XML(xml), "permission-id"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "permission-id",
                    "id_description": "permission",
                }
            )
        )


class CreateRoleTest(LibraryAclTest):
    def test_create_for_new_role_id(self):
        role_id = 'new-id'
        lib.create_role(self.cib.tree, role_id)

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name(
                'configuration',
                '<acls><acl_role id="{0}"/></acls>'.format(role_id)
            )
        )

    def test_refuse_invalid_id(self):
        assert_raise_library_error(
            lambda: lib.create_role(self.cib.tree, '#invalid'),
            (
                severities.ERROR,
                report_codes.INVALID_ID,
                {'id': '#invalid'},
            ),
        )

    def test_refuse_existing_non_role_id(self):
        self.cib.append_to_first_tag_name(
            'nodes',
            '<node id="node-id" uname="node-hostname"/>'
        )

        assert_raise_library_error(
            lambda: lib.create_role(self.cib.tree, 'node-id'),
            (
                severities.ERROR,
                report_codes.ID_ALREADY_EXISTS,
                {'id': 'node-id'},
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
        self.assert_raises(
            lib.AclRoleNotFound,
            lambda: lib.remove_role(self.tree, "id-of-role"),
            {"role_id": "id-of-role"}
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
            """
        )

    def test_success_target(self):
        target = self.cib.tree.find(
            ".//acl_target[@id='{0}']".format("target1")
        )
        role = self.cib.tree.find(".//acl_role[@id='{0}']".format("role1"))
        lib.assign_role(target, role)
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
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
            """
        ))

    def test_sucess_group(self):
        group = self.cib.tree.find(".//acl_group[@id='{0}']".format("group1"))
        role = self.cib.tree.find(".//acl_role[@id='{0}']".format("role1"))
        lib.assign_role(group, role)
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
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
            """
        ))

    def test_role_already_assigned(self):
        target = self.cib.tree.find(
            ".//acl_target[@id='{0}']".format("target1")
        )
        role = self.cib.tree.find(".//acl_role[@id='{0}']".format("role2"))
        assert_raise_library_error(
            lambda: lib.assign_role(target, role),
            (
                severities.ERROR,
                report_codes.CIB_ACL_ROLE_IS_ALREADY_ASSIGNED_TO_TARGET,
                {
                    "role_id": "role2",
                    "target_id": "target1",
                }
            )
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
            """
        )

    def test_success_target(self):
        target = self.cib.tree.find(
            ".//acl_target[@id='{0}']".format("target1")
        )
        lib.unassign_role(target, "role2")
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
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
            """
        ))

    def test_success_group(self):
        group = self.cib.tree.find(".//acl_group[@id='{0}']".format("group1"))
        lib.unassign_role(group, "role1")
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
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
            """
        ))

    def test_not_existing_role(self):
        target = self.cib.tree.find(
            ".//acl_target[@id='{0}']".format("target1")
        )
        lib.unassign_role(target, "role3")
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
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
            """
        ))

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
                }
            )
        )

    def test_autodelete(self):
        target = self.cib.tree.find(".//acl_group[@id='{0}']".format("group1"))
        lib.unassign_role(target, "role1", True)
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
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
            """
        ))


class FindTargetTest(LibraryAclTest, ExtendedAssertionsMixin):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.cib.append_to_first_tag_name(
            "configuration", '<acl_target id="target1"/>'
        )
        self.cib.append_to_first_tag_name(
            "configuration",
            """
                <acls>
                    <acl_target id="target1" description="test"/>
                </acls>
            """
        )

    def test_success(self):
        assert_xml_equal(
            '<acl_target id="target1" description="test"/>',
            etree.tostring(lib.find_target(self.cib.tree, "target1")).decode()
        )

    def test_not_found(self):
        self.assert_raises(
            lib.AclTargetNotFound,
            lambda: lib.find_target(self.cib.tree, "target2"),
            {"target_id": "target2"}
        )


class FindGroupTest(LibraryAclTest, ExtendedAssertionsMixin):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.cib.append_to_first_tag_name(
            "configuration", '<acl_group id="group2"/>'
        )
        self.cib.append_to_first_tag_name(
            "configuration",
            """
                <acls>
                    <acl_group id="group1" description="desc"/>
                </acls>
            """
        )

    def test_success(self):
        assert_xml_equal(
            '<acl_group id="group1" description="desc"/>',
            etree.tostring(lib.find_group(self.cib.tree, "group1")).decode()
        )

    def test_not_found(self):
        self.assert_raises(
            lib.AclGroupNotFound,
            lambda: lib.find_group(self.cib.tree, "group2"),
            {"group_id": "group2"}
        )


class AddPermissionsToRoleTest(LibraryAclTest):
    def test_add_for_correct_permissions(self):
        role_id = 'role1'
        self.fixture_add_role(role_id)

        lib.add_permissions_to_role(
            self.cib.tree.find(".//acl_role[@id='{0}']".format(role_id)),
            [('read', 'xpath', '/whatever')]
        )

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name('configuration', '''
              <acls>
                <acl_role id="{0}">
                  <acl_permission id="{0}-read" kind="read" xpath="/whatever"/>
                </acl_role>
              </acls>
            '''.format(role_id))
        )


class ProvideRoleTest(LibraryAclTest):
    def test_add_role_for_nonexisting_id(self):
        role_id = 'new-id'
        lib.provide_role(self.cib.tree, role_id)

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name('configuration', '''
              <acls>
                <acl_role id="{0}"/>
              </acls>
            '''.format(role_id))
        )

    def test_add_role_for_nonexisting_role_id(self):
        self.fixture_add_role('role1')

        role_id = 'role1'
        lib.provide_role(self.cib.tree, role_id)

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name('configuration', '''
              <acls>
                <acl_role id="{0}"/>
              </acls>
            '''.format(role_id))
        )


class CreateTargetTest(LibraryAclTest):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.fixture_add_role("target3")
        self.cib.append_to_first_tag_name("acls", '<acl_target id="target2"/>')

    def test_success(self):
        lib.create_target(self.cib.tree, "target1")
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
            "configuration",
            """
            <acls>
                <acl_role id="target3"/>
                <acl_target id="target2"/>
                <acl_target id="target1"/>
            </acls>
            """
        ))

    def test_target_id_is_not_unique_id(self):
        lib.create_target(self.cib.tree, "target3")
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
            "configuration",
            """
            <acls>
                <acl_role id="target3"/>
                <acl_target id="target2"/>
                <acl_target id="target3"/>
            </acls>
            """
        ))

    def test_target_id_is_not_unique_target_id(self):
        assert_raise_library_error(
            lambda: lib.create_target(self.cib.tree, "target2"),
            (
                severities.ERROR,
                report_codes.CIB_ACL_TARGET_ALREADY_EXISTS,
                {"target_id":"target2"}
            )
        )


class CreateGroupTest(LibraryAclTest):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.fixture_add_role("group2")

    def test_success(self):
        lib.create_group(self.cib.tree, "group1")
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
            "configuration",
            """
            <acls>
                <acl_role id="group2"/>
                <acl_group id="group1"/>
            </acls>
            """
        ))

    def test_existing_id(self):
        assert_raise_library_error(
            lambda: lib.create_group(self.cib.tree, "group2"),
            (
                severities.ERROR,
                report_codes.ID_ALREADY_EXISTS,
                {"id": "group2"}
            )
        )


class RemoveTargetTest(LibraryAclTest, ExtendedAssertionsMixin):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.fixture_add_role("target2")
        self.cib.append_to_first_tag_name("acls", '<acl_target id="target1"/>')

    def test_success(self):
        lib.remove_target(self.cib.tree, "target1")
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
            "configuration",
            """
            <acls>
                <acl_role id="target2"/>
            </acls>
            """
        ))

    def test_not_existing(self):
        assert_raise_library_error(
            lambda: lib.remove_target(self.cib.tree, "target2"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {"id": "target2"}
            )
        )


class RemoveGroupTest(LibraryAclTest, ExtendedAssertionsMixin):
    def setUp(self):
        LibraryAclTest.setUp(self)
        self.fixture_add_role("group2")
        self.cib.append_to_first_tag_name("acls", '<acl_group id="group1"/>')

    def test_success(self):
        lib.remove_group(self.cib.tree, "group1")
        self.assert_cib_equal(self.create_cib().append_to_first_tag_name(
            "configuration",
            """
            <acls>
                <acl_role id="group2"/>
            </acls>
            """
        ))

    def test_not_existing(self):
        assert_raise_library_error(
            lambda: lib.remove_group(self.cib.tree, "group2"),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {"id": "group2"}
            )
        )


class RemovePermissionForReferenceTest(LibraryAclTest):
    def test_has_no_efect_when_id_not_referenced(self):
        lib.remove_permissions_referencing(self.cib.tree, 'dummy')
        self.assert_cib_equal(self.create_cib())

    def test_remove_all_references(self):
        self.cib.append_to_first_tag_name('configuration', '''
            <acls>
              <acl_role id="role1">
                <acl_permission id="role1-read" kind="read" reference="dummy"/>
                <acl_permission id="role1-read" kind="read" reference="dummy2"/>
              </acl_role>
              <acl_role id="role2">
                <acl_permission id="role2-read" kind="read" reference="dummy"/>
              </acl_role>
            </acls>
        ''')

        lib.remove_permissions_referencing(self.cib.tree, 'dummy')

        self.assert_cib_equal(
            self.create_cib().append_to_first_tag_name('configuration', '''
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
            ''')
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
                report_codes.ID_NOT_FOUND,
                {
                    "id": "role-id",
                    "id_description": "permission",
                }
            )
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
            """
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
                    }
                ]
            },
            {
                "id": "role2",
                "description": None,
                "permission_list": [],
            }
        ]
        self.assertEqual(expected, lib.get_role_list(self.cib.tree))


class GetPermissionListTest(LibraryAclTest):
    def test_success(self):
        role_el = etree.Element("acl_role")
        etree.SubElement(
            role_el,
            "acl_permission",
            {
                "id":"role1-perm1",
                "kind": "read",
                "xpath": "XPATH",
            }
        )
        etree.SubElement(
            role_el,
            "acl_permission",
            {
                "id": "role1-perm2",
                "description": "desc",
                "kind": "write",
                "reference": "id",
            }
        )
        etree.SubElement(
            role_el,
            "acl_permission",
            {
                "id": "role1-perm3",
                "kind": "deny",
                "object-type": "type",
                "attribute": "attr",
            }
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
            }
        ]
        self.assertEqual(expected, lib._get_permission_list(role_el))


@mock.patch("pcs.lib.cib.acl._get_target_like_list_with_tag")
class GetTargetListTest(TestCase):
    def test_success(self, mock_fn):
        mock_fn.return_value = "returned data"
        self.assertEqual("returned data", lib.get_target_list("tree"))
        mock_fn.assert_called_once_with("tree", "acl_target")


@mock.patch("pcs.lib.cib.acl._get_target_like_list_with_tag")
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
            """
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
                }
            ],
            lib._get_target_like_list_with_tag(self.cib.tree, "acl_target")
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
                }
            ],
            lib._get_target_like_list_with_tag(self.cib.tree, "acl_group")
        )


class GetRoleListOfTargetTest(LibraryAclTest):
    def test_success(self):
        target_el = etree.Element("target")
        etree.SubElement(target_el, "role", {"id": "role1"})
        etree.SubElement(target_el, "role", {"id": "role2"})
        etree.SubElement(target_el, "role")
        etree.SubElement(target_el, "role", {"id": "role3"})
        self.assertEqual(
            ["role1", "role2", "role3"], lib._get_role_list_of_target(target_el)
        )


class AclErrorToReportItemTest(TestCase, ExtendedAssertionsMixin):
    def test_acl_target_not_found(self):
        assert_report_item_equal(
            lib.acl_error_to_report_item(lib.AclTargetNotFound("id")),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "id",
                    "id_description": "user",
                }
            )
        )

    def test_acl_group_not_found(self):
        assert_report_item_equal(
            lib.acl_error_to_report_item(lib.AclGroupNotFound("id")),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "id",
                    "id_description": "group",
                }
            )
        )

    def test_acl_role_not_found(self):
        assert_report_item_equal(
            lib.acl_error_to_report_item(lib.AclRoleNotFound("id")),
            (
                severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "id",
                    "id_description": "role",
                }
            )
        )

    def test_unknown_exception(self):
        self.assert_raises(
            LibraryError,
            lambda: lib.acl_error_to_report_item(LibraryError())
        )

