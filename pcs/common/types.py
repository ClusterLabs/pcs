from enum import (
    Enum,
    auto,
)
from typing import (
    MutableSequence,
    Union,
)

StringSequence = Union[MutableSequence[str], tuple[str, ...]]
StringCollection = Union[StringSequence, set[str]]


class AutoNameEnum(str, Enum):
    def _generate_next_value_(name, start, count, last_values):  # type: ignore
        # pylint: disable=no-self-argument
        del start, count, last_values
        return name


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


class CorosyncNodeAddressType(Enum):
    IPV4 = "IPv4"
    IPV6 = "IPv6"
    FQDN = "FQDN"
    UNRESOLVABLE = "unresolvable"
