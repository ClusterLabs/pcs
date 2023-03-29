from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
)

from pcs.common.const import PcmkRoleType
from pcs.common.interface.dto import DataTransferObject

from ..rule import CibRuleExpressionDto
from .set import CibResourceSetDto


@dataclass(frozen=True)
class CibConstraintColocationAttributesDto(DataTransferObject):
    constraint_id: str
    score: Optional[str]
    influence: Optional[str]
    lifetime: Sequence[CibRuleExpressionDto]


@dataclass(frozen=True)
class CibConstraintColocationDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    resource_id: str
    with_resource_id: str
    node_attribute: Optional[str]
    resource_role: Optional[PcmkRoleType]
    with_resource_role: Optional[PcmkRoleType]
    resource_instance: Optional[int]
    with_resource_instance: Optional[int]
    attributes: CibConstraintColocationAttributesDto


@dataclass(frozen=True)
class CibConstraintColocationSetDto(DataTransferObject):
    resource_sets: Sequence[CibResourceSetDto]
    attributes: CibConstraintColocationAttributesDto
