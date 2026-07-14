from collections.abc import Sequence
from dataclasses import dataclass

from pcs.common.const import PcmkRoleType
from pcs.common.interface.dto import DataTransferObject

from ..rule import CibRuleExpressionDto
from .set import CibResourceSetDto


@dataclass(frozen=True)
class CibConstraintColocationAttributesDto(DataTransferObject):
    constraint_id: str
    score: str | None
    influence: str | None
    lifetime: Sequence[CibRuleExpressionDto]


@dataclass(frozen=True)
class CibConstraintColocationDto(DataTransferObject):
    resource_id: str
    with_resource_id: str
    node_attribute: str | None
    resource_role: PcmkRoleType | None
    with_resource_role: PcmkRoleType | None
    resource_instance: int | None
    with_resource_instance: int | None
    attributes: CibConstraintColocationAttributesDto


@dataclass(frozen=True)
class CibConstraintColocationSetDto(DataTransferObject):
    resource_sets: Sequence[CibResourceSetDto]
    attributes: CibConstraintColocationAttributesDto
