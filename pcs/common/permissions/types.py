from enum import StrEnum


class PermissionTargetType(StrEnum):
    USER = "user"
    GROUP = "group"

    @property
    def label(self) -> str:
        return self.value.capitalize()

    @property
    def description(self) -> str:
        return ""


class PermissionGrantedType(StrEnum):
    READ = "read"
    WRITE = "write"
    GRANT = "grant"
    FULL = "full"

    @property
    def label(self) -> str:
        return self.value.capitalize()

    @property
    def description(self) -> str:
        return _PERMISSION_TYPE_DESCRIPTIONS[self]

    @property
    def dependencies(self) -> list["PermissionGrantedType"]:
        return _PERMISSION_DEPENDENCIES[self]


_PERMISSION_TYPE_DESCRIPTIONS = {
    PermissionGrantedType.READ: "Allows to view cluster settings",
    PermissionGrantedType.WRITE: (
        "Allows to modify cluster settings except permissions and ACLs"
    ),
    PermissionGrantedType.GRANT: (
        "Allows to modify cluster permissions and ACLs"
    ),
    PermissionGrantedType.FULL: (
        "Allows unrestricted access to a cluster except for adding nodes"
    ),
}

_PERMISSION_DEPENDENCIES = {
    PermissionGrantedType.READ: [],
    PermissionGrantedType.WRITE: [PermissionGrantedType.READ],
    PermissionGrantedType.GRANT: [],
    PermissionGrantedType.FULL: [
        PermissionGrantedType.READ,
        PermissionGrantedType.WRITE,
        PermissionGrantedType.GRANT,
    ],
}
