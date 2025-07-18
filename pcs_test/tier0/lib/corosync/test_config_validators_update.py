from unittest import TestCase

from pcs.lib.corosync import config_validators

from pcs_test.tier0.lib.corosync.test_config_validators_common import (
    TotemBase,
    TransportKnetBase,
    TransportUdpBase,
)
from pcs_test.tools.assertions import assert_report_item_list_equal


class UpdateTotem(TotemBase, TestCase):
    def call_function(self, options):
        return config_validators.update_totem(options)

    def test_empty_values_allowed(self):
        assert_report_item_list_equal(
            self.call_function(dict.fromkeys(self.allowed_options, "")),
            [],
        )


class UpdateTransportKnet(TransportKnetBase, TestCase):
    def call_function(
        self,
        generic_options,
        compression_options,
        crypto_options,
        current_crypto_options=None,
    ):
        return config_validators.update_transport_knet(
            generic_options,
            compression_options,
            crypto_options,
            current_crypto_options=(
                {} if current_crypto_options is None else current_crypto_options
            ),
        )

    def test_empty_values_allowed(self):
        assert_report_item_list_equal(
            self.call_function(
                {
                    "ip_version": "",
                    "knet_pmtud_interval": "",
                    "link_mode": "",
                },
                {
                    "level": "",
                    "model": "",
                    "threshold": "",
                },
                {
                    "cipher": "",
                    "hash": "",
                    "model": "",
                },
            ),
            [],
        )

    def test_crypto_config_enabled_set_to_disabled(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {"cipher": "none", "hash": "none"},
                {"cipher": "aes256", "hash": "sha256"},
            ),
            [],
        )

    def test_crypto_config_enabled_set_to_default(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {"cipher": "", "hash": ""},
                {"cipher": "aes256", "hash": "sha256"},
            ),
            [],
        )

    def test_crypto_config_enabled_default_hash(self):
        assert_report_item_list_equal(
            self.call_function(
                {}, {}, {"hash": ""}, {"cipher": "aes256", "hash": "sha256"}
            ),
            [self.fixture_error_prerequisite],
        )

    def test_crypto_config_enabled_disabled_hash(self):
        assert_report_item_list_equal(
            self.call_function(
                {}, {}, {"hash": "none"}, {"cipher": "aes256", "hash": "sha256"}
            ),
            [self.fixture_error_prerequisite],
        )

    def test_crypto_config_enabled_changed_hash(self):
        assert_report_item_list_equal(
            self.call_function(
                {}, {}, {"hash": "md5"}, {"cipher": "aes256", "hash": "sha256"}
            ),
            [],
        )

    def test_crypto_config_enabled_changed_cipher(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {"cipher": "aes128"},
                {"cipher": "aes256", "hash": "sha256"},
            ),
            [],
        )

    def test_crypto_config_hash_enabled_enable_cipher(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {"cipher": "aes128"},
                {"hash": "sha256"},
            ),
            [],
        )

    def test_crypto_config_hash_enabled_enable_cipher_disable_hash(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {"cipher": "aes128", "hash": "none"},
                {"hash": "sha256"},
            ),
            [self.fixture_error_prerequisite],
        )

    def test_crypto_config_hash_enabled_enable_cipher_default_hash(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {"cipher": "aes128", "hash": ""},
                {"hash": "sha256"},
            ),
            [self.fixture_error_prerequisite],
        )


class UpdateTransportUdp(TransportUdpBase, TestCase):
    def call_function(
        self, generic_options, compression_options, crypto_options
    ):
        return config_validators.update_transport_udp(
            generic_options, compression_options, crypto_options
        )

    def test_empty_values_allowed(self):
        assert_report_item_list_equal(
            self.call_function({"ip_version": "", "netmtu": ""}, {}, {}),
            [],
        )
