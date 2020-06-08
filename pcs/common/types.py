from enum import auto

from pcs.common.tools import AutoNameEnum


class CibNvsetType(AutoNameEnum):
    INSTANCE = auto()
    META = auto()


class CibRuleExpressionType(AutoNameEnum):
    RULE = auto()
    EXPRESSION = auto()
    DATE_EXPRESSION = auto()
    OP_EXPRESSION = auto()
    RSC_EXPRESSION = auto()


class ResourceRelationType(AutoNameEnum):
    ORDER = auto()
    ORDER_SET = auto()
    INNER_RESOURCES = auto()
    OUTER_RESOURCE = auto()


class DrRole(AutoNameEnum):
    PRIMARY = auto()
    RECOVERY = auto()
