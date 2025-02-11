from unittest import TestCase

import pcs.lib.corosync.config_facade as lib
from pcs.lib.corosync import constants
from pcs.lib.corosync.config_parser import Parser


class GetSimpleValueMixin:
    def assert_value(self, value, config):
        facade = lib.ConfigFacade(Parser.parse(config.encode("utf-8")))
        self.assertEqual(value, self.getter(facade))
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class GetClusterNameTest(GetSimpleValueMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_cluster_name()

    def test_no_name(self):
        self.assert_value("", "")

    def test_empty_name(self):
        self.assert_value("", "totem {\n cluster_name:\n}\n")

    def test_one_name(self):
        self.assert_value("test", "totem {\n cluster_name: test\n}\n")

    def test_more_names(self):
        self.assert_value(
            "TEST", "totem {\n cluster_name: test\n cluster_name: TEST\n}\n"
        )

    def test_more_sections(self):
        self.assert_value(
            "TEST",
            "totem{\n cluster_name: test\n}\ntotem{\n cluster_name: TEST\n}\n",
        )


class SetClusterName(TestCase):
    @staticmethod
    def _fixture_facade(config: str) -> lib.ConfigFacade:
        return lib.ConfigFacade(Parser.parse(config.encode("utf-8")))

    def test_replace_old_name(self):
        facade = self._fixture_facade("totem {\n cluster_name: NAME\n}\n")
        facade.set_cluster_name("a")
        self.assertTrue(facade.need_stopped_cluster)
        self.assertEqual(facade.get_cluster_name(), "a")

    def test_missing_totem_section(self):
        facade = self._fixture_facade("")
        facade.set_cluster_name("a")
        self.assertTrue(facade.need_stopped_cluster)
        self.assertEqual(facade.get_cluster_name(), "a")

    def test_missing_cluster_name_option(self):
        facade = self._fixture_facade("totem {\n}\n")
        facade.set_cluster_name("a")
        self.assertTrue(facade.need_stopped_cluster)
        self.assertEqual(facade.get_cluster_name(), "a")


class GetTransport(GetSimpleValueMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_transport()

    def test_no_name(self):
        self.assert_value(constants.TRANSPORT_DEFAULT, "")

    def test_empty_name(self):
        self.assert_value(
            constants.TRANSPORT_DEFAULT, "totem {\n transport:\n}\n"
        )

    def test_one_name(self):
        self.assert_value("udp", "totem {\n transport: udp\n}\n")

    def test_more_names(self):
        self.assert_value(
            "udpu", "totem {\n transport: udp\n transport: udpu\n}\n"
        )

    def test_more_sections(self):
        self.assert_value(
            "udpu", "totem{\n transport: udp\n}\ntotem{\n transport: udpu\n}\n"
        )


class GetIpVersion(GetSimpleValueMixin, TestCase):
    transport_ip_list = [
        ("udp", constants.IP_VERSION_4),
        ("udpu", constants.IP_VERSION_64),
        ("knet", constants.IP_VERSION_64),
    ]

    @staticmethod
    def getter(facade):
        return facade.get_ip_version()

    def test_empty_config(self):
        self.assert_value(constants.IP_VERSION_64, "")

    def test_no_name(self):
        for transport, ip in self.transport_ip_list:
            with self.subTest(transport=transport, ip=ip):
                self.assert_value(
                    ip, f"totem {{\n transport: {transport}\n}}\n"
                )

    def test_no_value(self):
        for transport, ip in self.transport_ip_list:
            with self.subTest(transport=transport, ip=ip):
                self.assert_value(
                    ip, f"totem {{\n transport: {transport}\n ip_version:\n}}\n"
                )

    def test_one_name(self):
        self.assert_value(
            "ipv4-6", "totem {\n transport: udp\n ip_version: ipv4-6\n}\n"
        )

    def test_more_names(self):
        self.assert_value(
            "ipv6",
            (
                "totem {\ntransport: udp\nip_version: ipv4-6\nip_version: "
                "ipv6\n}\n"
            ),
        )

    def test_more_sections(self):
        self.assert_value(
            "ipv6",
            "totem {\n transport: knet\n ip_version: ipv4-6\n}\n"
            "totem {\n ip_version: ipv6\n}\n",
        )
