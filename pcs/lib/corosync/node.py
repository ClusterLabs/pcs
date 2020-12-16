from collections import namedtuple
import socket

from pcs.lib.validate import (
    is_ipv4_address,
    is_ipv6_address,
)
from pcs.common.corosync_conf import (
    CorosyncNodeAddressDto,
    CorosyncNodeDto,
)

ADDR_IPV4 = "IPv4"
ADDR_IPV6 = "IPv6"
ADDR_FQDN = "FQDN"
ADDR_UNRESOLVABLE = "unresolvable"


# TODO: add pcs.common.interface.dto.ImplementsToDto inheritance
class CorosyncNodeAddress(namedtuple("CorosyncNodeAddress", "addr link")):
    """An address of a node loaded from corosync.conf"""

    _type = None

    @property
    def type(self):
        if self._type is None:
            self._type = self._get_type()
        return self._type

    def _get_type(self):
        return get_address_type(self.addr, resolve=False)

    def to_dto(self) -> CorosyncNodeAddressDto:
        return CorosyncNodeAddressDto(
            addr=self.addr, link=self.link, type=self.type,
        )


# TODO: add pcs.common.interface.dto.ImplementsToDto inheritance
class CorosyncNode(namedtuple("CorosyncNode", "name addrs nodeid")):
    """A node loaded from corosync.conf"""

    _addrs_plain = None

    def __new__(cls, name, addrs, nodeid):
        return super().__new__(cls, name, tuple(addrs), nodeid)

    def addr_plain_for_link(self, link):
        for addr in self.addrs:
            if addr.link == link:
                return addr.addr
        return None

    def addrs_plain(self, except_link=None):
        if except_link:
            return [
                addr.addr for addr in self.addrs if addr.link != except_link
            ]
        if self._addrs_plain is None:
            self._addrs_plain = [addr.addr for addr in self.addrs]
        return self._addrs_plain

    def to_dto(self) -> CorosyncNodeDto:
        return CorosyncNodeDto(
            name=self.name,
            nodeid=self.nodeid,
            addrs=[addr.to_dto() for addr in self.addrs],
        )


def get_address_type(address, resolve=False):
    if is_ipv4_address(address):
        return ADDR_IPV4
    if is_ipv6_address(address):
        return ADDR_IPV6
    if resolve:
        try:
            socket.getaddrinfo(address, None)
        except socket.gaierror:
            return ADDR_UNRESOLVABLE
    return ADDR_FQDN
