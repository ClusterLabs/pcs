from unittest import TestCase

from pcs.lib.corosync.node import (
    CorosyncNode,
    CorosyncNodeAddress,
)


class AddrsPlain(TestCase):
    @staticmethod
    def _fixture_no_addrs():
        return CorosyncNode("node1", [], "1")

    @staticmethod
    def _fixture_one_addr():
        return CorosyncNode(
            "node1",
            [CorosyncNodeAddress("10.0.0.1", "1")],
            "1"
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
            "1"
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
            ["10.0.0.0", "10.0.0.1", "10.0.0.4", "10.0.0.3"],
            node.addrs_plain()
        )

    def test_several_addrs_set_get_all_except_one(self):
        node = self._fixture_several_addrs()
        self.assertEqual(
            ["10.0.0.0", "10.0.0.4", "10.0.0.3"],
            node.addrs_plain(except_link="1")
        )

    def test_several_addrs_set_get_all_except_another(self):
        node = self._fixture_several_addrs()
        self.assertEqual(
            ["10.0.0.0", "10.0.0.1", "10.0.0.4", "10.0.0.3"],
            node.addrs_plain(except_link=1)
        )
        self.assertEqual(
            ["10.0.0.0", "10.0.0.1", "10.0.0.4", "10.0.0.3"],
            node.addrs_plain(except_link="2")
        )
