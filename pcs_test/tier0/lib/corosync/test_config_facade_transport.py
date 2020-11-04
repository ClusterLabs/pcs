from textwrap import dedent
from unittest import TestCase

import pcs.lib.corosync.config_facade as lib


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

    def _assert_needs_stoped_cluster(self, config, need_stopped, option_list):
        for options in option_list:
            with self.subTest(options):
                facade = lib.ConfigFacade.from_string(config)
                facade.set_transport_options(options, {}, {})
                self.assertEqual(facade.need_stopped_cluster, need_stopped)

    def test_remove_not_present_options(self):
        self._assert_needs_stoped_cluster("", False, self._option_list_empty)

    def test_remove_present_empty_options(self):
        config = dedent(
            """\
            totem {
                ip_version:
                netmtu:
            }
        """
        )
        self._assert_needs_stoped_cluster(
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
        self._assert_needs_stoped_cluster(config, True, self._option_list_empty)

    def test_modify_present_options(self):
        config = dedent(
            """\
            totem {
                ip_version: ipv4-6
                netmtu: 1500
            }
        """
        )
        self._assert_needs_stoped_cluster(
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
        self._assert_needs_stoped_cluster(config, False, not_banned_options)


class SetTransportOptionsKnetBase:
    # pylint: disable=no-member
    knet_transport = None

    def test_add_knet_transport_options(self):
        config = dedent(
            """\
            totem {{{0}
            }}
        """
        ).format(self.knet_transport)
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {
                "link_mode": "active",
                "knet_pmtud_interval": "1234",
                "ip_version": "ipv4",
            },
            {"threshold": "1234", "model": "zlib", "level": "5",},
            {"model": "nss", "hash": "sha256", "cipher": "aes256",},
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
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {"link_mode": "", "knet_pmtud_interval": "", "ip_version": "",},
            {"threshold": "", "model": "", "level": "",},
            {"model": "", "hash": "", "cipher": "",},
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
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {
                "link_mode": "passive",
                "knet_pmtud_interval": "1000",
                "ip_version": "ipv6",
            },
            {"threshold": "1000", "model": "lz4", "level": "9",},
            {"model": "openssl", "hash": "md5", "cipher": "aes128",},
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
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {"link_mode": "active", "ip_version": "ipv6",},
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
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {"ip_version": "", "link_mode": "",},
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
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {"ip_version": "ipv4-6", "link_mode": "passive",},
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
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {"ip_version": "ipv4-6", "link_mode": "passive",},
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


class SetTransportOptionsDefaultKnetTest(SetTransportOptionsKnetBase, TestCase):
    knet_transport = ""


class SetTransportOptionsDefinedKnetTest(SetTransportOptionsKnetBase, TestCase):
    knet_transport = "\n    transport: knet"


class SetTransportOptionsUdpBase:
    # pylint: disable=no-member
    udp_transport = None

    def test_add_udp_transport_options_generic_only(self):
        config = dedent(
            f"""\
            totem {{
                transport: {self.udp_transport}
            }}
        """
        )
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {"ip_version": "ipv4", "netmtu": "1500"},
            {"threshold": "1234", "model": "zlib", "level": "5",},
            {"model": "nss", "hash": "sha256", "cipher": "aes256",},
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
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {"ip_version": "", "netmtu": "", "knet_pmtud_interval": "",},
            {"model": ""},
            {"": "", "cipher": "",},
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
        facade = lib.ConfigFacade.from_string(config)
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
        facade = lib.ConfigFacade.from_string(config)
        facade.set_transport_options(
            {"ip_version": "ipv6", "netmtu": "1000",},
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
        facade = lib.ConfigFacade.from_string(config)
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
        facade = lib.ConfigFacade.from_string(config)
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
        facade = lib.ConfigFacade.from_string(config)
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


class SetTransportOptionsUdpTest(SetTransportOptionsUdpBase, TestCase):
    udp_transport = "udp"


class SetTransportOptionsUdpuTest(SetTransportOptionsUdpBase, TestCase):
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
                facade = lib.ConfigFacade.from_string(
                    before.format(_prefix=self._option_prefix_list[idx]),
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
            self._remove_option_params_list, "", "",
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
        for transport, params in [("udp", params), ("udpu", params)]:
            with self.subTest(transport=transport, params=params):
                self._assert_set_transport_options(
                    params,
                    self._transport_option_tmplt.format(transport=transport),
                    self._transport_option_tmplt.format(transport=transport),
                )

    def test_modify_option(self):
        params = self._add_option_params_list
        for transport, params in [
            ("", params),
            ("knet", params),
            ("udp", params[0:1]),
            ("udpu", params[0:1]),
        ]:
            with self.subTest(transport=transport, params=params):
                self._assert_set_transport_options(
                    params,
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
        for transport, params in [("udp", params), ("udpu", params)]:
            with self.subTest(transport=transport, params=params):
                self._assert_set_transport_options(
                    params,
                    self._transport_option_tmplt.format(transport=transport),
                    self._transport_option_tmplt.format(transport=transport),
                )
