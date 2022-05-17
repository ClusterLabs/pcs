import grp
import logging
from dataclasses import dataclass
from typing import (
    List,
    Optional,
    Sequence,
    cast,
)

from pcs.common.file import RawFileError
from pcs.daemon.auth import get_user_groups_sync
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.json import JsonParserException
from pcs.lib.interface.config import ParserErrorException

from . import const
from .config.facade import Facade
from .config.parser import ParserError


@dataclass(frozen=True)
class AuthUser:
    username: str
    groups: Sequence[str]

    @property
    def is_superuser(self) -> bool:
        return self.username == const.SUPERUSER


# TODO: remove
def _get_user_groups(username: str) -> List[str]:
    return sorted(
        group.gr_name for group in grp.getgrall() if username in group.gr_mem
    )


class AuthProvider:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._config_file_instance = FileInstance.for_pcs_users_config()

    def _get_facade(self) -> Facade:
        try:
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

    def _write_facade(self, facade: Facade) -> None:
        try:
            self._config_file_instance.write_facade(facade, can_overwrite=True)
        except RawFileError as e:
            self._logger.error(
                "Action '%s' on file '%s' failed: %s",
                e.action,
                e.metadata.path,
                e.reason,
            )

    def login_by_token(self, token: str) -> Optional[AuthUser]:
        username = self._get_facade().get_user(token)
        if username is None:
            return None
        groups = tuple(get_user_groups_sync(username))
        if const.ADMIN_GROUP in groups:
            return AuthUser(username=username, groups=groups)
        return None

    def create_token(self, username: str) -> str:
        facade = self._get_facade()
        token = facade.add_user(username)
        self._write_facade(facade)
        return token
