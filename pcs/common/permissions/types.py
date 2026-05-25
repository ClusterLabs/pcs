from enum import StrEnum


class PermissionTargetType(StrEnum):
    USER = "user"
    GROUP = "group"


class PermissionGrantedType(StrEnum):
    READ = "read"
    WRITE = "write"
    GRANT = "grant"
    FULL = "full"
