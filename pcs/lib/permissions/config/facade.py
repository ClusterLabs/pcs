from dataclasses import replace
from typing import (
    List,
    Optional,
    cast,
)

from pcs.lib.interface.config import SyncVersionFacadeInterface

from .types import (
    ClusterPermissions,
    ConfigV2,
    PermissionEntry,
    PermissionTargetType,
)


class PermissionEntryNotFound(Exception):
    pass


class FacadeV2(SyncVersionFacadeInterface):
    def __init__(self, parsed_config: ConfigV2) -> None:
        super().__init__(parsed_config)

    @property
    def config(self) -> ConfigV2:
        return cast(ConfigV2, super().config)

    @property
    def data_version(self) -> int:
        return self.config.data_version

    def set_data_version(self, new_version: int) -> None:
        return self._set_config(replace(self.config, data_version=new_version))

    def _set_config(self, config: ConfigV2) -> None:
        super()._set_config(config)

    def _set_permissions(self, permissions: List[PermissionEntry]) -> None:
        self._set_config(
            replace(
                self.config,
                permissions=ClusterPermissions(local_cluster=permissions),
            )
        )

    def get_entry(
        self, target: str, target_type: PermissionTargetType
    ) -> Optional[PermissionEntry]:
        for entry in self.config.permissions.local_cluster:
            if entry.type == target_type and entry.name == target:
                return entry
        return None

    def _ensure_not_present(self, entry: PermissionEntry) -> None:
        self._set_permissions(
            [
                item
                for item in self.config.permissions.local_cluster
                if item != entry
            ]
        )

    def remove_permission(self, entry: PermissionEntry) -> None:
        if entry not in self.config.permissions.local_cluster:
            raise PermissionEntryNotFound()
        self._ensure_not_present(entry)

    def set_permission(self, entry: PermissionEntry) -> None:
        existing_entry = self.get_entry(entry.name, entry.type)
        if existing_entry is not None:
            self._ensure_not_present(existing_entry)
        self._set_permissions(
            list(self.config.permissions.local_cluster) + [entry]
        )
