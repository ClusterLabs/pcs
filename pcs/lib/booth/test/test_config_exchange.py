from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.test.tools.pcs_unittest import TestCase
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
                config_structure.ConfigItem("ticket", "TB", [
                    config_structure.ConfigItem("expire", "10")
                ]),
            ],
            config_exchange.from_exchange_format([
                {"key": "authfile","value": "/path/to/auth.file","details": []},
                {"key": "site", "value": "1.1.1.1", "details": []},
                {"key": "site", "value": "2.2.2.2", "details": []},
                {"key": "arbitrator", "value": "3.3.3.3", "details": []},
                {"key": "ticket", "value": "TA", "details": []},
                {"key": "ticket", "value": "TB", "details": [
                    {"key": "expire", "value": "10", "details": []}
                ]},
            ])
        )


class GetExchenageFormatTest(TestCase):
    def test_convert_parsed_config_to_exchange_format(self):
        self.assertEqual(
            [
                {"key": "site", "value": "1.1.1.1", "details": []},
                {"key": "site", "value": "2.2.2.2", "details": []},
                {"key": "arbitrator", "value": "3.3.3.3", "details": []},
                {"key": "ticket", "value": "TA", "details": []},
                {"key": "ticket", "value": "TB", "details": [
                    {"key": "timeout", "value": "10", "details": []}
                ]},
            ],
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
