from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import unittest

from pcs.test.library_test_tools import LibraryAssertionMixin
from pcs.test.library_test_tools import get_xml_manipulation_creator
from pcs.test.tools.resources import get_test_resource as rc

from pcs.lib.cib import acl as lib
from pcs.lib import error_codes
from pcs.lib.errors import ReportItemSeverity as severities

class LibraryAclTest(unittest.TestCase, LibraryAssertionMixin):
    def setUp(self):
        self.create_cib = get_xml_manipulation_creator(rc("cib-empty.xml"))
        self.cib = self.create_cib()

    def fixture_add_role(self, role_id):
        self.cib.append_to_first_tag_name(
            'configuration',
            '<acls><acl_role id="{0}"/></acls>'.format(role_id)
        )

class CreateRoleTest(LibraryAclTest):
    def test_create_for_new_role_id(self):
        role_id = 'new-id'
        lib.create_role(self.cib.tree, role_id)

        self.assert_xml_equal(
            self.create_cib().append_to_first_tag_name(
                'configuration',
                '<acls><acl_role id="{0}"/></acls>'.format(role_id)
            )
        )

    def test_refuse_invalid_id(self):
        self.assert_raise_library_error(
            lambda: lib.create_role(self.cib.tree, '#invalid'),
            (
                severities.ERROR,
                error_codes.INVALID_ID,
                {'id': '#invalid'},
            ),
        )

    def test_refuse_existing_role_id(self):
        role_id = 'role1'
        self.fixture_add_role(role_id)
        self.assert_raise_library_error(
            lambda: lib.create_role(self.cib.tree, role_id),
            (
                severities.ERROR,
                error_codes.ACL_ROLE_ALREADY_EXISTS,
                {'id': role_id},
            ),
        )

    def test_refuse_existing_non_role_id(self):
        self.cib.append_to_first_tag_name(
            'nodes',
            '<node id="node-id" uname="node-hostname"/>'
        )

        self.assert_raise_library_error(
            lambda: lib.create_role(self.cib.tree, 'node-id'),
            (
                severities.ERROR,
                error_codes.ID_ALREADY_EXISTS,
                {'id': 'node-id'},
            ),
        )

class AddPermissionsToRoleTest(LibraryAclTest):
    def test_add_for_correct_permissions(self):
        role_id = 'role1'
        self.fixture_add_role(role_id)

        lib.add_permissions_to_role(
            self.cib.tree, role_id, [('read', 'xpath', '/whatever')]
        )

        self.assert_xml_equal(
            self.create_cib().append_to_first_tag_name('configuration', '''
              <acls>
                <acl_role id="{0}">
                  <acl_permission id="{0}-read" kind="read" xpath="/whatever"/>
                </acl_role>
              </acls>
            '''.format(role_id))
        )


    def test_refuse_add_for_nonexistent_role_id(self):
        role_id = 'role1'
        self.assert_raise_library_error(
            lambda: lib.add_permissions_to_role(
                self.cib.tree, role_id, [('read', 'xpath', '/whatever')]
            ),
            (
                severities.ERROR,
                error_codes.ACL_ROLE_NOT_FOUND,
                {'role_id': role_id},
            ),
        )

    def test_refuse_bad_permission_and_bad_scope_type(self):
        role_id = 'role1'
        self.fixture_add_role(role_id)

        self.assert_raise_library_error(
            lambda: lib.add_permissions_to_role(
                self.cib.tree, role_id, [('readX', 'xpathX', '/whatever')]
            ),
            (
                severities.ERROR,
                error_codes.BAD_ACL_PERMISSION,
                {'permission': 'readX'},
            ),
            (
                severities.ERROR,
                error_codes.BAD_ACL_SCOPE_TYPE,
                {'scope_type': 'xpathX'},
            ),
        )

    def test_refuse_pointing_to_nonexisten_id(self):
        role_id = 'role1'
        self.fixture_add_role(role_id)

        self.assert_raise_library_error(
            lambda: lib.add_permissions_to_role(
                self.cib.tree, role_id, [('read', 'id', 'non-existent')]
            ),
            (
                severities.ERROR,
                error_codes.ID_NOT_FOUND,
                {'id': 'non-existent'}
            ),
        )

class ProvideRoleTest(LibraryAclTest):
    def test_add_role_for_nonexisting_id(self):
        role_id = 'new-id'
        lib.provide_role(self.cib.tree, role_id)

        self.assert_xml_equal(
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

        self.assert_xml_equal(
            self.create_cib().append_to_first_tag_name('configuration', '''
              <acls>
                <acl_role id="{0}"/>
              </acls>
            '''.format(role_id))
        )

class RemovePermissionForReferenceTest(LibraryAclTest):
    def test_has_no_efect_when_id_not_referenced(self):
        lib.remove_permissions_referencing(self.cib.tree, 'dummy')
        self.assert_xml_equal(self.create_cib())

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

        self.assert_xml_equal(
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
