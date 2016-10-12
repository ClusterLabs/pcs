from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)


from pcs.test.tools.assertions import (
    assert_raise_library_error,
    ExtendedAssertionsMixin,
)
from pcs.test.tools.custom_mock import MockLibraryReportProcessor
from pcs.test.tools.pcs_unittest import mock, TestCase

from pcs.common import report_codes
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity as Severities,
)
from pcs.lib.env import LibraryEnvironment

import pcs.lib.commands.acl as cmd_acl
import pcs.lib.cib.acl as acl_lib


REQUIRED_CIB_VERSION = (2, 0, 0)


class AclCommandsTest(TestCase, ExtendedAssertionsMixin):
    def setUp(self):
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)
        self.mock_env.report_processor = self.mock_rep
        self.cib = "cib"
        self.mock_env.get_cib.return_value = self.cib

    def assert_get_cib_called(self):
        self.mock_env.get_cib.assert_called_once_with(REQUIRED_CIB_VERSION)

    def assert_same_cib_pushed(self):
        self.mock_env.push_cib.assert_called_once_with(self.cib)

    def assert_cib_not_pushed(self):
        self.assertEqual(0, self.mock_env.push_cib.call_count)



@mock.patch("pcs.lib.cib.acl.validate_permissions")
@mock.patch("pcs.lib.cib.acl.create_role")
@mock.patch("pcs.lib.cib.acl.add_permissions_to_role")
class CreateRoleTest(AclCommandsTest):
    def test_success(self, mock_add_perm, mock_create_role, mock_validate):
        perm_list = ["my", "list"]
        mock_create_role.return_value = "role el"
        cmd_acl.create_role(self.mock_env, "role_id", perm_list, "desc")
        self.assert_get_cib_called()
        mock_validate.assert_called_once_with(self.cib, perm_list)
        mock_create_role.assert_called_once_with(self.cib, "role_id", "desc")
        mock_add_perm.assert_called_once_with("role el", perm_list)
        self.assert_same_cib_pushed()

    def test_no_permission(
        self, mock_add_perm, mock_create_role, mock_validate
    ):
        mock_create_role.return_value = "role el"
        cmd_acl.create_role(self.mock_env, "role_id", [], "desc")
        self.assert_get_cib_called()
        self.assertEqual(0, mock_validate.call_count)
        mock_create_role.assert_called_once_with(self.cib, "role_id", "desc")
        self.assertEqual(0, mock_add_perm.call_count)
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.cib.acl.remove_role")
class RemoveRoleTest(AclCommandsTest):
    def test_success_no_autodelete(self, mock_remove):
        cmd_acl.remove_role(self.mock_env, "role_id", False)
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "role_id", False)
        self.assert_same_cib_pushed()

    def test_success_autodelete(self, mock_remove):
        cmd_acl.remove_role(self.mock_env, "role_id", True)
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "role_id", True)
        self.assert_same_cib_pushed()

    def test_role_not_found(self, mock_remove):
        mock_remove.side_effect = acl_lib.AclRoleNotFound("role_id")
        assert_raise_library_error(
            lambda: cmd_acl.remove_role(self.mock_env, "role_id", True),
            (
                Severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "role_id",
                    "id_description": "role",
                }
            )
        )
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "role_id", True)
        self.assert_cib_not_pushed()


@mock.patch("pcs.lib.commands.acl._get_target_or_group")
@mock.patch("pcs.lib.cib.acl.assign_role")
@mock.patch("pcs.lib.cib.acl.find_role")
@mock.patch("pcs.lib.cib.acl.acl_error_to_report_item")
class AssignRoleNotSpecific(AclCommandsTest, ExtendedAssertionsMixin):
    def test_success(
        self, mock_error_convert, mock_find_role, mock_assign, mock_get_tg
    ):
        mock_get_tg.return_value = "target_el"
        mock_find_role.return_value = "role_el"
        cmd_acl.assign_role_not_specific(self.mock_env, "role_id", "target_id")
        self.assert_get_cib_called()
        mock_get_tg.assert_called_once_with(self.cib, "target_id")
        mock_find_role.assert_called_once_with(self.cib, "role_id")
        mock_assign.assert_called_once_with("target_el", "role_el")
        self.assertEqual(0, mock_error_convert.call_count)
        self.assert_same_cib_pushed()

    def test_failure(
        self, mock_error_convert, mock_find_role, mock_assign, mock_get_tg
    ):
        mock_get_tg.return_value = "target_el"
        exception_obj = acl_lib.AclRoleNotFound("role_id")
        mock_find_role.side_effect = exception_obj
        self.assert_raises(
            LibraryError,
            lambda: cmd_acl.assign_role_not_specific(
                self.mock_env, "role_id", "target_id"
            )
        )
        self.assert_get_cib_called()
        self.assertEqual(0, mock_assign.call_count)
        mock_error_convert.assert_called_once_with(exception_obj)
        self.assert_cib_not_pushed()


