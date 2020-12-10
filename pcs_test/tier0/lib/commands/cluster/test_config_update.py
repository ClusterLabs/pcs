from textwrap import dedent
from unittest import TestCase

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from pcs.common.corosync_conf import (
    CorosyncConfDto,
    CorosyncNodeAddressDto,
    CorosyncNodeDto,
    CorosyncQuorumDeviceSettingsDto,
)
from pcs.common.reports import codes as report_codes
from pcs.common.types import CorosyncTransportType
from pcs.lib.commands import cluster
from pcs.lib.corosync.constants import (
    TOTEM_OPTIONS,
    TRANSPORT_KNET_CRYPTO_OPTIONS,
    TRANSPORT_KNET_COMPRESSION_OPTIONS,
    TRANSPORT_KNET_GENERIC_OPTIONS,
)

ALLOWED_COMPRESSION_OPTIONS = list(TRANSPORT_KNET_COMPRESSION_OPTIONS)

ALLOWED_CRYPTO_OPTIONS = list(TRANSPORT_KNET_CRYPTO_OPTIONS)

ALLOWED_TOTEM_OPTIONS = list(TOTEM_OPTIONS)

ALLOWED_KNET_TRANSPORT_OPTIONS = list(TRANSPORT_KNET_GENERIC_OPTIONS)

TRANSPORT_OPTIONS = {
    "ip_version": "ipv4",
    "knet_pmtud_interval": "1234",
    "link_mode": "active",
}

COMPRESSION_OPTIONS = {"level": "5", "model": "zlib", "threshold": "1234"}

CRYPTO_OPTIONS = {"cipher": "aes256", "hash": "sha256", "model": "nss"}

TOTEM_OPTIONS = {opt: str(num) for num, opt in enumerate(ALLOWED_TOTEM_OPTIONS)}

TOTEM_TEMPLATE = """\
totem {{
    transport: {transport_type}\
{totem_options}{transport_options}{compression_options}{crypto_options}
}}
"""


def fixture_totem(
    transport_type="knet",
    transport_options=None,
    compression_options=None,
    crypto_options=None,
    totem_options=None,
):
    def options_fixture(options, prefix=""):
        options = options or {}
        template = "\n    {prefix}{option}: {value}"
        return "".join(
            [
                template.format(prefix=prefix, option=o, value=v)
                for o, v in sorted(options.items())
            ]
        )

    return TOTEM_TEMPLATE.format(
        transport_type=transport_type,
        transport_options=options_fixture(transport_options),
        compression_options=options_fixture(
            compression_options, prefix="knet_compression_"
        ),
        crypto_options=options_fixture(crypto_options, prefix="crypto_"),
        totem_options=options_fixture(totem_options),
    )


class CheckLiveMixin:
    # pylint: disable=invalid-name
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def get_lib_command(self):
        raise NotImplementedError

    def assert_live_required(self, forbidden_options):
        self.env_assist.assert_raise_library_error(
            self.get_lib_command(),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=forbidden_options,
                )
            ],
            expected_in_processor=False,
        )

    def test_mock_corosync(self):
        self.config.env.set_corosync_conf_data("")
        self.assert_live_required(["COROSYNC_CONF"])

    def test_mock_cib(self):
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required(["CIB"])

    def test_mock_cib_corosync(self):
        self.config.env.set_corosync_conf_data("")
        self.config.env.set_cib_data("<cib />")
        self.assert_live_required(["CIB", "COROSYNC_CONF"])


class CheckLiveUpdateConfig(CheckLiveMixin, TestCase):
    def get_lib_command(self):
        return lambda: cluster.config_update(
            self.env_assist.get_env(), {}, {}, {}, {}
        )


class CheckLiveUpdateConfigLocal(CheckLiveMixin, TestCase):
    def get_lib_command(self):
        return lambda: cluster.config_update_local(
            self.env_assist.get_env(), b"", {}, {}, {}, {}
        )


