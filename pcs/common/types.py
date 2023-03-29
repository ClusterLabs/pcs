from collections.abc import Set
from enum import (
    Enum,
    auto,
)
from typing import (
    Generator,
    Literal,
    MutableSequence,
    Optional,
    Type,
    TypeVar,
    Union,
)

StringSequence = Union[MutableSequence[str], tuple[str, ...]]
StringCollection = Union[StringSequence, Set[str]]
StringIterable = Union[StringCollection, Generator[str, None, None]]


class AutoNameEnum(str, Enum):
    def _generate_next_value_(name, start, count, last_values):  # type: ignore
        # pylint: disable=no-self-argument
        del start, count, last_values
        return name


T = TypeVar("T", bound=AutoNameEnum)


def str_to_enum(enum_type: Type[T], value: Optional[str]) -> Optional[T]:
    if value:
        value = value.upper()
        if value in {item.value for item in enum_type}:
            return enum_type(value)
    return None


PcmkScore = Union[int, Literal["INFINITY", "+INFINITY", "-INFINITY"]]


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
