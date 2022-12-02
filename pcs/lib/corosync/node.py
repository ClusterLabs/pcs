import socket
from dataclasses import dataclass
from typing import (
    Optional,
    Sequence,
)

from pcs.common import reports
from pcs.common.corosync_conf import (
    CorosyncNodeAddressDto,
    CorosyncNodeAddressType,
    CorosyncNodeDto,
)
from pcs.common.interface.dto import ImplementsToDto
from pcs.lib.errors import LibraryError
from pcs.lib.validate import (
    is_ipv4_address,
    is_ipv6_address,
)


@dataclass(frozen=True)
class CorosyncNodeAddress(ImplementsToDto):
    """An address of a node loaded from corosync.conf"""

    addr: str
    link: str

    @property
    def type(self) -> CorosyncNodeAddressType:
        return get_address_type(self.addr, resolve=False)

    def to_dto(self) -> CorosyncNodeAddressDto:
        return CorosyncNodeAddressDto(
            addr=self.addr,
            link=self.link,
            type=self.type,
        )


@dataclass(frozen=True)
class CorosyncNode(ImplementsToDto):
    """A node loaded from corosync.conf"""

    name: Optional[str]
    addrs: Sequence[CorosyncNodeAddress]
    nodeid: Optional[str]

    def __post_init__(self) -> None:
        # Make sure addrs is a tuple so it is not possible to change its items.
        # Since the dataclass is frozen, object__setattr__ must be used.
        object.__setattr__(self, "addrs", tuple(self.addrs))

    def addr_plain_for_link(self, link: str) -> Optional[str]:
        for addr in self.addrs:
            if addr.link == link:
                return addr.addr
        return None

    def addrs_plain(self, except_link: Optional[str] = None) -> list[str]:
        return [
            addr.addr
            for addr in self.addrs
            if except_link is None or addr.link != except_link
        ]

    def to_dto(self) -> CorosyncNodeDto:
        if not self.name:
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.CorosyncConfigMissingNamesOfNodes(
                        fatal=True
                    )
                )
            )
        if not self.nodeid:
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.CorosyncConfigMissingIdsOfNodes()
                )
            )
        return CorosyncNodeDto(
            name=self.name,
            nodeid=self.nodeid,
            addrs=[addr.to_dto() for addr in self.addrs],
        )


def get_address_type(
    address: str, resolve: bool = False
) -> CorosyncNodeAddressType:
    if is_ipv4_address(address):
        return CorosyncNodeAddressType.IPV4
    if is_ipv6_address(address):
        return CorosyncNodeAddressType.IPV6
    if resolve:
        try:
            socket.getaddrinfo(address, None)
        except socket.gaierror:
            return CorosyncNodeAddressType.UNRESOLVABLE
    return CorosyncNodeAddressType.FQDN
