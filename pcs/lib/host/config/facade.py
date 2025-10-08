from dataclasses import replace
from typing import Sequence

from pcs.common.host import PcsKnownHost
from pcs.common.types import StringSequence
from pcs.lib.interface.config import SyncVersionFacadeInterface

from .types import KnownHosts


class Facade(SyncVersionFacadeInterface):
    def __init__(self, parsed_config: KnownHosts):
        super().__init__(parsed_config)

    @classmethod
    def create(cls, data_version: int = 1) -> "Facade":
        return cls(
            KnownHosts(
                format_version=1, data_version=data_version, known_hosts={}
            )
        )

    @property
    def config(self) -> KnownHosts:
        return self._config

    @property
    def data_version(self) -> int:
        return self.config.data_version

    def set_data_version(self, new_version: int) -> None:
        self._set_config(replace(self.config, data_version=new_version))

    @property
    def known_hosts(self) -> dict[str, PcsKnownHost]:
        return dict(self.config.known_hosts)

    def update_known_hosts(self, hosts: Sequence[PcsKnownHost]) -> None:
        updated_hosts = self.known_hosts
        for new_host in hosts:
            updated_hosts[new_host.name] = new_host

        self._set_config(replace(self.config, known_hosts=updated_hosts))

    def remove_known_hosts(self, hosts: StringSequence) -> None:
        updated_hosts = self.known_hosts
        for host_name in hosts:
            if host_name in updated_hosts:
                del updated_hosts[host_name]

        self._set_config(replace(self.config, known_hosts=updated_hosts))
