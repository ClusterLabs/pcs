from typing import (
    Optional,
    Sequence,
)

from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto


@dataclass(frozen=True)
class CibResourceGroupDto(DataTransferObject):
    id: str  # pylint: disable=invalid-name
    description: Optional[str]
    member_ids: Sequence[str]
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]
