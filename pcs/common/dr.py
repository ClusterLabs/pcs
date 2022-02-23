from dataclasses import dataclass
from typing import Sequence

from pcs.common.interface.dto import DataTransferObject
from pcs.common.types import DrRole


@dataclass(frozen=True)
class DrConfigNodeDto(DataTransferObject):
    name: str


@dataclass(frozen=True)
class DrConfigSiteDto(DataTransferObject):
    site_role: DrRole
    node_list: Sequence[DrConfigNodeDto]


@dataclass(frozen=True)
class DrConfigDto(DataTransferObject):
    local_site: DrConfigSiteDto
    remote_site_list: Sequence[DrConfigSiteDto]


@dataclass(frozen=True)
class DrSiteStatusDto(DataTransferObject):
    local_site: bool
    site_role: DrRole
    status_plaintext: str
    status_successfully_obtained: bool
