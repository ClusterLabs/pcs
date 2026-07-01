from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject
from pcs.common.services_dto import ServiceStatusDto


@dataclass(frozen=True)
class SbdWatchdogStatusDto(DataTransferObject):
    path: str
    exists: bool
    is_supported: bool


@dataclass(frozen=True)
class SbdDeviceStatusDto(DataTransferObject):
    path: str
    exists: bool
    is_block_device: bool


@dataclass(frozen=True)
class SbdCheckResultDto(DataTransferObject):
    sbd_service: ServiceStatusDto
    watchdog: SbdWatchdogStatusDto | None = None
    device_list: list[SbdDeviceStatusDto] | None = None
