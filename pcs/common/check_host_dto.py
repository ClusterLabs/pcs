from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject
from pcs.common.services_dto import ServiceStatusDto
from pcs.common.version_dto import ClusterComponentVersionDto


@dataclass(frozen=True)
class CheckHostResultDto(DataTransferObject):
    cluster_configuration_exists: bool
    services: list[ServiceStatusDto]
    versions: ClusterComponentVersionDto
