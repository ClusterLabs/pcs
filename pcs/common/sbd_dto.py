from dataclasses import dataclass
from typing import Optional

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
    watchdog: Optional[SbdWatchdogStatusDto] = None
    device_list: Optional[list[SbdDeviceStatusDto]] = None
