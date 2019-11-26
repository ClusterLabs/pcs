from enum import auto
from typing import (
    Any,
    Mapping,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.tools import AutoNameEnum


class DrRole(AutoNameEnum):
    PRIMARY = auto()
    RECOVERY = auto()


class DrSiteStatusDto(DataTransferObject):
    def __init__(
        self,
        local_site: bool,
        site_role: DrRole,
        status_plaintext: str,
        status_successfully_obtained: bool
    ):
        self.local_site = local_site
        self.site_role = site_role
        self.status_plaintext = status_plaintext
        self.status_successfully_obtained = status_successfully_obtained

    def to_dict(self) -> Mapping[str, Any]:
        return dict(
            local_site=self.local_site,
            site_role=self.site_role.value,
            status_plaintext=self.status_plaintext,
            status_successfully_obtained=self.status_successfully_obtained,
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DrSiteStatusDto":
        return cls(
            payload["local_site"],
            DrRole(payload["site_role"]),
            payload["status_plaintext"],
            payload["status_successfully_obtained"],
        )
