import logging
from typing import (
    Optional,
    cast,
)

from pcs.common.file import RawFileError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.json import JsonParserException
from pcs.lib.interface.config import ParserErrorException

from . import const
from .config.facade import Facade
from .config.parser import ParserError
from .pam import authenticate_user
from .tools import (
    UserGroupsError,
    get_user_groups,
)
from .types import AuthUser


class AuthProvider:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._config_file_instance = FileInstance.for_pcs_users_config()

    def _get_facade(self) -> Facade:
        try:
            if not self._config_file_instance.raw_file.exists():
                return Facade([])
            return cast(Facade, self._config_file_instance.read_to_facade())
        except ParserError as e:
            self._logger.error(
                "Unable to parse file '%s': %s",
                self._config_file_instance.raw_file.metadata.path,
                e.msg,
            )
        except JsonParserException:
            self._logger.error(
                "Unable to parse file '%s': not valid json",
                self._config_file_instance.raw_file.metadata.path,
            )
        except ParserErrorException:
            self._logger.error(
                "Unable to parse file '%s'",
                self._config_file_instance.raw_file.metadata.path,
            )
        except RawFileError as e:
            self._logger.error(
                "Unable to read file '%s': %s",
                self._config_file_instance.raw_file.metadata.path,
                e.reason,
            )
        return Facade([])

    def _write_facade(self, facade: Facade) -> bool:
        try:
            self._write_facade_base(facade)
        except RawFileError as e:
            self._logger.error(
                "Action '%s' on file '%s' failed: %s",
                e.action,
                e.metadata.path,
                e.reason,
            )
            return False
        return True

    def _write_facade_base(self, facade: Facade) -> None:
        self._config_file_instance.write_facade(facade, can_overwrite=True)

    def login_user(self, username: str) -> Optional[AuthUser]:
        try:
            groups = get_user_groups(username)
        except UserGroupsError:
            self._logger.error(
                "Unable to determine groups of user '%s'", username
            )
            return None
        if const.ADMIN_GROUP not in groups:
            self._logger.debug(
                "User '%s' is not a member of '%s' group",
                username,
                const.ADMIN_GROUP,
            )
            return None
        self._logger.debug("Successful login by '%s'", username)
        return AuthUser(username=username, groups=tuple(groups))

    def auth_by_token(self, token: str) -> Optional[AuthUser]:
        username = self._get_facade().get_user(token)
        if username is None:
            return None
        return self.login_user(username)

    def auth_by_username_password(
        self, username: str, password: str
    ) -> Optional[AuthUser]:
        if authenticate_user(username, password):
            return self.login_user(username)
        self._logger.info(
            "Failed login by '%s': bad username or password", username
        )
        return None

    def create_token(self, username: str) -> Optional[str]:
        facade = self._get_facade()
        token = facade.add_user(username)
        if self._write_facade(facade):
            return token
        return None
