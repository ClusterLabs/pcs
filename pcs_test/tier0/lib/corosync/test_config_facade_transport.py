from textwrap import dedent
from unittest import TestCase

import pcs.lib.corosync.config_facade as lib
from pcs.lib.corosync.config_parser import Parser


def _get_facade(config_text):
    return lib.ConfigFacade(Parser.parse(config_text.encode("utf-8")))


class NeedsStoppedClusterTest(TestCase):
    # pcs.lib.corosync.constants.TRANSPORT_RUNTIME_CHANGE_BANNED_OPTIONS
    # ip_version, netmtu
    _option_list_empty = [
        {"ip_version": ""},
        {"netmtu": ""},
        {"ip_version": "", "netmtu": ""},
    ]
    _option_list_modify = [
        {"ip_version": "ipv6"},
        {"netmtu": "1000"},
        {"ip_version": "ipv4-6", "netmtu": "2000"},
    ]

    def _assert_needs_stopped_cluster(self, config, need_stopped, option_list):
        for options in option_list:
            with self.subTest(options):
                facade = _get_facade(config)
                facade.set_transport_options(options, {}, {})
                self.assertEqual(facade.need_stopped_cluster, need_stopped)

    def test_remove_not_present_options(self):
        self._assert_needs_stopped_cluster("", False, self._option_list_empty)

    def test_remove_present_empty_options(self):
        config = dedent(
            """\
            totem {
                ip_version:
                netmtu:
            }
        """
        )
        self._assert_needs_stopped_cluster(
            config, False, self._option_list_empty
        )

    def test_remove_present_options(self):
        config = dedent(
            """\
            totem {
                ip_version: ipv4
                netmtu: 1500
            }
        """
        )
        self._assert_needs_stopped_cluster(
            config, True, self._option_list_empty
        )

    def test_modify_present_options(self):
        config = dedent(
            """\
            totem {
                ip_version: ipv4-6
                netmtu: 1500
            }
        """
        )
        self._assert_needs_stopped_cluster(
            config, True, self._option_list_modify
        )

    def test_not_banned_options(self):
        config = dedent(
            """\
            totem {
                opt1:
                opt2: val2
            }
        """
        )
        not_banned_options = [
            {"opt0": "", "opt1": "", "opt2": ""},
            {"opt0": "val0", "opt1": "val1", "opt2": "val22"},
        ]
        self._assert_needs_stopped_cluster(config, False, not_banned_options)


