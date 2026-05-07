from dataclasses import dataclass
from typing import Optional

from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class BoothConfigFileDto(DataTransferObject):
    name: str
    data: str


@dataclass(frozen=True)
class BoothConfigAndAuthfileDto(DataTransferObject):
    config: BoothConfigFileDto
    authfile: Optional[BoothConfigFileDto]
