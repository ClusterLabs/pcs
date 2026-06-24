from collections.abc import Mapping, Sequence
from dataclasses import dataclass

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
    date_spec: CibRuleDateCommonDto | None
    duration: CibRuleDateCommonDto | None
    expressions: Sequence["CibRuleExpressionDto"]
    as_string: str
