from typing import Sequence

from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject

from .nvset import CibNvsetDto


@dataclass(frozen=True)
class CibDefaultsDto(DataTransferObject):
    instance_attributes: Sequence[CibNvsetDto]
    meta_attributes: Sequence[CibNvsetDto]
