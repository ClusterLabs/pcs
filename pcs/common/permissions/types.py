from enum import Enum


class PermissionTargetType(Enum):
    USER = "user"
    GROUP = "group"


class PermissionAccessType(Enum):
    READ = "read"
    WRITE = "write"
    GRANT = "grant"
    FULL = "full"
    SUPERUSER = "superuser"
