from collections.abc import Sequence
from dataclasses import dataclass

from pcs.common.const import PcmkRoleType
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.types import CibTicketLossPolicy

from .set import CibResourceSetDto


@dataclass(frozen=True)
class CibConstraintTicketAttributesDto(DataTransferObject):
    constraint_id: str
    ticket: str
    loss_policy: CibTicketLossPolicy | None


@dataclass(frozen=True)
class CibConstraintTicketDto(DataTransferObject):
    resource_id: str
    role: PcmkRoleType | None
    attributes: CibConstraintTicketAttributesDto


@dataclass(frozen=True)
class CibConstraintTicketSetDto(DataTransferObject):
    resource_sets: Sequence[CibResourceSetDto]
    attributes: CibConstraintTicketAttributesDto
