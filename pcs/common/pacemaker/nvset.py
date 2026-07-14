from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.rule import CibRuleExpressionDto


@dataclass(frozen=True)
class CibNvpairDto(DataTransferObject):
    id: str
    name: str
    value: str


@dataclass(frozen=True)
class CibNvsetDto(DataTransferObject):
    id: str
    options: Mapping[str, str]
    rule: CibRuleExpressionDto | None
    nvpairs: Sequence[CibNvpairDto]


@dataclass(frozen=True)
class ListCibNvsetDto(DataTransferObject):
    nvsets: Sequence[CibNvsetDto]
