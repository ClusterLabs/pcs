from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto
from pcs.common.types import StringSequence


@dataclass(frozen=True)
class CibResourceGroupDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    description: Optional[str]
    member_ids: StringSequence
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]
