from collections.abc import Sequence
from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto


@dataclass(frozen=True)
class CibResourceCloneDto(DataTransferObject):
    id: str
    description: str | None
    member_id: str
    meta_attributes: Sequence[CibNvsetDto]
    instance_attributes: Sequence[CibNvsetDto]
