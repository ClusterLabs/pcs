from pcs.common.reports import codes as report_codes

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal

forbidden_characters_kwargs = dict(
    allowed_values=None,
    cannot_be_empty=False,
    forbidden_characters=r"{}\n\r",
)


class TransportKnetBase:
    fixture_error_prerequisite = fixture.error(
        report_codes.PREREQUISITE_OPTION_MUST_BE_ENABLED_AS_WELL,
        option_name="cipher",
        option_type="crypto",
        prerequisite_name="hash",
        prerequisite_type="crypto",
    )

    def call_function(
        self,
        generic_options,
        compression_options,
        crypto_options,
        current_crypto_options=None,
    ):
        raise NotImplementedError()

    def test_no_options(self):
        assert_report_item_list_equal(self.call_function({}, {}, {}), [])

    def test_all_valid(self):
        assert_report_item_list_equal(
            self.call_function(
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
                },
            ),
            [],
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            self.call_function(
                {
                    "ip_version": "ipv5",
                    "knet_pmtud_interval": "a minute",
                    "link_mode": "random",
                },
                {
                    "level": "maximum",
                    "threshold": "reasonable",
                },
                {
                    "cipher": "strongest",
                    "hash": "fastest",
                    "model": "best",
                },
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv5",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6", "ipv4-6", "ipv6-4"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="a minute",
                    option_name="knet_pmtud_interval",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="random",
                    option_name="link_mode",
                    allowed_values=("active", "passive", "rr"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="maximum",
                    option_name="level",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="reasonable",
                    option_name="threshold",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="strongest",
                    option_name="cipher",
                    allowed_values=("none", "aes256", "aes192", "aes128"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="fastest",
                    option_name="hash",
                    allowed_values=(
                        "none",
                        "md5",
                        "sha1",
                        "sha256",
                        "sha384",
                        "sha512",
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="best",
                    option_name="model",
                    allowed_values=("nss", "openssl"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_invalid_options(self):
        assert_report_item_list_equal(
            self.call_function(
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
                },
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
            ],
        )

    def test_forbidden_characters(self):
        assert_report_item_list_equal(
            self.call_function(
                {
                    "ip_version": "ipv4\r",
                    "knet_pmtud_interval": "\n1234",
                    "link_mode": "a{ctive",
                    "op:.tionA": "va}l{ueA",
                },
                {
                    "level": "}5",
                    "model": "zl\rib",
                    "threshold": "1\n234",
                    "op:.tionB": "va}l{ueB",
                },
                {
                    "cipher": "aes{256",
                    "hash": "sha256}",
                    "model": "nss\n",
                    "op:.tionC": "va}l{ueC",
                },
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tionA"],
                    option_type="knet transport",
                    allowed=["ip_version", "knet_pmtud_interval", "link_mode"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv4\r",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6", "ipv4-6", "ipv6-4"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\n1234",
                    option_name="knet_pmtud_interval",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="a{ctive",
                    option_name="link_mode",
                    allowed_values=("active", "passive", "rr"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tionA"],
                    option_type="knet transport",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv4\r",
                    option_name="ip_version",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\n1234",
                    option_name="knet_pmtud_interval",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="a{ctive",
                    option_name="link_mode",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ueA",
                    option_name="op:.tionA",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tionB"],
                    option_type="compression",
                    allowed=["level", "model", "threshold"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}5",
                    option_name="level",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="1\n234",
                    option_name="threshold",
                    allowed_values="a non-negative integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tionB"],
                    option_type="compression",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}5",
                    option_name="level",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="zl\rib",
                    option_name="model",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="1\n234",
                    option_name="threshold",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ueB",
                    option_name="op:.tionB",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tionC"],
                    option_type="crypto",
                    allowed=["cipher", "hash", "model"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="aes{256",
                    option_name="cipher",
                    allowed_values=("none", "aes256", "aes192", "aes128"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="sha256}",
                    option_name="hash",
                    allowed_values=(
                        "none",
                        "md5",
                        "sha1",
                        "sha256",
                        "sha384",
                        "sha512",
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="nss\n",
                    option_name="model",
                    allowed_values=("nss", "openssl"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tionC"],
                    option_type="crypto",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="aes{256",
                    option_name="cipher",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="sha256}",
                    option_name="hash",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="nss\n",
                    option_name="model",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ueC",
                    option_name="op:.tionC",
                    **forbidden_characters_kwargs,
                ),
            ],
        )

    def test_crypto_disabled(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {
                    "cipher": "none",
                    "hash": "none",
                },
            ),
            [],
        )

    def test_crypto_enabled_cipher_disabled_hash(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {
                    "cipher": "aes256",
                    "hash": "none",
                },
            ),
            [self.fixture_error_prerequisite],
        )

    def test_crypto_enabled_cipher_default_hash(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {
                    "cipher": "aes256",
                },
            ),
            [self.fixture_error_prerequisite],
        )

    def test_crypto_disabled_cipher_default_hash(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {
                    "cipher": "none",
                },
            ),
            [],
        )

    def test_crypto_enabled_hash_disabled_cipher(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {
                    "cipher": "none",
                    "hash": "sha256",
                },
            ),
            [],
        )

    def test_crypto_enabled_hash_default_cipher(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {
                    "hash": "sha256",
                },
            ),
            [],
        )

    def test_crypto_disabled_hash_default_cipher(self):
        assert_report_item_list_equal(
            self.call_function(
                {},
                {},
                {
                    "hash": "none",
                },
            ),
            [],
        )


class TransportUdpBase:
    def call_function(
        self, generic_options, compression_options, crypto_options
    ):
        raise NotImplementedError()

    def test_no_options(self):
        assert_report_item_list_equal(self.call_function({}, {}, {}), [])

    def test_all_valid(self):
        assert_report_item_list_equal(
            self.call_function(
                {
                    "ip_version": "ipv4",
                    "netmtu": "1234",
                },
                {},
                {},
            ),
            [],
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            self.call_function(
                {
                    "ip_version": "ipv5",
                    "netmtu": "-5",
                },
                {},
                {},
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="ipv5",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6", "ipv4-6", "ipv6-4"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="-5",
                    option_name="netmtu",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ],
        )

    def test_invalid_option(self):
        assert_report_item_list_equal(
            self.call_function(
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
                },
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
                    required_transports=["knet"],
                ),
                fixture.error(
                    report_codes.COROSYNC_TRANSPORT_UNSUPPORTED_OPTIONS,
                    option_type="crypto",
                    actual_transport="udp/udpu",
                    required_transports=["knet"],
                ),
            ],
        )

    def test_forbidden_characters(self):
        assert_report_item_list_equal(
            self.call_function(
                {
                    "ip_version": "}ipv4{",
                    "netmtu": "\r1234\n",
                    "op:.tion": "va}l{ue",
                },
                {},
                {},
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="udp/udpu transport",
                    allowed=["ip_version", "netmtu"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}ipv4{",
                    option_name="ip_version",
                    allowed_values=("ipv4", "ipv6", "ipv4-6", "ipv6-4"),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\r1234\n",
                    option_name="netmtu",
                    allowed_values="a positive integer",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="udp/udpu transport",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="}ipv4{",
                    option_name="ip_version",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="\r1234\n",
                    option_name="netmtu",
                    **forbidden_characters_kwargs,
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ue",
                    option_name="op:.tion",
                    **forbidden_characters_kwargs,
                ),
            ],
        )


