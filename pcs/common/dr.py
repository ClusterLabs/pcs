from enum import auto
from typing import (
    Any,
    Iterable,
    Mapping,
)

from pcs.common.interface.dto import DataTransferObject
from pcs.common.tools import AutoNameEnum


class DrRole(AutoNameEnum):
    PRIMARY = auto()
    RECOVERY = auto()


class DrConfigNodeDto(DataTransferObject):
    def __init__(self, name: str):
        self.name = name

    def to_dict(self) -> Mapping[str, Any]:
        return dict(name=self.name)

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DrConfigNodeDto":
        return cls(payload["name"])


class DrConfigSiteDto(DataTransferObject):
    def __init__(
        self,
        site_role: DrRole,
        node_list: Iterable[DrConfigNodeDto]
    ):
        self.site_role = site_role
        self.node_list = node_list

    def to_dict(self) -> Mapping[str, Any]:
        return dict(
            site_role=self.site_role.value,
            node_list=[node.to_dict() for node in self.node_list]
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DrConfigSiteDto":
        return cls(
            DrRole(payload["site_role"]),
            [
                DrConfigNodeDto.from_dict(payload_node)
                for payload_node in payload["node_list"]
            ],
        )


class DrConfigDto(DataTransferObject):
    def __init__(
        self,
        local_site: DrConfigSiteDto,
        remote_site_list: Iterable[DrConfigSiteDto]
    ):
        self.local_site = local_site
        self.remote_site_list = remote_site_list

    def to_dict(self) -> Mapping[str, Any]:
        return dict(
            local_site=self.local_site.to_dict(),
            remote_site_list=[site.to_dict() for site in self.remote_site_list],
        )

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "DrConfigDto":
        return cls(
            DrConfigSiteDto.from_dict(payload["local_site"]),
            [
                DrConfigSiteDto.from_dict(payload_site)
                for payload_site in payload["remote_site_list"]
            ],
        )


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
