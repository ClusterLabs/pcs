from unittest import TestCase

from pcs.common import report_codes
from pcs.lib.corosync import config_validators
from pcs.lib.errors import ReportItemSeverity as severity
from pcs.test.tools import fixture
from pcs.test.tools.assertions import assert_report_item_list_equal


class CreateLinkListUdp(TestCase):
    def test_no_links(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp([]),
            []
        )

    def test_no_options(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp([{}]),
            []
        )

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "bindnetaddr": "10.0.0.1",
                        "broadcast": "0",
                        "mcastaddr": "225.0.0.1",
                        "mcastport": "5405",
                        "ttl": "12",
                    }
                ]
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "bindnetaddr": "my-network",
                        "broadcast": "yes",
                        "mcastaddr": "my-group",
                        "mcastport": "0",
                        "ttl": "256",
                    }
                ]
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="my-network",
                    option_name="bindnetaddr",
                    allowed_values="an IP address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="yes",
                    option_name="broadcast",
                    allowed_values=("0", "1")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="my-group",
                    option_name="mcastaddr",
                    allowed_values="an IP address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="0",
                    option_name="mcastport",
                    allowed_values="a port number (1-65535)"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="256",
                    option_name="ttl",
                    allowed_values="0..255"
                ),
            ]
        )

    def test_invalid_options(self):
        allowed_options = [
        "bindnetaddr",
        "broadcast",
        "mcastaddr",
        "mcastport",
        "ttl",
        ]
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "linknumber": "0",
                        "nonsense": "doesnt matter",
                    }
                ]
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["linknumber", "nonsense"],
                    option_type="link",
                    allowed=allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_more_links(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {"ttl": "64"},
                    {"ttl": "64"},
                ]
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_TOO_MANY_LINKS,
                    actual_count=2,
                    max_count=1,
                    transport="udp/udpu"
                )
            ]
        )

    def test_broadcast_default_mcastaddr_set(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "mcastaddr": "225.0.0.1"
                    }
                ]
            ),
            [
            ]
        )

    def test_broadcast_disabled_mcastaddr_set(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "broadcast": "0",
                        "mcastaddr": "225.0.0.1"
                    }
                ]
            ),
            [
            ]
        )

    def test_broadcast_enabled_mcastaddr_set(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_udp(
                [
                    {
                        "broadcast": "1",
                        "mcastaddr": "225.0.0.1"
                    }
                ]
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_DISABLED,
                    option_name="mcastaddr",
                    option_type="link",
                    prerequisite_name="broadcast",
                    prerequisite_type="link"
                ),
            ]
        )


