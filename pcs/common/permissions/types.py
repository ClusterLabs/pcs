from enum import Enum


class PermissionTargetType(str, Enum):
    USER = "user"
    GROUP = "group"


class PermissionGrantedType(str, Enum):
    READ = "read"
    WRITE = "write"
    GRANT = "grant"
    FULL = "full"
