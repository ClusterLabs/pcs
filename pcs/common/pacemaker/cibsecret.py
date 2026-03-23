from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class CibResourceSecretDto(DataTransferObject):
    resource_id: str
    name: str
    value: str


@dataclass(frozen=True)
class CibResourceSecretListDto(DataTransferObject):
    resource_secrets: list[CibResourceSecretDto]