class SetTransportOptionsKnetMixin:
    knet_transport = None

    def test_add_knet_transport_options(self):
        config = dedent(
            """\
            totem {{{0}
            }}
        """
        ).format(self.knet_transport)
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "link_mode": "active",
                "knet_pmtud_interval": "1234",
                "ip_version": "ipv4",
            },
            {
                "threshold": "1234",
                "model": "zlib",
                "level": "5",
            },
            {
                "model": "nss",
                "hash": "sha256",
                "cipher": "aes256",
            },
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                """\
                totem {{{0}
                    ip_version: ipv4
                    knet_pmtud_interval: 1234
                    link_mode: active
                    knet_compression_level: 5
                    knet_compression_model: zlib
                    knet_compression_threshold: 1234
                    crypto_cipher: aes256
                    crypto_hash: sha256
                    crypto_model: nss
                }}
            """
            ).format(self.knet_transport),
            facade.config.export(),
        )

    def test_remove_knet_transport_options(self):
        config = dedent(
            """\
            totem {{{0}
                ip_version: ipv4
                knet_pmtud_interval: 1234
                link_mode: active
                knet_compression_level: 5
                knet_compression_model: zlib
                knet_compression_threshold: 1234
                crypto_cipher: aes256
                crypto_hash: sha256
                crypto_model: nss
            }}
        """,
        ).format(self.knet_transport)
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "link_mode": "",
                "knet_pmtud_interval": "",
                "ip_version": "",
            },
            {
                "threshold": "",
                "model": "",
                "level": "",
            },
            {
                "model": "",
                "hash": "",
                "cipher": "",
            },
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            "totem {\n    transport: knet\n}\n" if self.knet_transport else "",
            facade.config.export(),
        )

    def test_modify_knet_transport_options(self):
        config = dedent(
            """\
            totem {{{0}
                ip_version: ipv4
                knet_pmtud_interval: 1234
                link_mode: active
                knet_compression_level: 5
                knet_compression_model: zlib
                knet_compression_threshold: 1234
                crypto_cipher: aes256
                crypto_hash: sha256
                crypto_model: nss
            }}
        """,
        ).format(self.knet_transport)
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "link_mode": "passive",
                "knet_pmtud_interval": "1000",
                "ip_version": "ipv6",
            },
            {
                "threshold": "1000",
                "model": "lz4",
                "level": "9",
            },
            {
                "model": "openssl",
                "hash": "md5",
                "cipher": "aes128",
            },
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                """\
                totem {{{0}
                    ip_version: ipv6
                    knet_pmtud_interval: 1000
                    link_mode: passive
                    knet_compression_level: 9
                    knet_compression_model: lz4
                    knet_compression_threshold: 1000
                    crypto_cipher: aes128
                    crypto_hash: md5
                    crypto_model: openssl
                }}
            """
            ).format(self.knet_transport),
            facade.config.export(),
        )

    def test_add_knet_transport_options_multiple_sections(self):
        config = dedent(
            """\
            totem {{{0}
                knet_pmtud_interval: 1000
                knet_compression_model: zlib
                crypto_cipher: aes256
            }}

            totem {{
                knet_pmtud_interval: 2000
                knet_compression_model: lza4
                crypto_hash: sha256
            }}
        """
        ).format(self.knet_transport)
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "link_mode": "active",
                "ip_version": "ipv6",
            },
            {"level": "5"},
            {"model": "openssl"},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                """\
                totem {{{0}
                    knet_pmtud_interval: 1000
                    knet_compression_model: zlib
                    crypto_cipher: aes256
                }}

                totem {{
                    knet_pmtud_interval: 2000
                    knet_compression_model: lza4
                    crypto_hash: sha256
                    ip_version: ipv6
                    link_mode: active
                    knet_compression_level: 5
                    crypto_model: openssl
                }}
            """
            ).format(self.knet_transport),
            facade.config.export(),
        )

    def test_remove_knet_transport_options_multiple_sections(self):
        config = dedent(
            """\
            totem {{{0}
                ip_version: ipv6
                knet_pmtud_interval: 1000
                knet_compression_model: zlib
                crypto_cipher: aes256
                ip_version: ipv4
            }}

            totem {{
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv4
                link_mode: active
                knet_pmtud_interval: 2000
                knet_compression_model: lza4
                knet_compression_level: 5
                crypto_hash: sha256
                crypto_model: nss
            }}
        """
        ).format(self.knet_transport)
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "ip_version": "",
                "link_mode": "",
            },
            {"model": ""},
            {"cipher": "", "hash": ""},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                """\
                totem {{{0}
                    knet_pmtud_interval: 1000
                }}

                totem {{
                    knet_pmtud_interval: 2000
                    knet_compression_level: 5
                    crypto_model: nss
                }}
            """,
            ).format(self.knet_transport),
            facade.config.export(),
        )

    def test_modify_knet_transport_options_multiple_sections(self):
        config = dedent(
            """\
            totem {{{0}
                ip_version: ipv6
                knet_pmtud_interval: 1000
                link_mode: active
                knet_compression_model: zlib
                knet_compression_level: 5
                knet_compression_threshold: 100
                crypto_cipher: aes256
                crypto_hash: sha512
                ip_version: ipv4
                crypto_model: nss
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv4
                knet_pmtud_interval: 2000
                knet_compression_model: lza4
                knet_compression_level: 5
                crypto_hash: sha256
                crypto_model: openssl
            }}
        """
        ).format(self.knet_transport)
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "ip_version": "ipv4-6",
                "link_mode": "passive",
            },
            {"model": "zlib", "threshold": "100"},
            {"cipher": "aes128", "hash": "md5"},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                """\
                totem {{{0}
                    knet_pmtud_interval: 1000
                    knet_compression_level: 5
                    crypto_model: nss
                }}

                totem {{
                    ip_version: ipv4-6
                    knet_pmtud_interval: 2000
                    knet_compression_model: zlib
                    knet_compression_level: 5
                    crypto_hash: md5
                    crypto_model: openssl
                    link_mode: passive
                    knet_compression_threshold: 100
                    crypto_cipher: aes128
                }}
            """,
            ).format(self.knet_transport),
            facade.config.export(),
        )

    def test_modify_knet_transport_options_transport_override(self):
        config = dedent(
            """\
            totem {{{0}
                ip_version: ipv6
                knet_pmtud_interval: 1000
                link_mode: active
                knet_compression_model: zlib
                knet_compression_level: 5
                knet_compression_threshold: 100
                crypto_cipher: aes256
                crypto_hash: sha512
                ip_version: ipv4
                crypto_model: nss
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv6
            }}

            totem {{
                transport: udp
                ip_version: ipv4
                knet_pmtud_interval: 2000
                knet_compression_model: lza4
                knet_compression_level: 5
                crypto_hash: sha256
                crypto_model: openssl
            }}
        """
        ).format(self.knet_transport)
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "ip_version": "ipv4-6",
                "link_mode": "passive",
            },
            {"model": "zlib", "threshold": "100"},
            {"cipher": "aes128", "hash": "md5"},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                """\
                totem {{{0}
                    knet_pmtud_interval: 1000
                    knet_compression_model: zlib
                    knet_compression_level: 5
                    knet_compression_threshold: 100
                    crypto_cipher: aes256
                    crypto_hash: sha512
                    crypto_model: nss
                }}

                totem {{
                    transport: udp
                    ip_version: ipv4-6
                    knet_pmtud_interval: 2000
                    knet_compression_model: lza4
                    knet_compression_level: 5
                    crypto_hash: sha256
                    crypto_model: openssl
                    link_mode: passive
                }}
            """,
            ).format(self.knet_transport),
            facade.config.export(),
        )


