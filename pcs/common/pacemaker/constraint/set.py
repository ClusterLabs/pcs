from dataclasses import dataclass

from pcs.common.const import PcmkAction, PcmkRoleType
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.types import (
    CibResourceSetOrdering,
    CibResourceSetOrderType,
)


@dataclass(frozen=True)
class CibResourceSetDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    set_id: str
    sequential: bool | None
    require_all: bool | None
    ordering: CibResourceSetOrdering | None
    action: PcmkAction | None
    role: PcmkRoleType | None
    score: str | None
    kind: CibResourceSetOrderType | None
    resources_ids: list[str]
