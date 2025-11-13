import json
from textwrap import dedent
from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster
from pcs.lib.corosync.constants import (
    TOTEM_OPTIONS,
    TRANSPORT_KNET_COMPRESSION_OPTIONS,
    TRANSPORT_KNET_CRYPTO_OPTIONS,
    TRANSPORT_KNET_GENERIC_OPTIONS,
)

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .common import fixture_totem

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
TOTEM_OPTIONS = {
    opt: ("yes" if opt == "block_unlisted_ips" else str(num))
    for num, opt in enumerate(ALLOWED_TOTEM_OPTIONS)
}


class CheckLiveMixin:
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
            opt: ("no" if opt == "block_unlisted_ips" else val + "0")
            for opt, val in TOTEM_OPTIONS.items()
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
            corosync_conf_text=fixture_totem(),
            need_stopped_cluster=True,
        )
        cluster.config_update(
            self.env_assist.get_env(),
            dict.fromkeys(ALLOWED_KNET_TRANSPORT_OPTIONS, ""),
            dict.fromkeys(ALLOWED_COMPRESSION_OPTIONS, ""),
            dict.fromkeys(ALLOWED_CRYPTO_OPTIONS, ""),
            dict.fromkeys(ALLOWED_TOTEM_OPTIONS, ""),
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

    def test_reload_failed(self):
        node_labels = ["node1", "node2"]
        self.config.env.set_known_nodes(node_labels)
        corosync_nodes = dedent("""
            nodelist {
                node {
                    ring0_addr: node1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2
                    name: node2
                    nodeid: 2
                }
            }
            """)

        self.config.corosync_conf.load_content(fixture_totem() + corosync_nodes)
        self.config.http.corosync.set_corosync_conf(
            fixture_totem(crypto_options={"hash": "md5"}) + corosync_nodes,
            node_labels=node_labels,
        )
        self.config.http.corosync.reload_corosync_conf(
            communication_list=[
                [
                    dict(
                        label="node1",
                        output=json.dumps(
                            dict(code="failed", message="Some error")
                        ),
                    )
                ],
                [
                    dict(
                        label="node2",
                        output=json.dumps(
                            dict(code="failed", message="Some error")
                        ),
                    ),
                ],
            ],
        )

        self.env_assist.assert_raise_library_error(
            # option which does not need corosync to be stopped
            lambda: cluster.config_update(
                self.env_assist.get_env(), {}, {}, {"hash": "md5"}, {}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED),
                fixture.info(
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE, node="node1"
                ),
                fixture.info(
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE, node="node2"
                ),
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node="node1",
                    reason="Some error",
                ),
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_RELOAD_ERROR,
                    node="node2",
                    reason="Some error",
                ),
                fixture.warn(
                    report_codes.COROSYNC_CONFIG_INVALID_PREVENTS_CLUSTER_JOIN
                ),
                fixture.error(
                    report_codes.UNABLE_TO_PERFORM_OPERATION_ON_ANY_NODE
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

    def test_corosyncconf_parse_error(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.config_update_local(
                self.env_assist.get_env(),
                b"this is not\na valid corosync.conf file\n",
                {},
                {},
                {},
                {},
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.PARSE_ERROR_COROSYNC_CONF_LINE_IS_NOT_SECTION_NOR_KEY_VALUE
                )
            ],
        )

    def test_add_modify_remove_options(self):
        before = fixture_totem(
            cluster_uuid=None,
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
