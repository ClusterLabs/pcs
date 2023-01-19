from socket import gaierror
from unittest import TestCase
from unittest.mock import patch

from pcs.common.corosync_conf import (
    CorosyncNodeAddressDto,
    CorosyncNodeDto,
)
from pcs.common.types import CorosyncNodeAddressType
from pcs.lib.corosync.node import (
    CorosyncNode,
    CorosyncNodeAddress,
    get_address_type,
)


class AddrsPlain(TestCase):
    @staticmethod
    def _fixture_no_addrs():
        return CorosyncNode("node1", [], "1")

    @staticmethod
    def _fixture_one_addr():
        return CorosyncNode(
            "node1", [CorosyncNodeAddress("10.0.0.1", "1")], "1"
        )

    @staticmethod
    def _fixture_several_addrs():
        return CorosyncNode(
            "node1",
            [
                CorosyncNodeAddress("10.0.0.0", "0"),
                CorosyncNodeAddress("10.0.0.1", "1"),
                CorosyncNodeAddress("10.0.0.4", "4"),
                CorosyncNodeAddress("10.0.0.3", "3"),
            ],
            "1",
        )

    def test_no_addrs_set_get_one(self):
        node = self._fixture_no_addrs()
        self.assertEqual(None, node.addr_plain_for_link("0"))

    def test_no_addrs_set_get_all(self):
        node = self._fixture_no_addrs()
        self.assertEqual([], node.addrs_plain())

    def test_no_addrs_set_get_all_except(self):
        node = self._fixture_no_addrs()
        self.assertEqual([], node.addrs_plain(except_link="0"))

    def test_one_addr_set_get_it(self):
        node = self._fixture_one_addr()
        self.assertEqual("10.0.0.1", node.addr_plain_for_link("1"))

    def test_one_addr_set_get_another(self):
        node = self._fixture_one_addr()
        self.assertEqual(None, node.addr_plain_for_link(1))
        self.assertEqual(None, node.addr_plain_for_link("2"))

    def test_one_addr_set_get_all(self):
        node = self._fixture_one_addr()
        self.assertEqual(["10.0.0.1"], node.addrs_plain())

    def test_one_addr_set_get_all_except_it(self):
        node = self._fixture_one_addr()
        self.assertEqual([], node.addrs_plain(except_link="1"))

    def test_one_addr_set_get_all_except_another(self):
        node = self._fixture_one_addr()
        self.assertEqual(["10.0.0.1"], node.addrs_plain(except_link=1))
        self.assertEqual(["10.0.0.1"], node.addrs_plain(except_link="2"))

    def test_several_addrs_set_get_one_of_them(self):
        node = self._fixture_several_addrs()
        self.assertEqual("10.0.0.1", node.addr_plain_for_link("1"))

    def test_several_addrs_set_get_another(self):
        node = self._fixture_several_addrs()
        self.assertEqual(None, node.addr_plain_for_link(1))
        self.assertEqual(None, node.addr_plain_for_link("2"))

    def test_several_addrs_set_get_all(self):
        node = self._fixture_several_addrs()
        self.assertEqual(
            ["10.0.0.0", "10.0.0.1", "10.0.0.4", "10.0.0.3"], node.addrs_plain()
        )

    def test_several_addrs_set_get_all_except_one(self):
        node = self._fixture_several_addrs()
        self.assertEqual(
            ["10.0.0.0", "10.0.0.4", "10.0.0.3"],
            node.addrs_plain(except_link="1"),
        )

    def test_several_addrs_set_get_all_except_another(self):
        node = self._fixture_several_addrs()
        self.assertEqual(
            ["10.0.0.0", "10.0.0.1", "10.0.0.4", "10.0.0.3"],
            node.addrs_plain(except_link=1),
        )
        self.assertEqual(
            ["10.0.0.0", "10.0.0.1", "10.0.0.4", "10.0.0.3"],
            node.addrs_plain(except_link="2"),
        )


class CorosyncNodeToDto(TestCase):
    def test_no_addrs(self):
        self.assertEqual(
            CorosyncNode("node1", [], "1").to_dto(),
            CorosyncNodeDto("node1", "1", []),
        )

    def test_all_addr_types(self):
        self.assertEqual(
            CorosyncNode(
                "node1",
                [
                    CorosyncNodeAddress("10.0.0.1", "0"),
                    CorosyncNodeAddress("node1.domain", "1"),
                    CorosyncNodeAddress("fe80::5054:ff:fe81:1", "2"),
                ],
                "1",
            ).to_dto(),
            CorosyncNodeDto(
                "node1",
                "1",
                [
                    CorosyncNodeAddressDto(
                        "10.0.0.1", "0", CorosyncNodeAddressType.IPV4
                    ),
                    CorosyncNodeAddressDto(
                        "node1.domain", "1", CorosyncNodeAddressType.FQDN
                    ),
                    CorosyncNodeAddressDto(
                        "fe80::5054:ff:fe81:1",
                        "2",
                        CorosyncNodeAddressType.IPV6,
                    ),
                ],
            ),
        )


class GetAddrType(TestCase):
    def assert_call(self, expected_type, addr, resolve):
        self.assertEqual(expected_type, get_address_type(addr, resolve=resolve))

    def test_ipv4_resolve_false(self):
        self.assert_call(CorosyncNodeAddressType.IPV4, "10.0.0.1", False)

    def test_ipv6_resolve_false(self):
        self.assert_call(
            CorosyncNodeAddressType.IPV6, "fe80::5054:ff:fe81:1", False
        )

    def test_fqdn_resolve_false(self):
        self.assert_call(CorosyncNodeAddressType.FQDN, "node1.domain", False)

    def test_ipv4_resolve_true(self):
        self.assert_call(CorosyncNodeAddressType.IPV4, "10.0.0.1", True)

    def test_ipv6_resolve_true(self):
        self.assert_call(
            CorosyncNodeAddressType.IPV6, "fe80::5054:ff:fe81:1", True
        )

    @patch("pcs.lib.corosync.node.socket.getaddrinfo")
    def test_fqdn_resolvable(self, mock_getaddrinfo):
        mock_getaddrinfo.return_value = None
        self.assertEqual(
            CorosyncNodeAddressType.FQDN,
            get_address_type("node1.domain", resolve=True),
        )

    @patch("pcs.lib.corosync.node.socket.getaddrinfo")
    def test_fqdn_unresolvable(self, mock_getaddrinfo):
        mock_getaddrinfo.side_effect = gaierror()
        self.assertEqual(
            CorosyncNodeAddressType.UNRESOLVABLE,
            get_address_type("node1.domain", resolve=True),
        )
