from collections.abc import Sequence
from dataclasses import dataclass

from pcs.common.const import PcmkRoleType
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.types import CibResourceDiscovery

from ..rule import CibRuleExpressionDto
from .set import CibResourceSetDto


@dataclass(frozen=True)
class CibConstraintLocationAttributesDto(DataTransferObject):
    constraint_id: str
    score: str | None
    node: str | None
    rules: Sequence[CibRuleExpressionDto]
    lifetime: Sequence[CibRuleExpressionDto]
    resource_discovery: CibResourceDiscovery | None


@dataclass(frozen=True)
class CibConstraintLocationDto(DataTransferObject):
    resource_id: str | None
    resource_pattern: str | None
    role: PcmkRoleType | None
    attributes: CibConstraintLocationAttributesDto


@dataclass(frozen=True)
class CibConstraintLocationSetDto(DataTransferObject):
    resource_sets: Sequence[CibResourceSetDto]
    attributes: CibConstraintLocationAttributesDto
