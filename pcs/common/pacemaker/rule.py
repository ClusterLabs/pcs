from dataclasses import dataclass
from typing import (
    Mapping,
    Optional,
    Sequence,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.types import (
    CibRuleExpressionType,
    CibRuleInEffectStatus,
)


@dataclass(frozen=True)
class CibRuleDateCommonDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    options: Mapping[str, str]


@dataclass(frozen=True)
class CibRuleExpressionDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    id: str  # pylint: disable=invalid-name
    type: CibRuleExpressionType
    in_effect: CibRuleInEffectStatus  # only valid for type==rule
    options: Mapping[str, str]
    date_spec: Optional[CibRuleDateCommonDto]
    duration: Optional[CibRuleDateCommonDto]
    expressions: Sequence["CibRuleExpressionDto"]
    as_string: str