class CreateLinkListKnet(TestCase):
    def test_no_links(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet([], 8),
            []
        )

    def test_no_options(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet([{}], 8),
            []
        )

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "ip_version": "ipv4",
                        "linknumber": "0",
                        "link_priority": "20",
                        "mcastport": "5405",
                        "ping_interval": "250",
                        "ping_precision": "15",
                        "ping_timeout": "750",
                        "pong_count": "10",
                        "transport": "sctp",
                    },
                    {
                        "ip_version": "ipv6",
                        "linknumber": "1",
                        "link_priority": "10",
                        "mcastport": "5415",
                        "ping_interval": "2500",
                        "ping_precision": "150",
                        "ping_timeout": "7500",
                        "pong_count": "100",
                        "transport": "udp",
                    }
                ],
                2
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "ip_version": "ipv5",
                        "linknumber": "-1",
                        "link_priority": "256",
                        "mcastport": "65536",
                        "transport": "tcp",
                    },
                    {
                        "ping_interval": "-250",
                        "ping_precision": "-15",
                        "ping_timeout": "-750",
                        "pong_count": "-10",
                        "transport": "udpu",
                    }
                ],
                3
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv5",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-1",
                    option_name="linknumber",
                    allowed_values="0..3"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="256",
                    option_name="link_priority",
                    allowed_values="0..255"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="65536",
                    option_name="mcastport",
                    allowed_values="a port number (1-65535)"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="tcp",
                    option_name="transport",
                    allowed_values=("sctp", "udp")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-250",
                    option_name="ping_interval",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-15",
                    option_name="ping_precision",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-750",
                    option_name="ping_timeout",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-10",
                    option_name="pong_count",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="udpu",
                    option_name="transport",
                    allowed_values=("sctp", "udp")
                ),
            ]
        )

    def test_invalid_options(self):
        allowed_options = [
            "ip_version",
            "link_priority",
            "linknumber",
            "mcastport",
            "ping_interval",
            "ping_precision",
            "ping_timeout",
            "pong_count",
            "transport",
        ]
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "nonsense1": "0",
                        "nonsense2": "doesnt matter",
                    },
                    {
                        "nonsense3": "who cares",
                    }
                ],
                3
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense1", "nonsense2"],
                    option_type="link",
                    allowed=allowed_options,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense3"],
                    option_type="link",
                    allowed=allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_ping_dependencies(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "ping_interval": "250",
                        "ping_timeout": "750",
                    },
                    {
                        "ping_interval": "250",
                    },
                    {
                        "ping_timeout": "750",
                    },
                    {
                        "ping_interval": "",
                        "ping_timeout": "750",
                    },
                    {
                        "ping_interval": "250",
                        "ping_timeout": "",
                    },
                ],
                5
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="ping_interval",
                    option_type="link",
                    prerequisite_name="ping_timeout",
                    prerequisite_type="link"
                ),
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_IS_MISSING,
                    option_name="ping_timeout",
                    option_type="link",
                    prerequisite_name="ping_interval",
                    prerequisite_type="link"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="ping_interval",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="ping_timeout",
                    allowed_values="a non-negative integer"
                ),
            ]
        )

    def test_linknumber_within_range(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [{"linknumber": "2"}],
                2
            ),
            []
        )

    def test_linknumber_to_high(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [{"linknumber": "3"}],
                2
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="3",
                    option_name="linknumber",
                    allowed_values="0..2"
                ),
            ]
        )

    def test_link_count_in_range(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    { "ip_version": "ipv4"},
                    { "ip_version": "ipv4"},
                ],
                1
            ),
            [
            ]
        )

    def test_link_count_too_high(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                ],
                1
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_TOO_MANY_LINKS,
                    actual_count=3,
                    max_count=2,
                    transport="knet"
                )
            ]
        )

    def test_linknumber_not_unique(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {"linknumber": "2"},
                    {"linknumber": "0"},
                    {"linknumber": "0"},
                    {"linknumber": "1"},
                    {"linknumber": "2"},
                ],
                4
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_NUMBER_DUPLICATION,
                    link_number_list=["0", "2"]
                )
            ]
        )

    def test_max_link_number_too_low(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "ip_version": "ipv4",
                        "linknumber": "0",
                    },
                ],
                -1
            ),
            []
        )

    def test_max_link_number_too_high(self):
        assert_report_item_list_equal(
            config_validators.create_link_list_knet(
                [
                    {
                        "ip_version": "ipv4",
                        "linknumber": "8",
                    },
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                    {"ip_version": "ipv4"},
                ],
                8
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="8",
                    option_name="linknumber",
                    allowed_values="0..7"
                ),
                fixture.error(
                    report_codes.COROSYNC_TOO_MANY_LINKS,
                    actual_count=9,
                    max_count=8,
                    transport="knet"
                )
            ]
        )


