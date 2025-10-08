from dataclasses import dataclass

from pcs.common.host import Destination, PcsKnownHost


@dataclass(frozen=True)
class HostAuthData:
    username: str
    password: str
    dest_list: list[Destination]


@dataclass(frozen=True)
class HostWithTokenAuthData:
    token: str
    dest_list: list[Destination]

    def to_known_host(self, node_name: str) -> PcsKnownHost:
        return PcsKnownHost(node_name, self.token, self.dest_list)
