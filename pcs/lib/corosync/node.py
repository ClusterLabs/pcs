from collections import namedtuple

from pcs.lib.validate import (
    is_ipv4_address,
    is_ipv6_address,
)

class CorosyncNodeAddress(
    namedtuple("CorosyncNodeAddress", "addr link")
):
    """An address of a node loaded from corosync.conf"""
    _type = None

    @property
    def type(self):
        if self._type is None:
            self._type = self._get_type()
        return self._type

    def _get_type(self):
        if is_ipv4_address(self.addr):
            return "IPv4"
        if is_ipv6_address(self.addr):
            return "IPv6"
        return "FQDN"


class CorosyncNode(
    namedtuple("CorosyncNode", "name addrs nodeid")
):
    """A node loaded from corosync.conf"""
    _addrs_plain = None

    def __new__(cls, name, addrs, nodeid):
        return super().__new__(cls, name, tuple(addrs), nodeid)

    @property
    def addrs_plain(self):
        if self._addrs_plain is None:
            self._addrs_plain = [addr.addr for addr in self.addrs]
        return self._addrs_plain
