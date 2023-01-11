from logging import Logger
from unittest import (
    TestCase,
    mock,
)

from pcs.common.file import (
    FileMetadata,
    RawFileError,
)
from pcs.common.file_type_codes import PCS_USERS_CONF
from pcs.lib.auth import const
from pcs.lib.auth.config.facade import Facade
from pcs.lib.auth.config.parser import ParserError
from pcs.lib.auth.config.types import TokenEntry
from pcs.lib.auth.provider import AuthProvider
from pcs.lib.auth.types import AuthUser
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.json import JsonParserException
from pcs.lib.interface.config import ParserErrorException

_FILE_PATH = "file path"
_FILE_METADATA = FileMetadata(
    file_type_code=PCS_USERS_CONF,
    path=_FILE_PATH,
    owner_user_name="root",
    owner_group_name="root",
    permissions=None,
    is_binary=False,
)

_FACADE = Facade(
    [
        TokenEntry(token="token-user1", username="user1", creation_date="now"),
        TokenEntry(token="token-user2", username="user2", creation_date="now"),
    ]
)


class AuthProviderGetFacadeTest(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.file_instance_mock = mock.Mock(spec_set=FileInstance)
        self.file_instance_mock.raw_file.metadata = _FILE_METADATA
        self.logger = mock.Mock(spec_set=Logger)
        with mock.patch.object(
            FileInstance,
            "for_pcs_users_config",
            lambda *_args, **_kwargs: self.file_instance_mock,
        ):
            self.provider = AuthProvider(self.logger)

    def test_io_error(self):
        reason = "reason"
        self.file_instance_mock.read_to_facade.side_effect = RawFileError(
            _FILE_METADATA, RawFileError.ACTION_READ, reason
        )
        self.assertEqual(tuple(), self.provider._get_facade().config)
        self.logger.error.assert_called_once_with(
            "Unable to read file '%s': %s", _FILE_PATH, reason
        )

    def test_json_parser_error(self):
        self.file_instance_mock.read_to_facade.side_effect = (
            JsonParserException(None)
        )
        self.assertEqual(tuple(), self.provider._get_facade().config)
        self.logger.error.assert_called_once_with(
            "Unable to parse file '%s': not valid json", _FILE_PATH
        )

    def test_invalid_format(self):
        reason = "reason"
        self.file_instance_mock.read_to_facade.side_effect = ParserError(reason)
        self.assertEqual(tuple(), self.provider._get_facade().config)
        self.logger.error.assert_called_once_with(
            "Unable to parse file '%s': %s", _FILE_PATH, reason
        )

    def test_other_parsing_error(self):
        self.file_instance_mock.read_to_facade.side_effect = (
            ParserErrorException()
        )
        self.assertEqual(tuple(), self.provider._get_facade().config)
        self.logger.error.assert_called_once_with(
            "Unable to parse file '%s'", _FILE_PATH
        )

    def test_success(self):
        facade = Facade([f"token{i}" for i in range(3)])
        self.file_instance_mock.read_to_facade.return_value = facade
        self.assertEqual(facade, self.provider._get_facade())
        self.logger.error.assert_not_called()


class AuthProviderWriteFacadeTest(TestCase):
    # pylint: disable=protected-access
    def setUp(self):
        self.file_instance_mock = mock.Mock(spec_set=FileInstance)
        self.file_instance_mock.raw_file.metadata = _FILE_METADATA
        self.logger = mock.Mock(spec_set=Logger)
        self.facade = Facade([f"token{i}" for i in range(3)])
        with mock.patch.object(
            FileInstance,
            "for_pcs_users_config",
            lambda *_args, **_kwargs: self.file_instance_mock,
        ):
            self.provider = AuthProvider(self.logger)

    def test_io_error(self):
        reason = "reason"
        self.file_instance_mock.write_facade.side_effect = RawFileError(
            _FILE_METADATA, RawFileError.ACTION_READ, reason
        )
        self.provider._write_facade(self.facade)
        self.logger.error.assert_called_once_with(
            "Action '%s' on file '%s' failed: %s",
            RawFileError.ACTION_READ,
            _FILE_PATH,
            reason,
        )
        self.file_instance_mock.write_facade.assert_called_once_with(
            self.facade, can_overwrite=True
        )

    def test_success(self):
        self.provider._write_facade(self.facade)
        self.logger.error.assert_not_called()
        self.file_instance_mock.write_facade.assert_called_once_with(
            self.facade, can_overwrite=True
        )


@mock.patch.object(AuthProvider, "_get_facade", lambda _self: _FACADE)
@mock.patch("pcs.lib.auth.provider.get_user_groups")
class AuthProviderLoginByTokenTest(TestCase):
    def setUp(self):
        self.logger = mock.Mock(spec_set=Logger)
        self.provider = AuthProvider(self.logger)

    def test_non_existing_token(self, groups_mock):
        self.assertIsNone(self.provider.auth_by_token("non existing token"))
        groups_mock.assert_not_called()

    def test_not_in_admin_group(self, groups_mock):
        groups_mock.return_value = ["group1", "group0"]
        self.assertIsNone(self.provider.auth_by_token("token-user2"))
        groups_mock.assert_called_once_with("user2")

    def test_success(self, groups_mock):
        groups = ["group1", const.ADMIN_GROUP, "group0"]
        groups_mock.return_value = groups
        self.assertEqual(
            AuthUser(username="user1", groups=tuple(groups)),
            self.provider.auth_by_token("token-user1"),
        )
        groups_mock.assert_called_once_with("user1")


@mock.patch("pcs.lib.auth.provider.authenticate_user")
@mock.patch("pcs.lib.auth.provider.get_user_groups")
class AuthProviderLoginByUsernamePasswordTest(TestCase):
    def setUp(self):
        self.logger = mock.Mock(spec_set=Logger)
        self.provider = AuthProvider(self.logger)
        self.username = "user name"
        self.password = "psswd"

    def test_invalid_credentials(self, groups_mock, pam_mock):
        pam_mock.return_value = False
        self.assertIsNone(
            self.provider.auth_by_username_password(
                self.username, self.password
            )
        )
        pam_mock.assert_called_once_with(self.username, self.password)
        groups_mock.assert_not_called()

    def test_not_in_admin_group(self, groups_mock, pam_mock):
        pam_mock.return_value = True
        groups_mock.return_value = ["group1", "group0"]
        self.assertIsNone(
            self.provider.auth_by_username_password(
                self.username, self.password
            )
        )
        pam_mock.assert_called_once_with(self.username, self.password)
        groups_mock.assert_called_once_with(self.username)

    def test_success(self, groups_mock, pam_mock):
        pam_mock.return_value = True
        groups = ["group1", const.ADMIN_GROUP, "group0"]
        groups_mock.return_value = groups
        self.assertEqual(
            AuthUser(username=self.username, groups=tuple(groups)),
            self.provider.auth_by_username_password(
                self.username, self.password
            ),
        )
        pam_mock.assert_called_once_with(self.username, self.password)
        groups_mock.assert_called_once_with(self.username)


@mock.patch.object(AuthProvider, "_get_facade")
@mock.patch.object(AuthProvider, "_write_facade")
class AuthProviderCreateTokenTest(TestCase):
    def setUp(self):
        self.logger = mock.Mock(spec_set=Logger)
        self.provider = AuthProvider(self.logger)

    def test_success(self, write_facade_mock, get_facade_mock):
        token = "new_token"
        facade_mock = mock.Mock(spec_set=Facade)
        facade_mock.add_user.return_value = token
        get_facade_mock.return_value = facade_mock
        self.assertEqual(token, self.provider.create_token("new_user"))
        write_facade_mock.assert_called_once_with(facade_mock)
