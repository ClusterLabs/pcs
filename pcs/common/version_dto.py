from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class VersionDto(DataTransferObject):
    major: int
    minor: int
    revision: int

    def __str__(self) -> str:
        return f"{self.major}.{self.minor}.{self.revision}"


@dataclass(frozen=True)
class ClusterComponentVersionDto(DataTransferObject):
    corosync: VersionDto
    pacemaker: VersionDto
    pcsd: VersionDto
