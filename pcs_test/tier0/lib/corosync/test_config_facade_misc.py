from unittest import TestCase

from pcs_test.tools.assertions import (
    assert_raise_library_error,
)
from pcs_test.tools.misc import get_test_resource as rc

from pcs.common import report_codes
from pcs.lib.errors import ReportItemSeverity as severity

import pcs.lib.corosync.config_facade as lib
from pcs.lib.corosync import constants

class FromStringTest(TestCase):
    def test_success(self):
        config = open(rc("corosync.conf")).read()
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(facade.__class__, lib.ConfigFacade)
        self.assertEqual(facade.config.export(), config)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)

    def test_parse_error_missing_brace(self):
        # pylint: disable=no-self-use
        config = "section {"
        assert_raise_library_error(
            lambda: lib.ConfigFacade.from_string(config),
            (
                severity.ERROR,
                report_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
                {}
            )
        )

    def test_parse_error_unexpected_brace(self):
        # pylint: disable=no-self-use
        config = "}"
        assert_raise_library_error(
            lambda: lib.ConfigFacade.from_string(config),
            (
                severity.ERROR,
                report_codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE,
                {}
            )
        )


class GetSimpleValueMixin():
    def assert_value(self, value, config):
        facade = lib.ConfigFacade.from_string(config)
        self.assertEqual(value, self.getter(facade))
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)


class GetClusterNameTest(GetSimpleValueMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_cluster_name()

    def test_no_name(self):
        self.assert_value(
            "",
            ""
        )

    def test_empty_name(self):
        self.assert_value(
            "",
            "totem {\n cluster_name:\n}\n"
        )

    def test_one_name(self):
        self.assert_value(
            "test",
            "totem {\n cluster_name: test\n}\n"
        )

    def test_more_names(self):
        self.assert_value(
            "TEST",
            "totem {\n cluster_name: test\n cluster_name: TEST\n}\n"
        )

    def test_more_sections(self):
        self.assert_value(
            "TEST",
            "totem{\n cluster_name: test\n}\ntotem{\n cluster_name: TEST\n}\n"
        )


class GetTransport(GetSimpleValueMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_transport()

    def test_no_name(self):
        self.assert_value(
            constants.TRANSPORT_DEFAULT,
            ""
        )

    def test_empty_name(self):
        self.assert_value(
            constants.TRANSPORT_DEFAULT,
            "totem {\n transport:\n}\n"
        )

    def test_one_name(self):
        self.assert_value(
            "udp",
            "totem {\n transport: udp\n}\n"
        )

    def test_more_names(self):
        self.assert_value(
            "udpu",
            "totem {\n transport: udp\n transport: udpu\n}\n"
        )

    def test_more_sections(self):
        self.assert_value(
            "udpu",
            "totem{\n transport: udp\n}\ntotem{\n transport: udpu\n}\n"
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
        self.assert_value(
            constants.IP_VERSION_64,
            ""
        )

    def test_no_name(self):
        for transport, ip in self.transport_ip_list:
            with self.subTest(transport=transport, ip=ip):
                self.assert_value(
                    ip,
                    f"totem {{\n transport: {transport}\n}}\n"
                )

    def test_no_value(self):
        for transport, ip in self.transport_ip_list:
            with self.subTest(transport=transport, ip=ip):
                self.assert_value(
                    ip,
                    f"totem {{\n transport: {transport}\n ip_version:\n}}\n"
                )

    def test_one_name(self):
        self.assert_value(
            "ipv4-6",
            "totem {\n transport: udp\n ip_version: ipv4-6\n}\n"
        )

    def test_more_names(self):
        self.assert_value(
            "ipv6",
            "totem {\ntransport: udp\nip_version: ipv4-6\nip_version: ipv6\n}\n"
        )

    def test_more_sections(self):
        self.assert_value(
            "ipv6",
            "totem {\n transport: knet\n ip_version: ipv4-6\n}\n"
                "totem {\n ip_version: ipv6\n}\n"
        )
