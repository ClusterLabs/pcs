from enum import auto
from typing import Iterable

from pcs.common.tools import AutoNameEnum
from pcs.lib.interface.config import FacadeInterface


class DrRole(AutoNameEnum):
    PRIMARY = auto()
    RECOVERY = auto()


class Facade(FacadeInterface):
    @classmethod
    def create(cls, local_role: DrRole) -> "Facade":
        return cls(dict(
            local=dict(
                role=local_role.value,
            ),
            remote_sites=[],
        ))

    @property
    def local_role(self) -> DrRole:
        return DrRole(self._config["local_role"])

    def add_site(self, role: DrRole, node_list: Iterable[str]) -> None:
        self._config["remote_sites"].append(
            dict(
                role=role.value,
                nodes=[dict(name=node) for node in node_list],
            )
        )
