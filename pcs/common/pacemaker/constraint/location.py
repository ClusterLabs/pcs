from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
)

from pcs.common.const import PcmkRoleType
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.types import CibResourceDiscovery

from ..rule import CibRuleExpressionDto
from .set import CibResourceSetDto


@dataclass(frozen=True)
class CibConstraintLocationAttributesDto(DataTransferObject):
    constraint_id: str
    score: Optional[str]
    node: Optional[str]
    rules: Sequence[CibRuleExpressionDto]
    lifetime: Sequence[CibRuleExpressionDto]
    resource_discovery: Optional[CibResourceDiscovery]


@dataclass(frozen=True)
class CibConstraintLocationDto(DataTransferObject):
    resource_id: Optional[str]
    resource_pattern: Optional[str]
    role: Optional[PcmkRoleType]
    attributes: CibConstraintLocationAttributesDto


@dataclass(frozen=True)
class CibConstraintLocationSetDto(DataTransferObject):
    resource_sets: Sequence[CibResourceSetDto]
    attributes: CibConstraintLocationAttributesDto