@mock.patch("pcs.lib.cib.acl.find_target")
@mock.patch("pcs.lib.cib.acl.find_group")
class GetTargetOrGroupTest(AclCommandsTest):
    def test_target(self, mock_find_group, mock_find_target):
        mock_find_target.return_value = "target_el"
        self.assertEqual(
            "target_el", cmd_acl._get_target_or_group(self.cib, "target_id")
        )
        mock_find_target.assert_called_once_with(self.cib, "target_id")
        self.assertEqual(0, mock_find_group.call_count)

    def test_group(self, mock_find_group, mock_find_target):
        mock_find_target.side_effect = acl_lib.AclTargetNotFound("group_id")
        mock_find_group.return_value = "group_el"
        self.assertEqual(
            "group_el", cmd_acl._get_target_or_group(self.cib, "group_id")
        )
        mock_find_target.assert_called_once_with(self.cib, "group_id")
        mock_find_group.assert_called_once_with(self.cib, "group_id")

    def test_not_found(self, mock_find_group, mock_find_target):
        mock_find_target.side_effect = acl_lib.AclTargetNotFound("id")
        mock_find_group.side_effect = acl_lib.AclGroupNotFound("id")
        assert_raise_library_error(
            lambda: cmd_acl._get_target_or_group(self.cib, "id"),
            (
                Severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "id",
                    "id_description": "user/group",
                }
            )
        )
        mock_find_target.assert_called_once_with(self.cib, "id")
        mock_find_group.assert_called_once_with(self.cib, "id")


@mock.patch("pcs.lib.cib.acl.assign_role")
@mock.patch("pcs.lib.cib.acl.find_role")
@mock.patch("pcs.lib.cib.acl.find_target")
@mock.patch("pcs.lib.cib.acl.acl_error_to_report_item")
class AssignRoleToTargetTest(AclCommandsTest):
    def test_success(
        self, mock_error_convert, mock_target, mock_role, mock_assign
    ):
        mock_target.return_value = "target_el"
        mock_role.return_value = "role_el"
        cmd_acl.assign_role_to_target(self.mock_env, "role_id", "target_id")
        self.assert_get_cib_called()
        mock_target.assert_called_once_with(self.cib, "target_id")
        mock_role.assert_called_once_with(self.cib, "role_id")
        mock_assign.assert_called_once_with("target_el", "role_el")
        self.assert_same_cib_pushed()
        self.assertEqual(0, mock_error_convert.call_count)

    def test_failure(
        self, mock_error_convert, mock_target, mock_role, mock_assign
    ):
        exception_obj = acl_lib.AclTargetNotFound("target_id")
        mock_target.side_effect = exception_obj
        mock_role.return_value = "role_el"
        self.assert_raises(
            LibraryError,
            lambda: cmd_acl.assign_role_to_target(
                self.mock_env, "role_id", "target_id"
            )
        )
        self.assert_get_cib_called()
        mock_target.assert_called_once_with(self.cib, "target_id")
        mock_error_convert.assert_called_once_with(exception_obj)
        self.assertEqual(0, mock_assign.call_count)
        self.assert_cib_not_pushed()


@mock.patch("pcs.lib.cib.acl.assign_role")
@mock.patch("pcs.lib.cib.acl.find_role")
@mock.patch("pcs.lib.cib.acl.find_group")
@mock.patch("pcs.lib.cib.acl.acl_error_to_report_item")
class AssignRoleToGroupTest(AclCommandsTest):
    def test_success(
        self, mock_error_convert, mock_group, mock_role, mock_assign
    ):
        mock_group.return_value = "group_el"
        mock_role.return_value = "role_el"
        cmd_acl.assign_role_to_group(self.mock_env, "role_id", "group_id")
        self.assert_get_cib_called()
        mock_group.assert_called_once_with(self.cib, "group_id")
        mock_role.assert_called_once_with(self.cib, "role_id")
        mock_assign.assert_called_once_with("group_el", "role_el")
        self.assert_same_cib_pushed()
        self.assertEqual(0, mock_error_convert.call_count)

    def test_failure(
        self, mock_error_convert, mock_group, mock_role, mock_assign
    ):
        exception_obj = acl_lib.AclGroupNotFound("group_id")
        mock_group.side_effect = exception_obj
        mock_role.return_value = "role_el"
        self.assert_raises(
            LibraryError,
            lambda: cmd_acl.assign_role_to_group(
                self.mock_env, "role_id", "group_id"
            )
        )
        self.assert_get_cib_called()
        mock_group.assert_called_once_with(self.cib, "group_id")
        mock_error_convert.assert_called_once_with(exception_obj)
        self.assertEqual(0, mock_assign.call_count)
        self.assert_cib_not_pushed()


