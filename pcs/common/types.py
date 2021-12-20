from enum import auto

from pcs.common.tools import AutoNameEnum


class CibRuleExpressionType(AutoNameEnum):
    RULE = auto()
    EXPRESSION = auto()  # node attribute expression, named 'expression' in CIB
    DATE_EXPRESSION = auto()
    OP_EXPRESSION = auto()
    RSC_EXPRESSION = auto()


class CibRuleInEffectStatus(AutoNameEnum):
    NOT_YET_IN_EFFECT = auto()
    IN_EFFECT = auto()
    EXPIRED = auto()
    UNKNOWN = auto()


class ResourceRelationType(AutoNameEnum):
    ORDER = auto()
    ORDER_SET = auto()
    INNER_RESOURCES = auto()
    OUTER_RESOURCE = auto()
    RSC_PRIMITIVE = auto()
    RSC_CLONE = auto()
    RSC_GROUP = auto()
    RSC_BUNDLE = auto()
    RSC_UNKNOWN = auto()


class DrRole(AutoNameEnum):
    PRIMARY = auto()
    RECOVERY = auto()


class UnknownCorosyncTransportTypeException(Exception):
    def __init__(self, transport: str) -> None:
        super().__init__()
        self.transport = transport


class CorosyncTransportType(AutoNameEnum):
    UDP = auto()
    UDPU = auto()
    KNET = auto()

    @classmethod
    def from_str(cls, transport: str) -> "CorosyncTransportType":
        try:
            return cls(transport.upper())
        except ValueError:
            raise UnknownCorosyncTransportTypeException(transport) from None
