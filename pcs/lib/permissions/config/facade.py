from dataclasses import replace
from typing import (
    List,
    Optional,
)

from pcs.lib.interface.config import FacadeInterface

from .types import (
    ClusterPermissions,
    ConfigV2,
    PermissionEntry,
    PermissionTargetType,
)


class PermissionEntryNotFound(Exception):
    pass


class FacadeV2(FacadeInterface):
    _parsed_config: ConfigV2

    def __init__(self, parsed_config: ConfigV2) -> None:
        super().__init__(parsed_config)
        self._set_new_config(parsed_config)

    def _set_new_config(self, config: ConfigV2) -> None:
        self._set_config(config)
        self._parsed_config = config

    def _set_permissions(self, permissions: List[PermissionEntry]) -> None:
        self._set_new_config(
            replace(
                self._parsed_config,
                permissions=ClusterPermissions(local_cluster=permissions),
            )
        )

    def get_entry(
        self, target: str, target_type: PermissionTargetType
    ) -> Optional[PermissionEntry]:
        for entry in self._parsed_config.permissions.local_cluster:
            if entry.type == target_type and entry.name == target:
                return entry
        return None

    def _ensure_not_present(self, entry: PermissionEntry) -> None:
        self._set_permissions(
            [
                item
                for item in self._parsed_config.permissions.local_cluster
                if item != entry
            ]
        )

    def remove_permission(self, entry: PermissionEntry) -> None:
        if entry not in self._parsed_config.permissions.local_cluster:
            raise PermissionEntryNotFound()
        self._ensure_not_present(entry)

    def set_permission(self, entry: PermissionEntry) -> None:
        existing_entry = self.get_entry(entry.name, entry.type)
        if existing_entry is not None:
            self._ensure_not_present(existing_entry)
        self._set_permissions(
            list(self._parsed_config.permissions.local_cluster) + [entry]
        )