@mock.patch("pcs.lib.commands.acl._get_target_or_group")
@mock.patch("pcs.lib.cib.acl.unassign_role")
class UnassignRoleNotSpecificTest(AclCommandsTest):
    def test_success(self,  mock_unassign, mock_tg):
        mock_tg.return_value = "target_el"
        cmd_acl.unassign_role_not_specific(
            self.mock_env, "role_id", "target_id", False
        )
        self.assert_get_cib_called()
        mock_tg.assert_called_once_with(self.cib, "target_id")
        mock_unassign.assert_called_once_with("target_el", "role_id", False)
        self.assert_same_cib_pushed()

    def test_success_with_autodelete(self,  mock_unassign, mock_tg):
        mock_tg.return_value = "target_el"
        cmd_acl.unassign_role_not_specific(
            self.mock_env, "role_id", "target_id", True
        )
        self.assert_get_cib_called()
        mock_tg.assert_called_once_with(self.cib, "target_id")
        mock_unassign.assert_called_once_with("target_el", "role_id", True)
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.cib.acl.unassign_role")
@mock.patch("pcs.lib.cib.acl.find_target")
@mock.patch("pcs.lib.cib.acl.acl_error_to_report_item")
class UnassignRoleFromTargetTest(AclCommandsTest):
    def test_success(self, mock_error_convert, mock_find_el, mock_unassign):
        mock_find_el.return_value = "el"
        cmd_acl.unassign_role_from_target(
            self.mock_env, "role_id", "el_id", False
        )
        self.assert_get_cib_called()
        mock_find_el.assert_called_once_with(self.cib, "el_id")
        mock_unassign.assert_called_once_with("el", "role_id", False)
        self.assert_same_cib_pushed()
        self.assertEqual(0, mock_error_convert.call_count)

    def test_success_autodelete(
        self, mock_error_convert, mock_find_el, mock_unassign
    ):
        mock_find_el.return_value = "el"
        cmd_acl.unassign_role_from_target(
            self.mock_env, "role_id", "el_id", True
        )
        self.assert_get_cib_called()
        mock_find_el.assert_called_once_with(self.cib, "el_id")
        mock_unassign.assert_called_once_with("el", "role_id", True)
        self.assert_same_cib_pushed()
        self.assertEqual(0, mock_error_convert.call_count)

    def test_failure(self, mock_error_convert, mock_find_el, mock_unassign):
        exception_obj = acl_lib.AclTargetNotFound("el_id")
        mock_find_el.side_effect = exception_obj
        self.assert_raises(
            LibraryError,
            lambda: cmd_acl.unassign_role_from_target(
                self.mock_env, "role_id", "el_id", False
            )
        )
        self.assert_get_cib_called()
        mock_find_el.assert_called_once_with(self.cib, "el_id")
        self.assertEqual(0, mock_unassign.call_count)
        self.assert_cib_not_pushed()
        mock_error_convert.assert_called_once_with(exception_obj)


@mock.patch("pcs.lib.cib.acl.unassign_role")
@mock.patch("pcs.lib.cib.acl.find_group")
@mock.patch("pcs.lib.cib.acl.acl_error_to_report_item")
class UnassignRoleFromGroupTest(AclCommandsTest):
    def test_success(self, mock_error_convert, mock_find_el, mock_unassign):
        mock_find_el.return_value = "el"
        cmd_acl.unassign_role_from_group(
            self.mock_env, "role_id", "el_id", False
        )
        self.assert_get_cib_called()
        mock_find_el.assert_called_once_with(self.cib, "el_id")
        mock_unassign.assert_called_once_with("el", "role_id", False)
        self.assert_same_cib_pushed()
        self.assertEqual(0, mock_error_convert.call_count)

    def test_success_autodelete(
        self, mock_error_convert, mock_find_el, mock_unassign
    ):
        mock_find_el.return_value = "el"
        cmd_acl.unassign_role_from_group(
            self.mock_env, "role_id", "el_id", True
        )
        self.assert_get_cib_called()
        mock_find_el.assert_called_once_with(self.cib, "el_id")
        mock_unassign.assert_called_once_with("el", "role_id", True)
        self.assert_same_cib_pushed()
        self.assertEqual(0, mock_error_convert.call_count)

    def test_failure(self, mock_error_convert, mock_find_el, mock_unassign):
        exception_obj = acl_lib.AclGroupNotFound("el_id")
        mock_find_el.side_effect = exception_obj
        self.assert_raises(
            LibraryError,
            lambda: cmd_acl.unassign_role_from_group(
                self.mock_env, "role_id", "el_id", False
            )
        )
        self.assert_get_cib_called()
        mock_find_el.assert_called_once_with(self.cib, "el_id")
        self.assertEqual(0, mock_unassign.call_count)
        self.assert_cib_not_pushed()
        mock_error_convert.assert_called_once_with(exception_obj)


