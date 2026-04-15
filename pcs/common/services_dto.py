from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class ServiceStatusDto(DataTransferObject):
    service: str
    installed: bool
    enabled: bool
    running: bool


@dataclass(frozen=True)
class ServicesInfoResultDto(DataTransferObject):
    services: list[ServiceStatusDto]