class CreateTransportUdp(TestCase):
    def test_no_options(self):
        assert_report_item_list_equal(
            config_validators.create_transport_udp({}, {}, {}),
            []
        )

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_transport_udp(
                {
                    "ip_version": "ipv4",
                    "netmtu": "1234",
                },
                {},
                {}
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_transport_udp(
                {
                    "ip_version": "ipv5",
                    "netmtu": "-5",
                },
                {},
                {}
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv5",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-5",
                    option_name="netmtu",
                    allowed_values="a positive integer"
                ),
            ]
        )

    def test_invalid_option(self):
        assert_report_item_list_equal(
            config_validators.create_transport_udp(
                {
                    "knet_pmtud_interval": "1234",
                    "link_mode": "active",
                },
                {
                    "level": "5",
                    "model": "zlib",
                    "threshold": "1234",
                },
                {
                    "cipher": "aes256",
                    "hash": "sha256",
                    "model": "nss",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["knet_pmtud_interval", "link_mode"],
                    option_type="udp/udpu transport",
                    allowed=["ip_version", "netmtu"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
                    option_type="compression",
                    actual_transport="udp/udpu",
                    required_transport_list=("knet", )
                ),
                fixture.error(
                    report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
                    option_type="crypto",
                    actual_transport="udp/udpu",
                    required_transport_list=("knet", )
                ),
            ]
        )



class CreateTransportKnet(TestCase):
    def test_no_options(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet({}, {}, {}),
            []
        )

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {
                    "ip_version": "ipv4",
                    "knet_pmtud_interval": "1234",
                    "link_mode": "active",
                },
                {
                    "level": "5",
                    "model": "zlib",
                    "threshold": "1234",
                },
                {
                    "cipher": "aes256",
                    "hash": "sha256",
                    "model": "nss",
                }
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {
                    "ip_version": "ipv5",
                    "knet_pmtud_interval": "a minute",
                    "link_mode": "random",
                },
                {
                    "level": "maximum",
                    "model": "",
                    "threshold": "reasonable",
                },
                {
                    "cipher": "strongest",
                    "hash": "fastest",
                    "model": "best",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv5",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="a minute",
                    option_name="knet_pmtud_interval",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="random",
                    option_name="link_mode",
                    allowed_values=("active", "passive", "rr")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="maximum",
                    option_name="level",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="model",
                    allowed_values="a compression model e.g. zlib, lz4 or bzip2"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="reasonable",
                    option_name="threshold",
                    allowed_values="a non-negative integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="strongest",
                    option_name="cipher",
                    allowed_values=(
                        "none", "aes256", "aes192", "aes128", "3des"
                    )
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="fastest",
                    option_name="hash",
                    allowed_values=(
                        "none", "md5", "sha1", "sha256", "sha384", "sha512"
                    )
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="best",
                    option_name="model",
                    allowed_values=("nss", "openssl")
                ),
            ]
        )

    def test_invalid_options(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {
                    "level": "5",
                    "netmtu": "1500",
                },
                {
                    "cipher": "aes256",
                    "hash": "sha256",
                },
                {
                    "ip_version": "ipv4",
                    "link_mode": "active",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["level", "netmtu"],
                    option_type="knet transport",
                    allowed=["ip_version", "knet_pmtud_interval", "link_mode"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["cipher", "hash"],
                    option_type="compression",
                    allowed=["level", "model", "threshold"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["ip_version", "link_mode"],
                    option_type="crypto",
                    allowed=["cipher", "hash", "model"],
                    allowed_patterns=[],
                ),
            ]
        )

    def test_crypto_disabled(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "none",
                    "hash": "none",
                }
            ),
            []
        )

    def test_crypto_enabled_cipher_disabled_hash(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "aes256",
                    "hash": "none",
                }
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="cipher",
                    option_type="crypto",
                    prerequisite_name="hash",
                    prerequisite_type="crypto"
                )
            ]
        )

    def test_crypto_enabled_cipher_default_hash(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "aes256",
                }
            ),
            []
        )

    def test_crypto_disabled_cipher_default_hash(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "none",
                }
            ),
            []
        )

    def test_crypto_enabled_hash_disabled_cipher(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "cipher": "none",
                    "hash": "sha256",
                }
            ),
            []
        )

    def test_crypto_enabled_hash_default_cipher(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "hash": "sha256",
                }
            ),
            []
        )

    def test_crypto_disabled_hash_default_cipher(self):
        assert_report_item_list_equal(
            config_validators.create_transport_knet(
                {},
                {},
                {
                    "hash": "none",
                }
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="cipher",
                    option_type="crypto",
                    prerequisite_name="hash",
                    prerequisite_type="crypto"
                )
            ]
        )


