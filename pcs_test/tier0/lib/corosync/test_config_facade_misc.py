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
        self.assert_value("knet", "totem {\n transport: knet\n}\n")

    def test_more_names(self):
        self.assert_value(
            "other", "totem {\n transport: knet\n transport: other\n}\n"
        )

    def test_more_sections(self):
        self.assert_value(
            "other",
            "totem{\n transport: knet\n}\ntotem{\n transport: other\n}\n",
        )


class GetIpVersion(GetSimpleValueMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_ip_version()

    def test_empty_config(self):
        self.assert_value(constants.IP_VERSION_64, "")

    def test_no_name(self):
        self.assert_value(
            constants.IP_VERSION_64, "totem {\n transport: knet\n}\n"
        )

    def test_no_value(self):
        self.assert_value(
            constants.IP_VERSION_64,
            "totem {\n transport: knet\n ip_version:\n}\n",
        )

    def test_one_name(self):
        self.assert_value(
            constants.IP_VERSION_46,
            "totem {\n transport: knet\n ip_version: ipv4-6\n}\n",
        )

    def test_more_names(self):
        self.assert_value(
            constants.IP_VERSION_6,
            "totem {\ntransport: knet\nip_version: ipv4\nip_version: ipv6\n}\n",
        )

    def test_more_sections(self):
        self.assert_value(
            constants.IP_VERSION_6,
            (
                "totem {\n transport: knet\n ip_version: ipv4\n}\n"
                "totem {\n ip_version: ipv6\n}\n"
            ),
        )
