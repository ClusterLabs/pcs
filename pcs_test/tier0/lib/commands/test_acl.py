from unittest import (
    TestCase,
    mock,
)

import pcs.lib.commands.acl as cmd_acl
from pcs.common import reports
from pcs.lib.env import LibraryEnvironment

from pcs_test.tools import fixture
from pcs_test.tools.assertions import ExtendedAssertionsMixin
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.custom_mock import MockLibraryReportProcessor


class AclCommandsTest(TestCase, ExtendedAssertionsMixin):
    def setUp(self):
        self.mock_rep = MockLibraryReportProcessor()
        self.mock_env = mock.MagicMock(spec_set=LibraryEnvironment)
        self.mock_env.report_processor = self.mock_rep
        self.cib = "cib"
        self.mock_env.get_cib.return_value = self.cib

    def assert_get_cib_called(self):
        self.mock_env.get_cib.assert_called_once_with()

    def assert_same_cib_pushed(self):
        self.mock_env.push_cib.assert_called_once_with()

    def assert_cib_not_pushed(self):
        self.assertEqual(0, self.mock_env.push_cib.call_count)


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
class CibAclSection(TestCase):
    def test_push_cib_on_success(self):
        # pylint: disable=no-self-use
        env = mock.MagicMock()
        env.get_cib = mock.Mock(return_value="cib")
        with cmd_acl.cib_acl_section(env):
            pass
        env.get_cib.assert_called_once_with()
        env.push_cib.assert_called_once_with()

    def test_does_not_push_cib_on_exception(self):
        env = mock.MagicMock()

        def run():
            with cmd_acl.cib_acl_section(env):
                raise AssertionError()

        self.assertRaises(AssertionError, run)
        env.get_cib.assert_called_once_with()
        env.push_cib.assert_not_called()


class CreateRoleTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            resources="""
            <resources>
                <primitive id="R1" class="ocf" provider="pacemaker" type="Dummy"/>
                <primitive id="R2" class="ocf" provider="pacemaker" type="Dummy"/>
            </resources>
            """
        )

    def test_success_just_role(self):
        acl_xml = """
            <acls>
                <acl_role description="desc" id="role_id" />
            </acls>
        """
        self.config.env.push_cib(optional_in_conf=acl_xml)

        cmd_acl.create_role(self.env_assist.get_env(), "role_id", [], "desc")

    def test_success_with_permissions(self):
        acl_xml = """
            <acls>
                <acl_role id="role_id">
                    <acl_permission id="role_id-write" kind="write" reference="R1" />
                    <acl_permission id="role_id-read" kind="read" xpath="./" />
                </acl_role>
            </acls>
        """
        self.config.env.push_cib(optional_in_conf=acl_xml)

        cmd_acl.create_role(
            self.env_assist.get_env(),
            "role_id",
            [("write", "id", "R1"), ("read", "xpath", "./")],
            "",
        )

    def test_id_already_used(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_acl.create_role(self.env_assist.get_env(), "R1", [], "")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(reports.codes.ID_ALREADY_EXISTS, id="R1"),
            ]
        )

    def test_validation(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_acl.create_role(
                self.env_assist.get_env(),
                "#role_id",
                [
                    ("change", "id", "R1"),
                    ("read", "path", "./"),
                    ("deny", "id", "R3"),
                ],
                "",
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_ID_BAD_CHAR,
                    id="#role_id",
                    id_description="ACL role",
                    invalid_character="#",
                    is_first_char=True,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="permission",
                    option_value="change",
                    allowed_values=["read", "write", "deny"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="scope type",
                    option_value="path",
                    allowed_values=["xpath", "id"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="R3",
                    expected_types=["id"],
                    context_type="",
                    context_id="",
                ),
            ]
        )


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.remove_role")
class RemoveRoleTest(AclCommandsTest):
    def test_success(self, mock_remove):
        cmd_acl.remove_role(self.mock_env, "role_id", False)
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "role_id", False)
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.find_target_or_group")
@mock.patch("pcs.lib.cib.acl.assign_role")
class AssignRoleNotSpecific(AclCommandsTest, ExtendedAssertionsMixin):
    def test_success(self, mock_assign, find_target_or_group):
        find_target_or_group.return_value = "target_el"
        cmd_acl.assign_role_not_specific(self.mock_env, "role_id", "target_id")
        self.assert_get_cib_called()
        find_target_or_group.assert_called_once_with(self.cib, "target_id")
        mock_assign.assert_called_once_with(self.cib, "role_id", "target_el")
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.find_target")
@mock.patch("pcs.lib.cib.acl.assign_role")
class AssignRoleToTargetTest(AclCommandsTest):
    def test_success(self, mock_assign, find_target):
        find_target.return_value = "target_el"
        cmd_acl.assign_role_to_target(self.mock_env, "role_id", "target_id")
        self.assert_get_cib_called()
        mock_assign.assert_called_once_with(self.cib, "role_id", "target_el")
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.find_group")
@mock.patch("pcs.lib.cib.acl.assign_role")
class AssignRoleToGroupTest(AclCommandsTest):
    def test_success(self, mock_assign, find_group):
        find_group.return_value = "group_el"
        cmd_acl.assign_role_to_group(self.mock_env, "role_id", "group_id")
        self.assert_get_cib_called()
        mock_assign.assert_called_once_with(self.cib, "role_id", "group_el")
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.unassign_role")
@mock.patch("pcs.lib.cib.acl.find_target_or_group")
class UnassignRoleNotSpecificTest(AclCommandsTest):
    def test_success(self, find_target_or_group, mock_unassign):
        find_target_or_group.return_value = "target_el"
        cmd_acl.unassign_role_not_specific(
            self.mock_env, "role_id", "target_id", False
        )
        self.assert_get_cib_called()
        find_target_or_group.assert_called_once_with(self.cib, "target_id")
        mock_unassign.assert_called_once_with("target_el", "role_id", False)
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.unassign_role")
@mock.patch("pcs.lib.cib.acl.find_target")
class UnassignRoleFromTargetTest(AclCommandsTest):
    def test_success(self, find_target, mock_unassign):
        find_target.return_value = "el"
        cmd_acl.unassign_role_from_target(
            self.mock_env, "role_id", "el_id", False
        )
        self.assert_get_cib_called()
        find_target.assert_called_once_with(self.cib, "el_id")
        mock_unassign.assert_called_once_with("el", "role_id", False)
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.unassign_role")
@mock.patch("pcs.lib.cib.acl.find_group")
class UnassignRoleFromGroupTest(AclCommandsTest):
    def test_success(self, find_group, mock_unassign):
        find_group.return_value = "el"
        cmd_acl.unassign_role_from_group(
            self.mock_env, "role_id", "el_id", False
        )
        self.assert_get_cib_called()
        find_group.assert_called_once_with(self.cib, "el_id")
        mock_unassign.assert_called_once_with("el", "role_id", False)
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.create_target")
@mock.patch("pcs.lib.cib.acl.assign_all_roles")
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


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.create_group")
@mock.patch("pcs.lib.cib.acl.assign_all_roles")
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


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.remove_target")
class RemoveTargetTest(AclCommandsTest):
    def test_success(self, mock_remove):
        cmd_acl.remove_target(self.mock_env, "el_id")
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "el_id")
        self.assert_same_cib_pushed()


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
@mock.patch("pcs.lib.cib.acl.remove_group")
class RemoveGroupTest(AclCommandsTest):
    def test_success(self, mock_remove):
        cmd_acl.remove_group(self.mock_env, "el_id")
        self.assert_get_cib_called()
        mock_remove.assert_called_once_with(self.cib, "el_id")
        self.assert_same_cib_pushed()


