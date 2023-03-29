from dataclasses import dataclass
from typing import Optional

from pcs.common.const import (
    PcmkAction,
    PcmkRoleType,
)
from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.types import (
    CibResourceSetOrdering,
    CibResourceSetOrderType,
)
from pcs.common.types import StringSequence


@dataclass(frozen=True)
class CibResourceSetDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    set_id: str
    sequential: Optional[bool]
    require_all: Optional[bool]
    ordering: Optional[CibResourceSetOrdering]
    action: Optional[PcmkAction]
    role: Optional[PcmkRoleType]
    score: Optional[str]
    kind: Optional[CibResourceSetOrderType]
    resources_ids: StringSequence