class UpdateConfig(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_no_changed_options(self):
        self.config.corosync_conf.load_content(fixture_totem())
        self.config.env.push_corosync_conf(corosync_conf_text=fixture_totem())
        cluster.config_update(self.env_assist.get_env(), {}, {}, {}, {})
        self.env_assist.assert_reports([])

    def test_add_all_options(self):
        self.config.corosync_conf.load_content(fixture_totem())
        self.config.env.push_corosync_conf(
            corosync_conf_text=fixture_totem(
                transport_options=TRANSPORT_OPTIONS,
                compression_options=COMPRESSION_OPTIONS,
                crypto_options=CRYPTO_OPTIONS,
                totem_options=TOTEM_OPTIONS,
            ),
            need_stopped_cluster=True,
        )
        cluster.config_update(
            self.env_assist.get_env(),
            TRANSPORT_OPTIONS,
            COMPRESSION_OPTIONS,
            CRYPTO_OPTIONS,
            TOTEM_OPTIONS,
        )
        self.env_assist.assert_reports([])

    def _test_modify(self, transport_options, need_stopped_cluster):
        self.config.corosync_conf.load_content(
            fixture_totem(
                transport_options=TRANSPORT_OPTIONS,
                compression_options=COMPRESSION_OPTIONS,
                crypto_options=CRYPTO_OPTIONS,
                totem_options=TOTEM_OPTIONS,
            )
        )
        modified_transport_options = dict(TRANSPORT_OPTIONS)
        modified_transport_options.update(transport_options)
        modified_compression_options = {
            "level": "9",
            "model": "lz4",
            "threshold": "100",
        }
        modified_crypto_options = {
            "cipher": "aes128",
            "hash": "sha512",
            "model": "openssl",
        }
        modified_totem_options = {
            opt: val + "0" for opt, val in TOTEM_OPTIONS.items()
        }
        self.config.env.push_corosync_conf(
            corosync_conf_text=fixture_totem(
                transport_options=modified_transport_options,
                compression_options=modified_compression_options,
                crypto_options=modified_crypto_options,
                totem_options=modified_totem_options,
            ),
            need_stopped_cluster=need_stopped_cluster,
        )
        cluster.config_update(
            self.env_assist.get_env(),
            modified_transport_options,
            modified_compression_options,
            modified_crypto_options,
            modified_totem_options,
        )
        self.env_assist.assert_reports([])

    def test_modify_all_options(self):
        self._test_modify(
            {
                "ip_version": "ipv4-6",
                "link_mode": "passive",
                "knet_pmtud_interval": "1000",
            },
            need_stopped_cluster=True,
        )

    def test_modify_no_need_for_stopped_cluster(self):
        self._test_modify(
            {"link_mode": "passive", "knet_pmtud_interval": "1000"},
            need_stopped_cluster=False,
        )

    def test_remove_all_options(self):
        self.config.corosync_conf.load_content(
            fixture_totem(
                transport_options=TRANSPORT_OPTIONS,
                compression_options=COMPRESSION_OPTIONS,
                crypto_options=CRYPTO_OPTIONS,
                totem_options=TOTEM_OPTIONS,
            )
        )
        self.config.env.push_corosync_conf(
            corosync_conf_text=fixture_totem(), need_stopped_cluster=True,
        )
        cluster.config_update(
            self.env_assist.get_env(),
            {option: "" for option in ALLOWED_KNET_TRANSPORT_OPTIONS},
            {option: "" for option in ALLOWED_COMPRESSION_OPTIONS},
            {option: "" for option in ALLOWED_CRYPTO_OPTIONS},
            {option: "" for option in ALLOWED_TOTEM_OPTIONS},
        )
        self.env_assist.assert_reports([])

    def test_unknown_options_and_values(self):
        self.config.corosync_conf.load_content(fixture_totem())
        self.env_assist.assert_raise_library_error(
            lambda: cluster.config_update(
                self.env_assist.get_env(),
                {"unknown": "val", "ip_version": "4"},
                {"level": "high", "unknown": "val"},
                {"cipher": "strong", "unknown": "val"},
                {"unknown": "val", "downcheck": "check"},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    option_type="totem",
                    allowed=ALLOWED_TOTEM_OPTIONS,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="downcheck",
                    option_value="check",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    option_type="knet transport",
                    allowed=ALLOWED_KNET_TRANSPORT_OPTIONS,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="ip_version",
                    option_value="4",
                    allowed_values=("ipv4", "ipv6", "ipv4-6", "ipv6-4"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    option_type="compression",
                    allowed=ALLOWED_COMPRESSION_OPTIONS,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="level",
                    option_value="high",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    option_type="crypto",
                    allowed=ALLOWED_CRYPTO_OPTIONS,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="cipher",
                    option_value="strong",
                    allowed_values=("none", "aes256", "aes192", "aes128"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
                    option_name="cipher",
                    prerequisite_name="hash",
                    option_type="crypto",
                    prerequisite_type="crypto",
                ),
            ]
        )

    def test_unsupported_transport(self):
        self.config.corosync_conf.load_content(
            fixture_totem(transport_type="keynet")
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.config_update(
                self.env_assist.get_env(),
                {"unknown": "val", "ip_version": "4"},
                {"level": "high", "unknown": "val"},
                {"cipher": "strong", "unknown": "val"},
                {"unknown": "val", "downcheck": "check"},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["unknown"],
                    option_type="totem",
                    allowed=ALLOWED_TOTEM_OPTIONS,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.COROSYNC_CONFIG_UNSUPPORTED_TRANSPORT,
                    actual_transport="keynet",
                    supported_transport_types=["knet", "udp", "udpu"],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="downcheck",
                    option_value="check",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )

    def test_udp_transport_unsupported_options(self):
        self.config.corosync_conf.load_content(
            fixture_totem(transport_type="udp")
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.config_update(
                self.env_assist.get_env(),
                {"knet_pmtud_interval": "interval"},
                {"level": "high", "unknown": "val"},
                {"cipher": "strong", "unknown": "val"},
                {"downcheck": "check"},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="downcheck",
                    option_value="check",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["knet_pmtud_interval"],
                    option_type="udp/udpu transport",
                    allowed=["ip_version", "netmtu"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
                    option_type="compression",
                    actual_transport="udp/udpu",
                    required_transports=["knet"],
                ),
                fixture.error(
                    report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
                    option_type="crypto",
                    actual_transport="udp/udpu",
                    required_transports=["knet"],
                ),
            ]
        )


class UpdateConfigLocal(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_empty_config_no_change(self):
        self.assertEqual(
            cluster.config_update_local(
                self.env_assist.get_env(), b"", {}, {}, {}, {}
            ),
            b"",
        )

    def test_invalid_custom_corosync_conf(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.config_update_local(
                self.env_assist.get_env(),
                b"totem {\n    option.name: value\n}",
                {},
                {},
                {},
                {},
            ),
            [
                fixture.error(
                    report_codes.COROSYNC_CONFIG_CANNOT_SAVE_INVALID_NAMES_VALUES,
                    section_name_list=[],
                    attribute_name_list=["totem.option.name"],
                    attribute_value_pairs=[],
                )
            ],
            expected_in_processor=False,
        )

    def test_add_modify_remove_options(self):
        before = fixture_totem(
            transport_options={
                "ip_version": "ipv4",
                "knet_pmtud_interval": "10",
            },
            compression_options={"level": "9", "threshold": "100"},
            crypto_options={"cipher": "none", "model": "openssl"},
            totem_options={"token": "3000", "join": "50"},
        )
        after = dedent(
            """\
            totem {
                transport: knet
                token: 1000
                ip_version: ipv6
                knet_compression_level: 5
                crypto_cipher: aes128
                downcheck: 5
                link_mode: active
                knet_compression_model: zlib
                crypto_hash: sha256
            }
            """
        )
        self.assertEqual(
            cluster.config_update_local(
                self.env_assist.get_env(),
                before.encode(),
                {
                    "ip_version": "ipv6",
                    "link_mode": "active",
                    "knet_pmtud_interval": "",
                },
                {"level": "5", "model": "zlib", "threshold": ""},
                {"cipher": "aes128", "hash": "sha256", "model": ""},
                {"token": "1000", "downcheck": "5", "join": ""},
            ),
            after.encode(),
        )

    def test_some_validator_errors(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.config_update_local(
                self.env_assist.get_env(),
                fixture_totem(transport_type="udp").encode(),
                {"knet_pmtud_interval": "100"},
                {},
                {"cipher": "none", "hash": "none"},
                {"token": "notanumber"},
            ),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="token",
                    option_value="notanumber",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["knet_pmtud_interval"],
                    option_type="udp/udpu transport",
                    allowed=["ip_version", "netmtu"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
                    option_type="crypto",
                    actual_transport="udp/udpu",
                    required_transports=["knet"],
                ),
            ]
        )


class GetCorosyncConfStruct(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_unsupported_corosync_transport(self):
        self.config.corosync_conf.load_content(
            fixture_totem(transport_type="unknown")
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.get_corosync_conf_struct(self.env_assist.get_env()),
            [
                fixture.error(
                    report_codes.COROSYNC_CONFIG_UNSUPPORTED_TRANSPORT,
                    actual_transport="unknown",
                    supported_transport_types=["knet", "udp", "udpu"],
                ),
            ],
            expected_in_processor=False,
        )

    def test_empty_corosync_conf(self):
        self.config.corosync_conf.load_content("")
        self.assertEqual(
            CorosyncConfDto(
                cluster_name="",
                transport=CorosyncTransportType.KNET,
                totem_options={},
                transport_options={},
                compression_options={},
                crypto_options={},
                nodes=[],
                links_options={},
                quorum_options={},
                quorum_device=None,
            ),
            cluster.get_corosync_conf_struct(self.env_assist.get_env()),
        )

    def test_corosync_conf_with_qdevice(self):
        self.config.corosync_conf.load_content(
            dedent(
                """\
                totem {
                    version: 2
                    cluster_name: HACluster
                    transport: knet
                    ip_version: ipv4-6
                    link_mode: passive
                    knet_compression_level: 5
                    knet_compression_model: zlib
                    knet_compression_threshold: 100
                    crypto_cipher: aes256
                    crypto_hash: sha256
                    consensus: 3600
                    join: 50
                    token: 3000

                    interface {
                        linknumber: 0
                        knet_link_priority: 100
                        knet_ping_interval: 750
                        knet_ping_timeout: 1500
                        knet_transport: udp
                    }

                    interface {
                        linknumber: 1
                        knet_link_priority: 200
                        knet_ping_interval: 750
                        knet_ping_timeout: 1500
                        knet_transport: sctp
                    }
                }

                nodelist {
                    node {
                        ring0_addr: node1-addr
                        ring1_addr: 10.0.0.1
                        name: node1
                        nodeid: 1
                    }

                    node {
                        ring0_addr: node2-addr
                        ring1_addr: 10.0.0.2
                        name: node2
                        nodeid: 2
                    }
                }

                quorum {
                    provider: corosync_votequorum
                    two_node: 1
                    wait_for_all: 1
                    device {
                        model: net
                        sync_timeout: 5000
                        timeout: 5000
                        net {
                            algorithm: ffsplit
                            host: node-qdevice
                        }
                        heuristics {
                            mode: on
                            exec_ping: /usr/bin/ping -c 1 127.0.0.1
                        }
                    }
                }

                logging {
                    to_logfile: yes
                    logfile: /var/log/cluster/corosync.log
                    to_syslog: yes
                    timestamp: on
                }
                """
            )
        )
        self.assertEqual(
            CorosyncConfDto(
                cluster_name="HACluster",
                transport=CorosyncTransportType.KNET,
                totem_options={
                    "consensus": "3600",
                    "join": "50",
                    "token": "3000",
                },
                transport_options={
                    "ip_version": "ipv4-6",
                    "link_mode": "passive",
                },
                crypto_options={"cipher": "aes256", "hash": "sha256"},
                compression_options={
                    "level": "5",
                    "model": "zlib",
                    "threshold": "100",
                },
                nodes=[
                    CorosyncNodeDto(
                        name="node1",
                        nodeid="1",
                        addrs=[
                            CorosyncNodeAddressDto(
                                addr="node1-addr", link="0", type="FQDN",
                            ),
                            CorosyncNodeAddressDto(
                                addr="10.0.0.1", link="1", type="IPv4",
                            ),
                        ],
                    ),
                    CorosyncNodeDto(
                        name="node2",
                        nodeid="2",
                        addrs=[
                            CorosyncNodeAddressDto(
                                addr="node2-addr", link="0", type="FQDN",
                            ),
                            CorosyncNodeAddressDto(
                                addr="10.0.0.2", link="1", type="IPv4",
                            ),
                        ],
                    ),
                ],
                links_options={
                    "0": {
                        "linknumber": "0",
                        "link_priority": "100",
                        "ping_interval": "750",
                        "ping_timeout": "1500",
                        "transport": "udp",
                    },
                    "1": {
                        "linknumber": "1",
                        "link_priority": "200",
                        "ping_interval": "750",
                        "ping_timeout": "1500",
                        "transport": "sctp",
                    },
                },
                quorum_options={"wait_for_all": "1"},
                quorum_device=CorosyncQuorumDeviceSettingsDto(
                    model="net",
                    model_options={
                        "algorithm": "ffsplit",
                        "host": "node-qdevice",
                    },
                    generic_options={"sync_timeout": "5000", "timeout": "5000"},
                    heuristics_options={
                        "mode": "on",
                        "exec_ping": "/usr/bin/ping -c 1 127.0.0.1",
                    },
                ),
            ),
            cluster.get_corosync_conf_struct(self.env_assist.get_env()),
        )