class CreateTotem(TestCase):
    allowed_options = [
        "consensus",
        "downcheck",
        "fail_recv_const",
        "heartbeat_failures_allowed",
        "hold",
        "join",
        "max_messages",
        "max_network_delay",
        "merge",
        "miss_count_const",
        "send_join",
        "seqno_unchanged_const",
        "token",
        "token_coefficient",
        "token_retransmit",
        "token_retransmits_before_loss_const",
        "window_size",
    ]
    def test_no_options(self):
        assert_report_item_list_equal(
            config_validators.create_totem({}),
            []
        )

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.create_totem(
                {
                    name: value
                    for value, name in enumerate(self.allowed_options)
                }
            ),
            []
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            config_validators.create_totem(
                {
                    name: "x"
                    for name in self.allowed_options
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="x",
                    option_name=name,
                    allowed_values="a non-negative integer"
                )
                for name in self.allowed_options
            ]
        )

    def test_invalid_options(self):
        assert_report_item_list_equal(
            config_validators.create_totem(
                {
                    "nonsense1": "0",
                    "nonsense2": "doesnt matter",
                }
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["nonsense1", "nonsense2"],
                    option_type="totem",
                    allowed=self.allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )


class BaseQuorumOptions():
    def test_no_options(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                },
                has_qdevice
            ),
            []
        )

    def test_all_valid(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "0",
                    "last_man_standing": "1",
                    "last_man_standing_window": "1000",
                    "wait_for_all": "0",
                },
                has_qdevice
            ),
            []
        )

    def test_invalid_all_values(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "atb",
                    "last_man_standing": "lms",
                    "last_man_standing_window": "lmsw",
                    "wait_for_all": "wfa",
                },
                has_qdevice
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "auto_tie_breaker",
                        "option_value": "atb",
                        "allowed_values": ("0", "1"),
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "last_man_standing",
                        "option_value": "lms",
                        "allowed_values": ("0", "1"),
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "last_man_standing_window",
                        "option_value": "lmsw",
                        "allowed_values": "a positive integer",
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "wait_for_all",
                        "option_value": "wfa",
                        "allowed_values": ("0", "1"),
                    }
                ),
            ]
        )

    def test_invalid_option(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "1",
                    "nonsense1": "0",
                    "nonsense2": "doesnt matter",
                },
                has_qdevice
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["nonsense1", "nonsense2"],
                        "option_type": "quorum",
                        "allowed": [
                            "auto_tie_breaker",
                            "last_man_standing",
                            "last_man_standing_window",
                            "wait_for_all"
                        ],
                        "allowed_patterns": [],
                    }
                ),
            ]
        )

    def test_qdevice_incompatible_options(self):
        has_qdevice = True
        assert_report_item_list_equal(
            self.validator(
                {
                    "auto_tie_breaker": "1",
                    "last_man_standing": "1",
                    "last_man_standing_window": "250",
                    "wait_for_all": "1",
                },
                has_qdevice
            ),
            [
                (
                    severity.ERROR,
                    report_codes.COROSYNC_OPTIONS_INCOMPATIBLE_WITH_QDEVICE,
                    {
                        "options_names": [
                            "auto_tie_breaker",
                            "last_man_standing",
                            "last_man_standing_window",
                        ],
                    }
                ),
            ]
        )

    def test_qdevice_compatible_options(self):
        has_qdevice = True
        assert_report_item_list_equal(
            self.validator(
                {
                    "wait_for_all": "1",
                },
                has_qdevice
            ),
            []
        )

    def test_last_man_standing_required(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum"
                )
            ]
        )

    def test_last_man_standing_required_enabled(self):
        has_qdevice = False
        assert_report_item_list_equal(
            self.validator(
                {
                    "last_man_standing": "0",
                    "last_man_standing_window": "1000",
                },
                has_qdevice
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum"
                )
            ]
        )


