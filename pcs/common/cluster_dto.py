from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject
from pcs.common.services_dto import ServiceStatusDto
from pcs.common.version_dto import VersionDto


@dataclass(frozen=True)
class ClusterComponentVersionDto(DataTransferObject):
    corosync: VersionDto
    pacemaker: VersionDto
    pcsd: VersionDto


@dataclass(frozen=True)
class ClusterDaemonsInfoDto(DataTransferObject):
    cluster_configuration_exists: bool
    services: list[ServiceStatusDto]
    versions: ClusterComponentVersionDto
