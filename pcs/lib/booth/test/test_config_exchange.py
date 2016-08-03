from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from unittest import TestCase
from pcs.lib.booth import config_structure, config_exchange


class FromExchangeFormatTest(TestCase):
    def test_convert_all_supported_items(self):
        self.assertEqual(
            [
                config_structure.ConfigItem("authfile", "/path/to/auth.file"),
                config_structure.ConfigItem("site", "1.1.1.1"),
                config_structure.ConfigItem("site", "2.2.2.2"),
                config_structure.ConfigItem("arbitrator", "3.3.3.3"),
                config_structure.ConfigItem("ticket", "TA"),
                config_structure.ConfigItem("ticket", "TB"),
            ],
            config_exchange.from_exchange_format(
                {
                    "sites": ["1.1.1.1", "2.2.2.2"],
                    "arbitrators": ["3.3.3.3"],
                    "tickets": ["TA", "TB"],
                    "authfile": "/path/to/auth.file",
                },
            )
        )


class GetExchenageFormatTest(TestCase):
    def test_convert_parsed_config_to_exchange_format(self):
        self.assertEqual(
            {
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"],
                "tickets": ["TA", "TB"],
                "authfile": "/path/to/auth.file",
            },
            config_exchange.to_exchange_format([
                config_structure.ConfigItem("site", "1.1.1.1"),
                config_structure.ConfigItem("site", "2.2.2.2"),
                config_structure.ConfigItem("arbitrator", "3.3.3.3"),
                config_structure.ConfigItem("authfile", "/path/to/auth.file"),
                config_structure.ConfigItem("ticket", "TA"),
                config_structure.ConfigItem("ticket", "TB", [
                    config_structure.ConfigItem("timeout", "10")
                ]),
            ])
        )

    def test_convert_parsed_config_to_exchange_format_without_authfile(self):
        self.assertEqual(
            {
                "sites": ["1.1.1.1", "2.2.2.2"],
                "arbitrators": ["3.3.3.3"],
                "tickets": ["TA", "TB"],
            },
            config_exchange.to_exchange_format([
                config_structure.ConfigItem("site", "1.1.1.1"),
                config_structure.ConfigItem("site", "2.2.2.2"),
                config_structure.ConfigItem("arbitrator", "3.3.3.3"),
                config_structure.ConfigItem("ticket", "TA"),
                config_structure.ConfigItem("ticket", "TB", [
                    config_structure.ConfigItem("timeout", "10")
                ]),
            ])
        )
