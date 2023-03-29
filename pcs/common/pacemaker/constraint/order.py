from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
)

from pcs.common.const import PcmkAction
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.types import CibResourceSetOrderType

from .set import CibResourceSetDto


@dataclass(frozen=True)
class CibConstraintOrderAttributesDto(DataTransferObject):
    constraint_id: str
    symmetrical: Optional[bool]
    require_all: Optional[bool]
    score: Optional[str]
    kind: Optional[CibResourceSetOrderType]


@dataclass(frozen=True)
class CibConstraintOrderDto(DataTransferObject):
    first_resource_id: str
    then_resource_id: str
    first_action: Optional[PcmkAction]
    then_action: Optional[PcmkAction]
    first_resource_instance: Optional[int]
    then_resource_instance: Optional[int]
    attributes: CibConstraintOrderAttributesDto


@dataclass(frozen=True)
class CibConstraintOrderSetDto(DataTransferObject):
    resource_sets: Sequence[CibResourceSetDto]
    attributes: CibConstraintOrderAttributesDto
