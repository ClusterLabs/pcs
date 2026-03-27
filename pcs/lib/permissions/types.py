from enum import Enum


class PermissionRequiredType(str, Enum):
    NONE = "none"
    READ = "read"
    WRITE = "write"
    GRANT = "grant"
    FULL = "full"
    SUPERUSER = "superuser"
