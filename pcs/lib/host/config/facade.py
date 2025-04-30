from pcs.common.host import PcsKnownHost
from pcs.lib.interface.config import SyncVersionFacadeInterface

from .types import KnownHosts


class Facade(SyncVersionFacadeInterface):
    def __init__(self, parsed_config: KnownHosts):
        super().__init__(parsed_config)

    @classmethod
    def create(cls) -> "Facade":
        return cls(
            KnownHosts(format_version=1, data_version=1, known_hosts=dict())
        )

    @property
    def config(self) -> KnownHosts:
        return self._config

    @property
    def data_version(self) -> int:
        return self.config.data_version

    @property
    def known_hosts(self) -> dict[str, PcsKnownHost]:
        return dict(self.config.known_hosts)
