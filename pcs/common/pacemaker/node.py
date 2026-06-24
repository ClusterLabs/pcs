from collections.abc import Sequence
from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject
from pcs.common.pacemaker.nvset import CibNvsetDto


@dataclass(frozen=True)
class CibNodeDto(DataTransferObject):
    id: str
    uname: str
    description: str | None
    score: str | None
    type: str | None
    instance_attributes: Sequence[CibNvsetDto]
    utilization: Sequence[CibNvsetDto]


@dataclass(frozen=True)
class CibNodeListDto(DataTransferObject):
    nodes: Sequence[CibNodeDto]