class CreateQuorumOptions(BaseQuorumOptions, TestCase):
    def setUp(self):
        self.validator = config_validators.create_quorum_options


class QuorumOptionsUpdate(BaseQuorumOptions, TestCase):
    def setUp(self):
        self.validator = (
            lambda options, has_qdevice:
            config_validators.update_quorum_options(options, has_qdevice, {})
        )

    def test_last_man_standing_required_currently_disabled(self):
        has_qdevice = False
        assert_report_item_list_equal(
            config_validators.update_quorum_options(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice,
                {
                    "last_man_standing": "0",
                }
            ),
            [
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="last_man_standing_window",
                    option_type="quorum",
                    prerequisite_name="last_man_standing",
                    prerequisite_type="quorum"
                )
            ]
        )

    def test_last_man_standing_required_currently_enabled(self):
        has_qdevice = False
        assert_report_item_list_equal(
            config_validators.update_quorum_options(
                {
                    "last_man_standing_window": "1000",
                },
                has_qdevice,
                {
                    "last_man_standing": "1",
                }
            ),
            [
            ]
        )


class AddQuorumDevice(TestCase):
    def setUp(self):
        self.node_ids = ["1", "2", "3"]

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "127.0.0.1",
                    "port": "4433",
                    "algorithm": "ffsplit",
                    "connect_timeout": "12345",
                    "force_ip_version": "4",
                    "tie_breaker": "2",
                },
                {
                    "timeout": "23456",
                    "sync_timeout": "34567"
                },
                {
                    "mode": "on",
                    "timeout": "5",
                    "sync_timeout": "15",
                    "interval": "30",
                    "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                    "exec_ls": "test -f /tmp/test",
                },
                self.node_ids
            ),
            [
            ]
        )

    def test_bad_model(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "invalid",
                {},
                {},
                {},
                self.node_ids
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "model",
                        "option_value": "invalid",
                        "allowed_values": ["net", ],
                    },
                    report_codes.FORCE_QDEVICE_MODEL
                )
            ]
        )

    def test_bad_model_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "invalid",
                {},
                {},
                {},
                self.node_ids,
                force_model=True
            ),
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "model",
                        "option_value": "invalid",
                        "allowed_values": ["net", ],
                    },
                )
            ]
        )

    def test_missing_required_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {},
                {},
                {},
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["algorithm"],
                ),
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["host"],
                )
            ]
        )

    def test_missing_required_options_net_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {},
                {},
                {},
                self.node_ids,
                force_model=True,
                force_options=True
            ),
            [
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["algorithm"],
                ),
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["host"],
                )
            ]
        )

    def test_empty_required_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {"host": "", "algorithm": ""},
                {},
                {},
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms")
                )
            ]
        )

    def test_empty_required_options_net_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {"host": "", "algorithm": ""},
                {},
                {},
                self.node_ids,
                force_model=True,
                force_options=True
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms")
                )
            ]
        )

    def test_empty_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "",
                    "port": "",
                    "algorithm": "",
                    "connect_timeout": "",
                    "force_ip_version": "",
                    "tie_breaker": "",
                },
                {
                    "timeout": "",
                    "sync_timeout": "",
                },
                {
                    "mode": "",
                    "timeout": "",
                    "sync_timeout": "",
                    "interval": "",
                    "exec_ping": "",
                },
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "",
                        "allowed_values": "1000..120000",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "",
                        "allowed_values": ("0", "4", "6"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "",
                        "allowed_values": "a port number (1-65535)",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="mode",
                    option_value="",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="interval",
                    option_value="",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="sync_timeout",
                    option_value="",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="timeout",
                    option_value="",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="exec_ping",
                    option_value="",
                    allowed_values="a command to be run"
                ),
            ]
        )

    def test_bad_options_net(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "",
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                    "model": "some model",
                },
                {
                    "mode": "bad mode",
                    "timeout": "-5",
                    "sync_timeout": "-15",
                    "interval": "-30",
                    "exec_ping": "",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                },
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["model"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="exec_ping",
                    option_value="",
                    allowed_values="a command to be run"
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=[
                        "exec_ls bad", "exec_ls#bad", "exec_ls.bad",
                        "exec_ls:bad", "exec_ls{bad", "exec_ls}bad",
                    ],
                    option_type="heuristics",
                    allowed_description=(
                        "exec_NAME cannot contain '.:{}#' and whitespace "
                        "characters"
                    )
                )
            ]
        )

    def test_bad_options_net_forced(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "127.0.0.1",
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                },
                {
                    "mode": "bad mode",
                    "timeout": "-5",
                    "sync_timeout": "-15",
                    "interval": "-30",
                    "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                },
                self.node_ids,
                force_options=True
            ),
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    }
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    }
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
            ]
        )

    def test_cannot_force_bad_heuristics_exec_name(self):
        assert_report_item_list_equal(
            config_validators.add_quorum_device(
                "net",
                {
                    "host": "qnetd-host",
                    "algorithm": "ffsplit",
                },
                {},
                {
                    "mode": "on",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                },
                self.node_ids,
                force_options=True
            ),
            [
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=[
                        "exec_ls bad", "exec_ls#bad", "exec_ls.bad",
                        "exec_ls:bad", "exec_ls{bad", "exec_ls}bad",
                    ],
                    option_type="heuristics",
                    allowed_description=(
                        "exec_NAME cannot contain '.:{}#' and whitespace "
                        "characters"
                    )
                )
            ]
        )


