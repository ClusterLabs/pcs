from dataclasses import dataclass
from typing import Optional, Sequence

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto


@dataclass(frozen=True)
class CibNodeDto(DataTransferObject):
    id: str
    uname: str
    description: Optional[str]
    score: Optional[str]
    type: Optional[str]
    instance_attributes: Sequence[CibNvsetDto]
    utilization: Sequence[CibNvsetDto]


@dataclass(frozen=True)
class CibNodeListDto(DataTransferObject):
    nodes: Sequence[CibNodeDto]