class SetTransportOptionsDefaultKnetTest(
    SetTransportOptionsKnetMixin, TestCase
):
    knet_transport = ""


class SetTransportOptionsDefinedKnetTest(
    SetTransportOptionsKnetMixin, TestCase
):
    knet_transport = "\n    transport: knet"


class SetTransportOptionsUdpMixin:
    udp_transport = None

    def test_add_udp_transport_options_generic_only(self):
        config = dedent(
            f"""\
            totem {{
                transport: {self.udp_transport}
            }}
        """
        )
        facade = _get_facade(config)
        facade.set_transport_options(
            {"ip_version": "ipv4", "netmtu": "1500"},
            {
                "threshold": "1234",
                "model": "zlib",
                "level": "5",
            },
            {
                "model": "nss",
                "hash": "sha256",
                "cipher": "aes256",
            },
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                f"""\
                totem {{
                    transport: {self.udp_transport}
                    ip_version: ipv4
                    netmtu: 1500
                }}
            """
            ),
            facade.config.export(),
        )

    def test_remove_udp_transport_options_generic_only(self):
        config = dedent(
            f"""\
            totem {{
                transport: {self.udp_transport}
                ip_version: ipv4
                netmtu: 1500
                knet_pmtud_interval: 1234
                knet_compression_model: zlib
                crypto_cipher: aes256
                crypto_hash: sha256
            }}
        """
        )
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "ip_version": "",
                "netmtu": "",
                "knet_pmtud_interval": "",
            },
            {"model": ""},
            {
                "": "",
                "cipher": "",
            },
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                f"""\
                totem {{
                    transport: {self.udp_transport}
                    knet_compression_model: zlib
                    crypto_cipher: aes256
                    crypto_hash: sha256
                }}
            """
            ),
            facade.config.export(),
        )

    def test_modify_udp_transport_options_generic_only(self):
        config = dedent(
            f"""\
            totem {{
                transport: {self.udp_transport}
                ip_version: ipv4
                netmtu: 1500
                knet_pmtud_interval: 1234
                knet_compression_model: zlib
                crypto_cipher: aes256
                crypto_hash: sha256
            }}
        """
        )
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "ip_version": "ipv6",
                "netmtu": "1000",
                "knet_pmtud_interval": "1000",
            },
            {"model": "lz4"},
            {"cipher": "aes128", "hash": "md5"},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                f"""\
                totem {{
                    transport: {self.udp_transport}
                    ip_version: ipv6
                    netmtu: 1000
                    knet_pmtud_interval: 1000
                    knet_compression_model: zlib
                    crypto_cipher: aes256
                    crypto_hash: sha256
                }}
            """
            ),
            facade.config.export(),
        )

    def test_add_udp_transport_options_multiple_sections(self):
        config = dedent(
            f"""\
            totem {{
                transport: {self.udp_transport}
                knet_pmtud_interval: 1000
                knet_compression_model: zlib
                crypto_cipher: aes256
            }}

            totem {{
                knet_pmtud_interval: 2000
                knet_compression_model: lza4
                crypto_hash: sha256
            }}
        """
        )
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "ip_version": "ipv6",
                "netmtu": "1000",
            },
            {"level": "5"},
            {"model": "openssl"},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                f"""\
                totem {{
                    transport: {self.udp_transport}
                    knet_pmtud_interval: 1000
                    knet_compression_model: zlib
                    crypto_cipher: aes256
                }}

                totem {{
                    knet_pmtud_interval: 2000
                    knet_compression_model: lza4
                    crypto_hash: sha256
                    ip_version: ipv6
                    netmtu: 1000
                }}
            """
            ),
            facade.config.export(),
        )

    def test_remove_udp_transport_options_multiple_sections(self):
        config = dedent(
            f"""\
            totem {{
                transport: {self.udp_transport}
                ip_version: ipv6
                knet_pmtud_interval: 1000
                knet_compression_model: zlib
                crypto_cipher: aes256
                ip_version: ipv4
            }}

            totem {{
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv4
                netmtu: 1000
                knet_pmtud_interval: 2000
                knet_compression_model: lza4
                crypto_hash: sha256
            }}
        """
        )
        facade = _get_facade(config)
        facade.set_transport_options(
            {"ip_version": "", "netmtu": "", "knet_pmtud_interval": ""},
            {"model": ""},
            {"cipher": "", "hash": ""},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                f"""\
                totem {{
                    transport: {self.udp_transport}
                    knet_compression_model: zlib
                    crypto_cipher: aes256
                }}

                totem {{
                    knet_compression_model: lza4
                    crypto_hash: sha256
                }}
            """
            ),
            facade.config.export(),
        )

    def test_modify_udp_transport_options_multiple_sections(self):
        config = dedent(
            f"""\
            totem {{
                transport: {self.udp_transport}
                ip_version: ipv4
                knet_pmtud_interval: 1000
                knet_compression_model: zlib
                crypto_cipher: aes256
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv6
                netmtu: 1000
                knet_pmtud_interval: 2000
                knet_compression_model: lza4
                crypto_hash: sha256
                netmtu: 2000
            }}
        """
        )
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "ip_version": "ipv4-6",
                "netmtu": "1500",
                "knet_pmtud_interval": "2000",
            },
            {"model": "lza4"},
            {"cipher": "aes128", "hash": "md5"},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                f"""\
                totem {{
                    transport: {self.udp_transport}
                    knet_compression_model: zlib
                    crypto_cipher: aes256
                }}

                totem {{
                    ip_version: ipv4-6
                    netmtu: 1500
                    knet_pmtud_interval: 2000
                    knet_compression_model: lza4
                    crypto_hash: sha256
                }}
            """
            ),
            facade.config.export(),
        )

    def test_modify_udp_transport_options_transport_override(self):
        config = dedent(
            f"""\
            totem {{
                transport: {self.udp_transport}
                ip_version: ipv4
                knet_pmtud_interval: 1000
                knet_compression_model: zlib
                crypto_cipher: aes256
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv6
            }}

            totem {{
                ip_version: ipv6
                transport: knet
                netmtu: 1000
                knet_pmtud_interval: 2000
                knet_compression_model: lza4
                crypto_hash: sha256
                netmtu: 2000
            }}
        """
        )
        facade = _get_facade(config)
        facade.set_transport_options(
            {
                "ip_version": "ipv4-6",
                "netmtu": "1500",
                "knet_pmtud_interval": "2000",
            },
            {"model": "lza4"},
            {"cipher": "aes128", "hash": "md5"},
        )
        self.assertTrue(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(
            dedent(
                f"""\
                totem {{
                    transport: {self.udp_transport}
                }}

                totem {{
                    ip_version: ipv4-6
                    transport: knet
                    netmtu: 1500
                    knet_pmtud_interval: 2000
                    knet_compression_model: lza4
                    crypto_hash: md5
                    crypto_cipher: aes128
                }}
            """
            ),
            facade.config.export(),
        )


class SetTransportOptionsUdpTest(SetTransportOptionsUdpMixin, TestCase):
    udp_transport = "udp"


class SetTransportOptionsUdpuTest(SetTransportOptionsUdpMixin, TestCase):
    udp_transport = "udpu"


class SetTransportOptionsGeneralTest(TestCase):
    _option_prefix_list = ["", "knet_compression_", "crypto_"]

    _remove_option_params_list = [
        ({"option": ""}, {}, {}),
        ({}, {"option": ""}, {}),
        ({}, {}, {"option": ""}),
    ]

    _add_option_params_list = [
        ({"option": "value"}, {}, {}),
        ({}, {"option": "value"}, {}),
        ({}, {}, {"option": "value"}),
    ]

    _udp_do_not_modify_params_list = [
        ({}, {}, {}),
        ({}, {"option": "value"}, {}),
        ({}, {}, {"option": "value"}),
    ]

    _transport_option_tmplt = dedent(
        """\
        totem {{{{
            transport: {transport}
            {{_prefix}}option: value
        }}}}
    """,
    )

    def _assert_set_transport_options(self, params_list, before, after):
        for idx, params in enumerate(params_list):
            with self.subTest(params=params):
                facade = _get_facade(
                    before.format(_prefix=self._option_prefix_list[idx])
                )
                facade.set_transport_options(*params)
                self.assertFalse(facade.need_qdevice_reload)
                self.assertFalse(facade.need_stopped_cluster)
                self.assertEqual(
                    after.format(_prefix=self._option_prefix_list[idx]),
                    facade.config.export(),
                )

    def test_noop_on_no_options(self):
        self._assert_set_transport_options([({}, {}, {})], "", "")

    def test_add_missing_section(self):
        self._assert_set_transport_options(
            self._add_option_params_list,
            "",
            dedent(
                """\
                totem {{
                    {_prefix}option: value
                }}
            """
            ),
        )

    def test_do_not_add_missing_section(self):
        self._assert_set_transport_options(
            self._remove_option_params_list,
            "",
            "",
        )

    def test_remove_empty_section(self):
        for transport, params in [
            ("", self._remove_option_params_list),
            ("knet", self._remove_option_params_list),
            ("udp", self._remove_option_params_list[0:1]),
            ("udpu", self._remove_option_params_list[0:1]),
        ]:
            with self.subTest(transport=transport, params=params):
                self._assert_set_transport_options(
                    params,
                    dedent(
                        f"""\
                        totem {{{{
                            {{_prefix}}option: value
                        }}}}

                        totem {{{{
                            transport: {transport}
                        }}}}
                    """,
                    ),
                    dedent(
                        f"""\
                        totem {{{{
                            transport: {transport}
                        }}}}
                    """,
                    ),
                )

    def test_do_not_remove_option(self):
        params = self._udp_do_not_modify_params_list
        for transport, params_list in [("udp", params), ("udpu", params)]:
            with self.subTest(transport=transport, params=params):
                self._assert_set_transport_options(
                    params_list,
                    self._transport_option_tmplt.format(transport=transport),
                    self._transport_option_tmplt.format(transport=transport),
                )

    def test_modify_option(self):
        params = self._add_option_params_list
        for transport, params_list in [
            ("", params),
            ("knet", params),
            ("udp", params[0:1]),
            ("udpu", params[0:1]),
        ]:
            with self.subTest(transport=transport, params=params):
                self._assert_set_transport_options(
                    params_list,
                    dedent(
                        f"""\
                        totem {{{{
                            transport: {transport}
                            {{_prefix}}option: old_value
                        }}}}
                    """,
                    ),
                    self._transport_option_tmplt.format(transport=transport),
                )

    def test_do_not_modify_option(self):
        params = self._udp_do_not_modify_params_list
        for transport, params_list in [("udp", params), ("udpu", params)]:
            with self.subTest(transport=transport, params=params):
                self._assert_set_transport_options(
                    params_list,
                    self._transport_option_tmplt.format(transport=transport),
                    self._transport_option_tmplt.format(transport=transport),
                )


class GetOptionsDictMixin:
    _empty_transport_options_template = dedent(
        """
        totem {{
            version: 2
            cluster_name: test99
            transport: {transport}
            ip_version:
            netmtu:
            knet_pmtud_interval:
            link_mode:
            knet_compression_level:
            knet_compression_model:
            knet_compression_threshold:
            crypto_cipher:
            crypto_hash:
            crypto_model:
            block_unlisted_ips:
            consensus:
            downcheck:
            fail_recv_const:
            heartbeat_failures_allowed:
            hold:
            join:
            max_messages:
            max_network_delay:
            merge:
            miss_count_const:
            send_join:
            seqno_unchanged_const:
            token:
            token_coefficient:
            token_retransmit:
            token_retransmits_before_loss_const:
            window_size:
        }}
    """
    )

    _transport_options_template = dedent(
        """
        totem {{
            version: 2
            cluster_name: test99
            transport: {transport}
            ip_version: ipv4-6
            netmtu: 1500
            knet_pmtud_interval: 1234
            link_mode: active
            knet_compression_level: 5
            knet_compression_model: zlib
            knet_compression_threshold: 100
            crypto_cipher: aes256
            crypto_hash: sha256
            crypto_model: nss
            block_unlisted_ips: yes
            consensus: 3600
            downcheck: 1000
            fail_recv_const: 2500
            heartbeat_failures_allowed: 0
            hold: 180
            join: 50
            max_messages: 17
            max_network_delay: 50
            merge: 200
            miss_count_const: 5
            send_join: 0
            seqno_unchanged_const: 30
            token: 3000
            token_coefficient: 650
            token_retransmit: 238
            token_retransmits_before_loss_const: 4
            window_size: 50
        }}
    """
    )

    def _assert_option_dict(self, expected_dict, config):
        facade = _get_facade(config)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(expected_dict, self.getter(facade))

    def _assert_transport_option_dict(
        self, transport_list, expected_dict, config_template
    ):
        for transport in transport_list:
            with self.subTest(transport=transport):
                self._assert_option_dict(
                    expected_dict, config_template.format(transport=transport)
                )

    def test_empty_config(self):
        self._assert_option_dict({}, "")

    def test_empty_totem_section(self):
        self._assert_option_dict({}, "totem {\n}\n")


class GetTransportOptions(GetOptionsDictMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_transport_options()

    def test_empty_options_knet(self):
        self._assert_transport_option_dict(
            ["", "knet"],
            {"ip_version": "", "knet_pmtud_interval": "", "link_mode": ""},
            self._empty_transport_options_template,
        )

    def test_empty_options_udp(self):
        self._assert_transport_option_dict(
            ["udp", "udpu"],
            {"ip_version": "", "netmtu": ""},
            self._empty_transport_options_template,
        )

    def test_options_knet(self):
        self._assert_transport_option_dict(
            ["", "knet"],
            {
                "ip_version": "ipv4-6",
                "knet_pmtud_interval": "1234",
                "link_mode": "active",
            },
            self._transport_options_template,
        )

    def test_options_udp(self):
        self._assert_transport_option_dict(
            ["udp", "udpu"],
            {"ip_version": "ipv4-6", "netmtu": "1500"},
            self._transport_options_template,
        )


class GetCompressionOptions(GetOptionsDictMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_compression_options()

    def test_empty_compression_options(self):
        self._assert_transport_option_dict(
            ["", "knet", "udp", "udpu"],
            {"level": "", "model": "", "threshold": ""},
            self._empty_transport_options_template,
        )

    def test_compression_options(self):
        self._assert_transport_option_dict(
            ["", "knet", "udp", "udpu"],
            {"level": "5", "model": "zlib", "threshold": "100"},
            self._transport_options_template,
        )


class GetCryptoOptions(GetOptionsDictMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_crypto_options()

    def test_empty_crypto_options(self):
        self._assert_transport_option_dict(
            ["", "knet", "udp", "udpu"],
            {"cipher": "", "hash": "", "model": ""},
            self._empty_transport_options_template,
        )

    def test_crypto_options(self):
        self._assert_transport_option_dict(
            ["", "knet", "udp", "udpu"],
            {"cipher": "aes256", "hash": "sha256", "model": "nss"},
            self._transport_options_template,
        )


FIXTURE_TOTEM_TOKEN_OPTIONS = {
    "block_unlisted_ips": "yes",
    "consensus": "3600",
    "downcheck": "1000",
    "fail_recv_const": "2500",
    "heartbeat_failures_allowed": "0",
    "hold": "180",
    "join": "50",
    "max_messages": "17",
    "max_network_delay": "50",
    "merge": "200",
    "miss_count_const": "5",
    "send_join": "0",
    "seqno_unchanged_const": "30",
    "token": "3000",
    "token_coefficient": "650",
    "token_retransmit": "238",
    "token_retransmits_before_loss_const": "4",
    "window_size": "50",
}


FIXTURE_EMPTY_TOTEM_TOKEN_OPTIONS = {
    "block_unlisted_ips": "",
    "consensus": "",
    "downcheck": "",
    "fail_recv_const": "",
    "heartbeat_failures_allowed": "",
    "hold": "",
    "join": "",
    "max_messages": "",
    "max_network_delay": "",
    "merge": "",
    "miss_count_const": "",
    "send_join": "",
    "seqno_unchanged_const": "",
    "token": "",
    "token_coefficient": "",
    "token_retransmit": "",
    "token_retransmits_before_loss_const": "",
    "window_size": "",
}


class GetTotemOptions(GetOptionsDictMixin, TestCase):
    @staticmethod
    def getter(facade):
        return facade.get_totem_options()

    def test_empty_totem_options(self):
        self._assert_transport_option_dict(
            ["", "knet", "udp", "udpu"],
            FIXTURE_EMPTY_TOTEM_TOKEN_OPTIONS,
            self._empty_transport_options_template,
        )

    def test_totem_options(self):
        self._assert_transport_option_dict(
            ["", "knet", "udp", "udpu"],
            FIXTURE_TOTEM_TOKEN_OPTIONS,
            self._transport_options_template,
        )


class SetTotemOptionsTest(TestCase):
    _fixture_totem_token_config = dedent(
        """\
        totem {
            block_unlisted_ips: yes
            consensus: 3600
            downcheck: 1000
            fail_recv_const: 2500
            heartbeat_failures_allowed: 0
            hold: 180
            join: 50
            max_messages: 17
            max_network_delay: 50
            merge: 200
            miss_count_const: 5
            send_join: 0
            seqno_unchanged_const: 30
            token: 3000
            token_coefficient: 650
            token_retransmit: 238
            token_retransmits_before_loss_const: 4
            window_size: 50
        }
    """,
    )

    def _assert_set_totem_options(self, options, before, after):
        facade = _get_facade(before)
        facade.set_totem_options(options)
        self.assertFalse(facade.need_stopped_cluster)
        self.assertFalse(facade.need_qdevice_reload)
        self.assertEqual(after, facade.config.export())

    def test_add_totem_options(self):
        self._assert_set_totem_options(
            FIXTURE_TOTEM_TOKEN_OPTIONS,
            "",
            self._fixture_totem_token_config,
        )

    def test_remove_totem_options(self):
        self._assert_set_totem_options(
            FIXTURE_EMPTY_TOTEM_TOKEN_OPTIONS,
            self._fixture_totem_token_config,
            "",
        )

    def test_modify_totem_options(self):
        self._assert_set_totem_options(
            {
                "block_unlisted_ips": "no",
                "consensus": "7200",
                "downcheck": "2000",
                "fail_recv_const": "5000",
                "heartbeat_failures_allowed": "1",
                "hold": "360",
                "join": "100",
                "max_messages": "20",
                "max_network_delay": "100",
                "merge": "400",
                "miss_count_const": "10",
                "send_join": "1",
                "seqno_unchanged_const": "60",
                "token": "6000",
                "token_coefficient": "1300",
                "token_retransmit": "476",
                "token_retransmits_before_loss_const": "8",
                "window_size": "100",
            },
            self._fixture_totem_token_config,
            dedent(
                """\
                totem {
                    block_unlisted_ips: no
                    consensus: 7200
                    downcheck: 2000
                    fail_recv_const: 5000
                    heartbeat_failures_allowed: 1
                    hold: 360
                    join: 100
                    max_messages: 20
                    max_network_delay: 100
                    merge: 400
                    miss_count_const: 10
                    send_join: 1
                    seqno_unchanged_const: 60
                    token: 6000
                    token_coefficient: 1300
                    token_retransmit: 476
                    token_retransmits_before_loss_const: 8
                    window_size: 100
                }
            """,
            ),
        )
