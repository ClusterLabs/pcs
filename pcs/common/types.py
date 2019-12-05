from enum import auto

from pcs.common.tools import AutoNameEnum


class ResourceRelationType(AutoNameEnum):
    ORDER = auto()
    ORDER_SET = auto()
    INNER_RESOURCES = auto()
    OUTER_RESOURCE = auto()


class DrRole(AutoNameEnum):
    PRIMARY = auto()
    RECOVERY = auto()