@mock.patch("pcs.lib.cib.acl.assign_role")
@mock.patch("pcs.lib.cib.acl.find_role")
class AssignRolesToElement(AclCommandsTest):
    def test_success(self, mock_role, mock_assign):
        mock_role.side_effect = lambda _, el_id: "{0}_el".format(el_id)
        cmd_acl._assign_roles_to_element(
            self.cib, "el", ["role1", "role2", "role3"]
        )
        mock_role.assert_has_calls([
            mock.call(self.cib, "role1"),
            mock.call(self.cib, "role2"),
            mock.call(self.cib, "role3")
        ])
        mock_assign.assert_has_calls([
            mock.call("el", "role1_el"),
            mock.call("el", "role2_el"),
            mock.call("el", "role3_el")
        ])

    def test_failure(self, mock_role, mock_assign):
        def _mock_role(_, el_id):
            if el_id in ["role1", "role3"]:
                raise acl_lib.AclRoleNotFound(el_id)
            elif el_id == "role2":
                return "role2_el"
            else:
                raise AssertionError("unexpected input")

        mock_role.side_effect = _mock_role
        assert_raise_library_error(
            lambda: cmd_acl._assign_roles_to_element(
                self.cib, "el", ["role1", "role2", "role3"]
            ),
            (
                Severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "role1",
                    "id_description": "role",
                }
            ),
            (
                Severities.ERROR,
                report_codes.ID_NOT_FOUND,
                {
                    "id": "role3",
                    "id_description": "role",
                }
            )
        )
        mock_role.assert_has_calls([
            mock.call(self.cib, "role1"),
            mock.call(self.cib, "role2"),
            mock.call(self.cib, "role3")
        ])
        mock_assign.assert_called_once_with("el", "role2_el")


@mock.patch("pcs.lib.cib.acl.create_target")
@mock.patch("pcs.lib.commands.acl._assign_roles_to_element")
class CreateTargetTest(AclCommandsTest):
    def test_success(self, mock_assign, mock_create):
        mock_create.return_value = "el"
        cmd_acl.create_target(
            self.mock_env, "el_id", ["role1", "role2", "role3"]
        )
        self.assert_get_cib_called()
        mock_create.assert_called_once_with(self.cib, "el_id")
        mock_assign(self.cib, "el", ["role1", "role2", "role3"])
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.cib.acl.create_group")
@mock.patch("pcs.lib.commands.acl._assign_roles_to_element")
class CreateGroupTest(AclCommandsTest):
    def test_success(self, mock_assign, mock_create):
        mock_create.return_value = "el"
        cmd_acl.create_group(
            self.mock_env, "el_id", ["role1", "role2", "role3"]
        )
        self.assert_get_cib_called()
        mock_create.assert_called_once_with(self.cib, "el_id")
        mock_assign(self.cib, "el", ["role1", "role2", "role3"])
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.cib.acl.remove_target")
class RemoveTargetTest(AclCommandsTest):
    def test_success(self, mock_remove):
        cmd_acl.remove_target(self.mock_env, "el_id")
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "el_id")
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.cib.acl.remove_group")
class RemoveGroupTest(AclCommandsTest):
    def test_success(self, mock_remove):
        cmd_acl.remove_group(self.mock_env, "el_id")
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "el_id")
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.cib.acl.validate_permissions")
@mock.patch("pcs.lib.cib.acl.provide_role")
@mock.patch("pcs.lib.cib.acl.add_permissions_to_role")
class AddPermissionTest(AclCommandsTest):
    def test_success(self, mock_add_perm, mock_provide_role, mock_validate):
        mock_provide_role.return_value = "role_el"
        cmd_acl.add_permission(self.mock_env, "role_id", "permission_list")
        self.assert_get_cib_called()
        mock_validate.assert_called_once_with(self.cib, "permission_list")
        mock_provide_role.assert_called_once_with(self.cib, "role_id")
        mock_add_perm.assert_called_once_with("role_el", "permission_list")
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.cib.acl.remove_permission")
class RemovePermission(AclCommandsTest):
    def test_success(self, mock_remove):
        cmd_acl.remove_permission(self.mock_env, "id")
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "id")
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.cib.acl.get_target_list")
@mock.patch("pcs.lib.cib.acl.get_group_list")
@mock.patch("pcs.lib.cib.acl.get_role_list")
class GetConfigTest(AclCommandsTest):
    def test_success(self, mock_role, mock_group, mock_target):
        mock_role.return_value = "role"
        mock_group.return_value = "group"
        mock_target.return_value = "target"
        self.assertEqual(
            {
                "target_list": "target",
                "group_list": "group",
                "role_list": "role",
            },
            cmd_acl.get_config(self.mock_env)
        )