class AddPermissionTest(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.runner.cib.load(
            resources="""
            <resources>
                <primitive id="R1" class="ocf" provider="pacemaker" type="Dummy"/>
                <primitive id="R2" class="ocf" provider="pacemaker" type="Dummy"/>
            </resources>
            """,
            optional_in_conf=self.fixture_acls_xml(),
        )

    @staticmethod
    def fixture_acls_xml(roles="", permissions=""):
        return f"""
            <acls>
                <acl_role id="role1">
                    <acl_permission id="role1-write" kind="write" reference="R1" />
                    <acl_permission id="role1-read" kind="read" xpath="/" />
                    {permissions}
                </acl_role>
                {roles}
            </acls>
            """

    def test_existing_role(self):
        self.config.env.push_cib(
            optional_in_conf=self.fixture_acls_xml(
                permissions="""
                  <acl_permission id="role1-deny" kind="deny" reference="R2" />
                  <acl_permission id="role1-write-1" kind="write" xpath="/" />
                """
            )
        )
        cmd_acl.add_permission(
            self.env_assist.get_env(),
            "role1",
            [("deny", "id", "R2"), ("write", "xpath", "/")],
        )

    def test_nonexisting_role(self):
        self.config.env.push_cib(
            optional_in_conf=self.fixture_acls_xml(
                roles="""
                <acl_role id="role2">
                  <acl_permission id="role2-deny" kind="deny" reference="R2" />
                  <acl_permission id="role2-write" kind="write" xpath="/" />
                </acl_role>
                """
            )
        )
        cmd_acl.add_permission(
            self.env_assist.get_env(),
            "role2",
            [("deny", "id", "R2"), ("write", "xpath", "/")],
        )

    def test_not_role(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_acl.add_permission(self.env_assist.get_env(), "R1", []),
            [
                fixture.error(
                    reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                    id="R1",
                    expected_types=["acl_role"],
                    current_type="primitive",
                ),
            ],
            expected_in_processor=False,
        )

    def test_validation(self):
        self.env_assist.assert_raise_library_error(
            lambda: cmd_acl.add_permission(
                self.env_assist.get_env(),
                "#role_id",
                [
                    ("change", "id", "R1"),
                    ("read", "path", "./"),
                    ("deny", "id", "R3"),
                ],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_ID_BAD_CHAR,
                    id="#role_id",
                    id_description="ACL role",
                    invalid_character="#",
                    is_first_char=True,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="permission",
                    option_value="change",
                    allowed_values=["read", "write", "deny"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="scope type",
                    option_value="path",
                    allowed_values=["xpath", "id"],
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    reports.codes.ID_NOT_FOUND,
                    id="R3",
                    expected_types=["id"],
                    context_type="",
                    context_id="",
                ),
            ]
        )


@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
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
@mock.patch("pcs.lib.commands.acl.get_acls", mock.Mock(side_effect=lambda x: x))
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
            cmd_acl.get_config(self.mock_env),
        )
