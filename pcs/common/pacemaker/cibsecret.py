from dataclasses import dataclass
from typing import Final

from pcs.common.interface.dto import DataTransferObject

CIBSECRET_MARK_VALUE: Final = "lrm://"


@dataclass(frozen=True)
class CibResourceSecretDto(DataTransferObject):
    resource_id: str
    name: str
    value: str


@dataclass(frozen=True)
class CibResourceSecretListDto(DataTransferObject):
    resource_secrets: list[CibResourceSecretDto]
