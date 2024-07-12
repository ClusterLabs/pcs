from dataclasses import dataclass
from typing import Sequence

from pcs.common.interface.dto import DataTransferObject
from pcs.common.types import StringSequence


@dataclass(frozen=True)
class CibTagDto(DataTransferObject):
    id: str
    idref_list: StringSequence


@dataclass(frozen=True)
class CibTagListDto(DataTransferObject):
    tags: Sequence[CibTagDto]
