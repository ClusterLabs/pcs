from dataclasses import dataclass
from typing import (
    Mapping,
    Optional,
    Sequence,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.types import CibNvsetType


@dataclass(frozen=True)
class CibNvpairDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    name: str
    value: str


@dataclass(frozen=True)
class CibNvsetDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    type: CibNvsetType
    options: Mapping[str, str]
    rule: Optional[CibRuleExpressionDto]
    nvpairs: Sequence[CibNvpairDto]
