import logging
from typing import (
    Collection,
    Sequence,
    Set,
    cast,
)

from pcs.common.file import RawFileError
from pcs.lib.auth.const import (
    ADMIN_GROUP,
    SUPERUSER,
)
from pcs.lib.auth.types import AuthUser
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.json import JsonParserException
from pcs.lib.interface.config import ParserErrorException

from .config.facade import FacadeV2
from .config.parser import ParserError
from .config.types import (
    ClusterPermissions,
    ConfigV2,
    PermissionAccessType,
    PermissionEntry,
    PermissionTargetType,
)


def _get_empty_facade(permissions: Sequence[PermissionEntry]) -> FacadeV2:
    return FacadeV2(
        ConfigV2(
            data_version=1,
            clusters=[],
            permissions=ClusterPermissions(
                local_cluster=permissions,
            ),
        )
    )


def _complete_access_list(
    access_list: Collection[PermissionAccessType],
) -> Set[PermissionAccessType]:
    if PermissionAccessType.SUPERUSER in access_list:
        return set(PermissionAccessType)
    if PermissionAccessType.FULL in access_list:
        return {
            PermissionAccessType.READ,
            PermissionAccessType.WRITE,
            PermissionAccessType.GRANT,
            PermissionAccessType.FULL,
        }
    new = set(access_list)
    if PermissionAccessType.WRITE in access_list:
        return new | {PermissionAccessType.READ}
    return new


class PermissionsChecker:
    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._config_file_instance = FileInstance.for_pcs_settings_config()

    def _get_facade(self) -> FacadeV2:
        if not self._config_file_instance.raw_file.exists():
            self._logger.debug(
                "File '%s' doesn't exist, using default configuration",
                self._config_file_instance.raw_file.metadata.path,
            )
            return _get_empty_facade(
                (
                    PermissionEntry(
                        type=PermissionTargetType.GROUP,
                        name=ADMIN_GROUP,
                        allow=(
                            PermissionAccessType.READ,
                            PermissionAccessType.WRITE,
                            PermissionAccessType.GRANT,
                        ),
                    ),
                )
            )
        try:
            return cast(FacadeV2, self._config_file_instance.read_to_facade())
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
        return _get_empty_facade(tuple())

    def get_permissions(self, auth_user: AuthUser) -> Set[PermissionAccessType]:
        if auth_user.username == SUPERUSER:
            return _complete_access_list((PermissionAccessType.SUPERUSER,))
        facade = self._get_facade()
        all_permissions: Set[PermissionAccessType] = set()
        for target_name, target_type in [
            (auth_user.username, PermissionTargetType.USER)
        ] + [(group, PermissionTargetType.GROUP) for group in auth_user.groups]:
            entry = facade.get_entry(target_name, target_type)
            if entry:
                all_permissions |= set(entry.allow)
        return _complete_access_list(all_permissions)

    def is_authorized(
        self, auth_user: AuthUser, access: PermissionAccessType
    ) -> bool:
        self._logger.debug(
            "Permission check: username=%s groups=%s access=%s",
            auth_user.username,
            ",".join(auth_user.groups),
            str(access.value),
        )
        user_permissions = self.get_permissions(auth_user)
        self._logger.debug(
            "Current user permissions: %s",
            ",".join(
                sorted(permission.value for permission in user_permissions)
            ),
        )
        result = access in user_permissions
        if result:
            self._logger.debug(
                "%s access granted", str(access.value).capitalize()
            )
        else:
            self._logger.debug(
                "%s access denied", str(access.value).capitalize()
            )
        return result
