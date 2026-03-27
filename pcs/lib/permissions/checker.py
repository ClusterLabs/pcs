import logging

from pcs.common.permissions.types import (
    PermissionGrantedType,
    PermissionTargetType,
)
from pcs.common.reports.processor import ReportProcessorToLog
from pcs.lib.auth.const import SUPERUSER
from pcs.lib.auth.types import AuthUser

from .tools import complete_access_list, read_pcs_settings_conf
from .types import PermissionRequiredType


class PermissionsChecker:
    __REQUIRED_TO_GRANTED_ACCESS_TYPE_MAP = {
        PermissionRequiredType.FULL: PermissionGrantedType.FULL,
        PermissionRequiredType.GRANT: PermissionGrantedType.GRANT,
        PermissionRequiredType.WRITE: PermissionGrantedType.WRITE,
        PermissionRequiredType.READ: PermissionGrantedType.READ,
    }

    def __init__(self, logger: logging.Logger) -> None:
        self._logger = logger
        self._report_processor = ReportProcessorToLog(self._logger)

    def _get_permissions(
        self, auth_user: AuthUser
    ) -> set[PermissionGrantedType]:
        facade, report_list = read_pcs_settings_conf()
        self._report_processor.report_list(report_list)

        all_permissions = set()
        for target_name, target_type in [
            (auth_user.username, PermissionTargetType.USER)
        ] + [(group, PermissionTargetType.GROUP) for group in auth_user.groups]:
            entry = facade.get_entry(target_name, target_type)
            if entry:
                all_permissions |= set(entry.allow)
        return complete_access_list(all_permissions)

    def is_authorized(
        self, auth_user: AuthUser, access: PermissionRequiredType
    ) -> bool:
        self._logger.debug(
            "Permission check: username=%s groups=%s access=%s",
            auth_user.username,
            ",".join(auth_user.groups),
            str(access.value),
        )

        if auth_user.username == SUPERUSER:
            # Superuser has all the permissions, we dont need to read the file
            result = True
        elif access is PermissionRequiredType.NONE:
            # We dont need to read the file
            result = True
        elif access in self.__REQUIRED_TO_GRANTED_ACCESS_TYPE_MAP:
            user_permissions = self._get_permissions(auth_user)
            result = (
                self.__REQUIRED_TO_GRANTED_ACCESS_TYPE_MAP[access]
                in user_permissions
            )
        else:
            result = False

        self._logger.debug(
            "%s access %s",
            str(access.value).capitalize(),
            "granted" if result else "denied",
        )
        return result
