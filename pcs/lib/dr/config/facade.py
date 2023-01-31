from typing import (
    List,
    NamedTuple,
)

from pcs.common.dr import DrRole
from pcs.common.types import StringIterable
from pcs.lib.interface.config import FacadeInterface


class DrSite(NamedTuple):
    role: DrRole
    node_name_list: List[str]


class Facade(FacadeInterface):
    @classmethod
    def create(cls, local_role: DrRole) -> "Facade":
        return cls(
            dict(
                local=dict(
                    role=local_role.value,
                ),
                remote_sites=[],
            )
        )

    @classmethod
    def empty(cls) -> "Facade":
        return cls({})

    @property
    def local_role(self) -> DrRole:
        return DrRole(self._config["local"]["role"])

    def add_site(self, role: DrRole, node_list: StringIterable) -> None:
        self._config["remote_sites"].append(
            dict(
                role=role.value,
                nodes=[dict(name=node) for node in node_list],
            )
        )

    def get_remote_site_list(self) -> List[DrSite]:
        return [
            DrSite(
                DrRole(conf_site["role"]),
                [node["name"] for node in conf_site["nodes"]],
            )
            for conf_site in self._config.get("remote_sites", [])
        ]
