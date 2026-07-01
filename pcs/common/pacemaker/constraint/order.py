from collections.abc import Sequence
from dataclasses import dataclass

from pcs.common.const import PcmkAction
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.types import CibResourceSetOrderType

from .set import CibResourceSetDto


@dataclass(frozen=True)
class CibConstraintOrderAttributesDto(DataTransferObject):
    constraint_id: str
    symmetrical: bool | None
    require_all: bool | None
    score: str | None
    kind: CibResourceSetOrderType | None


@dataclass(frozen=True)
class CibConstraintOrderDto(DataTransferObject):
    first_resource_id: str
    then_resource_id: str
    first_action: PcmkAction | None
    then_action: PcmkAction | None
    first_resource_instance: int | None
    then_resource_instance: int | None
    attributes: CibConstraintOrderAttributesDto


@dataclass(frozen=True)
class CibConstraintOrderSetDto(DataTransferObject):
    resource_sets: Sequence[CibResourceSetDto]
    attributes: CibConstraintOrderAttributesDto