class UpdateQuorumDevice(TestCase):
    def setUp(self):
        self.node_ids = ["1", "2", "3"]

    def test_all_valid(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "host": "127.0.0.1",
                    "port": "4433",
                    "algorithm": "ffsplit",
                    "connect_timeout": "12345",
                    "force_ip_version": "4",
                    "tie_breaker": "2",
                },
                {
                    "timeout": "23456",
                    "sync_timeout": "34567"
                },
                {
                    "mode": "on",
                    "timeout": "5",
                    "sync_timeout": "15",
                    "interval": "30",
                    "exec_ping": 'ping -q -c 1 "127.0.0.1"',
                    "exec_ls": "test -f /tmp/test",
                },
                self.node_ids
            ),
            [
            ]
        )

    def test_all_valid_empty(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "",
                    "connect_timeout": "",
                    "force_ip_version": "",
                    "tie_breaker": "",
                },
                {
                    "timeout": "",
                    "sync_timeout": ""
                },
                {
                    "mode": "",
                    "timeout": "",
                    "sync_timeout": "",
                    "interval": "",
                    "exec_ping": "",
                    "exec_ls": "",
                },
                self.node_ids
            ),
            [
            ]
        )

    def test_net_doesnt_require_host_and_algorithm(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "12345",
                },
                { },
                { },
                self.node_ids
            ),
            [
            ]
        )

    def test_net_host_and_algorithm_cannot_be_removed(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "host": "",
                    "algorithm": "",
                },
                {
                },
                {
                },
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms")
                )
            ]
        )

    def test_net_host_and_algorithm_cannot_be_removed_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "host": "",
                    "algorithm": "",
                },
                { },
                { },
                self.node_ids,
                force_options=True
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="host",
                    option_value="",
                    allowed_values="a qdevice host address"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="algorithm",
                    option_value="",
                    allowed_values=("ffsplit", "lms")
                )
            ]
        )

    def test_bad_net_options(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {},
                {},
                self.node_ids
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    },
                    report_codes.FORCE_OPTIONS
                ),
            ]
        )

    def test_bad_net_options_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {
                    "port": "65537",
                    "algorithm": "bad algorithm",
                    "connect_timeout": "-1",
                    "force_ip_version": "3",
                    "tie_breaker": "125",
                    "bad_model_option": "bad model value",
                },
                {},
                {},
                self.node_ids,
                force_options=True
            ),
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "algorithm",
                        "option_value": "bad algorithm",
                        "allowed_values": ("ffsplit", "lms"),
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_model_option"],
                        "option_type": "quorum device model",
                        "allowed": [
                            "algorithm",
                            "connect_timeout",
                            "force_ip_version",
                            "host",
                            "port",
                            "tie_breaker",
                        ],
                        "allowed_patterns": [],
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "connect_timeout",
                        "option_value": "-1",
                        "allowed_values": "1000..120000",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "force_ip_version",
                        "option_value": "3",
                        "allowed_values": ("0", "4", "6"),
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "port",
                        "option_value": "65537",
                        "allowed_values": "a port number (1-65535)",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "tie_breaker",
                        "option_value": "125",
                        "allowed_values": ["lowest", "highest"] + self.node_ids,
                    },
                ),
            ]
        )

    def test_bad_generic_options(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                    "model": "some model",
                },
                {},
                self.node_ids
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["model"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                ),
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    },
                    report_codes.FORCE_OPTIONS
                )
            ]
        )

    def test_bad_generic_options_cannot_force_model(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {"model": "some model", },
                {},
                self.node_ids,
                force_options=True
            ),
            [
                (
                    severity.ERROR,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["model"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    }
                )
            ]
        )

    def test_bad_generic_options_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {
                    "timeout": "-2",
                    "sync_timeout": "-3",
                    "bad_generic_option": "bad generic value",
                },
                {},
                self.node_ids,
                force_options=True
            ),
            [
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTIONS,
                    {
                        "option_names": ["bad_generic_option"],
                        "option_type": "quorum device",
                        "allowed": ["sync_timeout", "timeout"],
                        "allowed_patterns": [],
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "sync_timeout",
                        "option_value": "-3",
                        "allowed_values": "a positive integer",
                    },
                ),
                (
                    severity.WARNING,
                    report_codes.INVALID_OPTION_VALUE,
                    {
                        "option_name": "timeout",
                        "option_value": "-2",
                        "allowed_values": "a positive integer",
                    },
                )
            ]
        )

    def test_heuristics_bad_options(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {},
                {
                    "mode": "bad mode",
                    "timeout": "-5",
                    "sync_timeout": "-15",
                    "interval": "-30",
                    "exec_ls.bad": "test -f /tmp/test",
                    "exec_ls:bad": "test -f /tmp/test",
                    "exec_ls bad": "test -f /tmp/test",
                    "exec_ls{bad": "test -f /tmp/test",
                    "exec_ls}bad": "test -f /tmp/test",
                    "exec_ls#bad": "test -f /tmp/test",
                },
                self.node_ids
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    force_code=report_codes.FORCE_OPTIONS,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=[
                        "exec_ls bad", "exec_ls#bad", "exec_ls.bad",
                        "exec_ls:bad", "exec_ls{bad", "exec_ls}bad",
                    ],
                    option_type="heuristics",
                    allowed_description=(
                        "exec_NAME cannot contain '.:{}#' and whitespace "
                        "characters"
                    )
                )
            ]
        )

    def test_heuristics_bad_options_forced(self):
        assert_report_item_list_equal(
            config_validators.update_quorum_device(
                "net",
                {},
                {},
                {
                    "interval": "-30",
                    "mode": "bad mode",
                    "sync_timeout": "-15",
                    "timeout": "-5",
                },
                self.node_ids,
                force_options=True
            ),
            [
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="mode",
                    option_value="bad mode",
                    allowed_values=("off", "on", "sync")
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="interval",
                    option_value="-30",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="sync_timeout",
                    option_value="-15",
                    allowed_values="a positive integer"
                ),
                fixture.warn(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="timeout",
                    option_value="-5",
                    allowed_values="a positive integer"
                ),
            ]
        )
