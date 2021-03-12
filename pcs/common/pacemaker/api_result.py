from dataclasses import dataclass
from typing import Sequence

from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class StatusDto(DataTransferObject):
    code: int
    message: str
    errors: Sequence[str]
