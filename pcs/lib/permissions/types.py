from enum import StrEnum


class PermissionRequiredType(StrEnum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    GRANT = "grant"
    FULL = "full"
    SUPERUSER = "superuser"
