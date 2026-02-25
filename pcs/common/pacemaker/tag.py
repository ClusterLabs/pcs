from dataclasses import dataclass
from typing import Sequence

from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class CibTagDto(DataTransferObject):
    id: str
    idref_list: list[str]


@dataclass(frozen=True)
class CibTagListDto(DataTransferObject):
    tags: Sequence[CibTagDto]