class TotemBase:
    allowed_options = [
        "block_unlisted_ips",
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

    def call_function(self, options):
        raise NotImplementedError()

    def test_no_options(self):
        # pylint: disable=no-self-use
        assert_report_item_list_equal(self.call_function({}), [])

    def test_all_valid(self):
        assert_report_item_list_equal(
            self.call_function(
                {
                    name: ("yes" if name == "block_unlisted_ips" else value)
                    for value, name in enumerate(self.allowed_options)
                }
            ),
            [],
        )

    def test_invalid_all_values(self):
        assert_report_item_list_equal(
            self.call_function(dict.fromkeys(self.allowed_options, "x")),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="x",
                    option_name=name,
                    allowed_values=(
                        ["yes", "no"]
                        if name == "block_unlisted_ips"
                        else "a non-negative integer"
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
                for name in self.allowed_options
            ],
        )

    def test_invalid_options(self):
        assert_report_item_list_equal(
            self.call_function(
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
            ],
        )

    def test_forbidden_characters(self):
        forbidden = "{}\r\n"
        options = {
            name: f"{value}{forbidden[value % len(forbidden)]}"
            for value, name in enumerate(self.allowed_options)
        }
        all_options = dict(options)
        all_options["op:.tion"] = "va}l{ue"

        assert_report_item_list_equal(
            self.call_function(all_options),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value=value,
                    option_name=name,
                    **forbidden_characters_kwargs,
                )
                for name, value in options.items()
            ]
            + [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value=value,
                    option_name=name,
                    allowed_values=(
                        ["yes", "no"]
                        if name == "block_unlisted_ips"
                        else "a non-negative integer"
                    ),
                    cannot_be_empty=False,
                    forbidden_characters=None,
                )
                for name, value in options.items()
            ]
            + [
                fixture.error(
                    report_codes.INVALID_USERDEFINED_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="totem",
                    allowed_characters="a-z A-Z 0-9 /_-",
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["op:.tion"],
                    option_type="totem",
                    allowed=self.allowed_options,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="va}l{ue",
                    option_name="op:.tion",
                    **forbidden_characters_kwargs,
                ),
            ],
        )
