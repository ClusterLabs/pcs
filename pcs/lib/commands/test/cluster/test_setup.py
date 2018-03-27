from unittest import mock, TestCase

from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.custom_mock import patch_getaddrinfo

from pcs import settings
from pcs.common import report_codes
from pcs.lib.commands import cluster
from pcs.lib.corosync import constants

DEFAULT_TRANSPORT_TYPE = "knet"
RANDOM_KEY = "I'm so random!".encode()
CLUSTER_NAME = "myCluster"
NODE_LIST = ["node1", "node2", "node3"]
COROSYNC_NODE_LIST = {node: [node] for node in NODE_LIST}
SERVICE_LIST = [
    "pacemaker", "pacemaker_remote", "corosync", "pcsd", "sbd", "qdevice",
    "booth",
]
RING_TEMPLATE = "ring{i}_addr: {addr}"
NODE_TEMPLATE = """\
    node {{
        {ring_list}
        name: {name}
        nodeid: {id}
    }}
"""
COROSYNC_CONF_TEMPLATE = """\
totem {{
    version: 2
    cluster_name: {cluster_name}
    transport: {transport_type}\
{totem_options}{transport_options}{compression_options}{crypto_options}\
{interface_list}
}}

nodelist {{
{node_list}}}

quorum {{
    provider: corosync_votequorum{quorum_options}
}}

logging {{
    to_logfile: yes
    logfile: {logfile}
    to_syslog: yes
}}
"""

OPTION_TEMPLATE = """
    {option}: {value}\
"""

INTERFACE_TEMPLATE = """

    interface {{{option_list}
    }}\
"""

INTERFACE_OPTION_TEMPLATE = """
        {option}: {value}\
"""

def flat_list(list_of_lists):
    return [item for item_list in list_of_lists for item in item_list]

def ring_list_fixture(addr_list):
    prefix = " " * 8
    return f"\n{prefix}".join(
        [f"ring{i}_addr: {addr}" for i, addr in enumerate(addr_list)]
    )

def add_key_prefix(prefix, options):
    options = options or {}
    return {f"{prefix}{key}": value for key, value in options.items()}

def options_fixture(options):
    options = options or {}
    return "".join([
        OPTION_TEMPLATE.format(option=o, value=v)
        for o,v in sorted(options.items())
    ])

def corosync_conf_fixture(
    node_addrs, transport_type=DEFAULT_TRANSPORT_TYPE, link_list=None,
    links_numbers=None, quorum_options=None, totem_options=None,
    transport_options=None, compression_options=None, crypto_options=None,
):
    interface_list = ""
    if link_list:
        link_list = [dict(link) for link in link_list]
        links_numbers = links_numbers if links_numbers else list(
            range(constants.LINKS_KNET_MAX)
        )
        for i, link in enumerate(link_list):
            link["linknumber"] = links_numbers[i]
        interface_list = "".join([
            INTERFACE_TEMPLATE.format(
                option_list="".join([
                    INTERFACE_OPTION_TEMPLATE.format(option=o, value=v)
                    for o, v in sorted(link.items())
                ])
            ) for link in sorted(
                link_list, key=lambda item: item["linknumber"]
            )
        ])
    return COROSYNC_CONF_TEMPLATE.format(
        cluster_name=CLUSTER_NAME,
        node_list="\n".join([
            NODE_TEMPLATE.format(
                name=node,
                id=i,
                ring_list=ring_list_fixture(addr_list),
            ) for i, (node, addr_list) in enumerate(node_addrs.items(), start=1)
        ]),
        logfile=settings.corosync_log_file,
        transport_type=transport_type,
        interface_list=interface_list,
        quorum_options=options_fixture(quorum_options),
        transport_options=options_fixture(transport_options),
        totem_options=options_fixture(totem_options),
        compression_options=options_fixture(
            add_key_prefix("knet_compression_", compression_options)
        ),
        crypto_options=options_fixture(
            add_key_prefix("crypto_", crypto_options)
        ),
    )

def config_succes_minimal_fixture(config, corosync_conf=None):
    services_status = {
        service: dict(
            installed=True, enabled=False, running=False, version="1.0",
        ) for service in SERVICE_LIST
    }
    (config
        .http.host.get_host_info(
            NODE_LIST,
            output_data=dict(
                services=services_status,
                cluster_configuration_exists=False,
            ),
        )
        .http.host.cluster_destroy(NODE_LIST)
        .http.host.update_known_hosts(NODE_LIST, to_add=NODE_LIST)
        .http.files.put_files(
            NODE_LIST,
            pcmk_authkey=RANDOM_KEY,
            corosync_authkey=RANDOM_KEY,
        )
        .http.files.remove_files(NODE_LIST, pcsd_settings=True)
        .http.files.put_files(
            NODE_LIST,
            corosync_conf=corosync_conf,
            name="distribute_corosync_conf",
        )
    )

def reports_success_minimal_fixture():
    auth_file_list = ["corosync authkey", "pacemaker_remote authkey"]
    pcsd_settings_file = "pcsd settings"
    corosync_conf_file = "corosync.conf"
    return (
        [
            fixture.info(
                report_codes.CLUSTER_DESTROY_STARTED,
                host_name_list=NODE_LIST,
            ),
        ]
        +
        [
            fixture.info(
                report_codes.CLUSTER_DESTROY_SUCCESS,
                node=node
            ) for node in NODE_LIST
        ]
        +
        [
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                file_list=auth_file_list,
                node_list=NODE_LIST,
                description="",
            )
        ]
        +
        [
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                node=node,
                file_description=file,
            ) for node in NODE_LIST for file in auth_file_list
        ]
        +
        [
            fixture.info(
                report_codes.FILES_REMOVE_FROM_NODE_STARTED,
                file_list=[pcsd_settings_file],
                node_list=NODE_LIST,
                description="",
            )
        ]
        +
        [
            fixture.info(
                report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
                node=node,
                file_description=pcsd_settings_file,
            ) for node in NODE_LIST
        ]
        +
        [
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                file_list=[corosync_conf_file],
                node_list=NODE_LIST,
                description="",
            )
        ]
        +
        [
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description=corosync_conf_file,
                node=node,
            ) for node in NODE_LIST
        ]
        +
        [
            fixture.info(report_codes.CLUSTER_SETUP_SUCCESS)
        ]
    )


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
class SetupSuccessMinimal(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(NODE_LIST + ["random_node"])
        patch_getaddrinfo(self, NODE_LIST)
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(COROSYNC_NODE_LIST),
        )

    def test_minimal(self):
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in NODE_LIST],
            transport_type=DEFAULT_TRANSPORT_TYPE,
        )
        self.env_assist.assert_reports(reports_success_minimal_fixture())

    def test_enable(self):
        self.config.http.host.enable_cluster(NODE_LIST)
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in NODE_LIST],
            transport_type=DEFAULT_TRANSPORT_TYPE,
            enable=True,
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()
            +
            [fixture.info(report_codes.CLUSTER_ENABLE_STARTED)]
            +
            [
                fixture.info(report_codes.CLUSTER_ENABLE_SUCCESS, node=node)
                for node in NODE_LIST
            ]
        )

    def test_start(self):
        self.config.http.host.start_cluster(NODE_LIST)
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in NODE_LIST],
            transport_type=DEFAULT_TRANSPORT_TYPE,
            start=True,
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()
            +
            [fixture.info(report_codes.CLUSTER_START_STARTED)]
        )

    @mock.patch("time.sleep", lambda secs: None)
    def test_start_wait(self):
        (self.config
            .http.host.start_cluster(NODE_LIST)
            .http.host.check_pacemaker_started(NODE_LIST)
        )
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in NODE_LIST],
            transport_type=DEFAULT_TRANSPORT_TYPE,
            start=True,
            wait=True,
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()
            +
            [
                fixture.info(report_codes.CLUSTER_START_STARTED),
                fixture.info(
                    report_codes.WAIT_FOR_NODE_STARTUP_STARTED,
                    node_name_list=NODE_LIST,
                ),
            ]
            +
            [
                fixture.info(
                    report_codes.CLUSTER_START_SUCCESS,
                    node=node,
                ) for node in NODE_LIST
            ]
        )

    def test_enable_start(self):
        (self.config
            .http.host.enable_cluster(NODE_LIST)
            .http.host.start_cluster(NODE_LIST)
        )
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in NODE_LIST],
            transport_type=DEFAULT_TRANSPORT_TYPE,
            enable=True,
            start=True,
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()
            +
            [fixture.info(report_codes.CLUSTER_ENABLE_STARTED)]
            +
            [
                fixture.info(report_codes.CLUSTER_ENABLE_SUCCESS, node=node)
                for node in NODE_LIST
            ]
            +
            [fixture.info(report_codes.CLUSTER_START_STARTED)]
        )

    @mock.patch("time.sleep", lambda secs: None)
    def test_enable_start_wait(self):
        (self.config
            .http.host.enable_cluster(NODE_LIST)
            .http.host.start_cluster(NODE_LIST)
            .http.host.check_pacemaker_started(NODE_LIST)
        )
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in NODE_LIST],
            transport_type=DEFAULT_TRANSPORT_TYPE,
            enable=True,
            start=True,
            wait=True,
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()
            +
            [fixture.info(report_codes.CLUSTER_ENABLE_STARTED)]
            +
            [
                fixture.info(report_codes.CLUSTER_ENABLE_SUCCESS, node=node)
                for node in NODE_LIST
            ]
            +
            [
                fixture.info(report_codes.CLUSTER_START_STARTED),
                fixture.info(
                    report_codes.WAIT_FOR_NODE_STARTUP_STARTED,
                    node_name_list=NODE_LIST,
                ),
            ]
            +
            [
                fixture.info(
                    report_codes.CLUSTER_START_SUCCESS,
                    node=node,
                ) for node in NODE_LIST
            ]
        )


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
class Validation(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3", "node4"])
        self.resolvable_hosts = patch_getaddrinfo(self, [])
        self.services_status_ok = {
            service: {
                "installed": True,
                "enabled": False,
                "running": False,
                "version": "1.0",
            } for service in SERVICE_LIST
        }

    def test_default_node_addrs(self):
        (self.config
            .http.host.get_host_info(
                ["node1", "node2", "node3", "node4"],
                output_data={
                    "services": self.services_status_ok,
                    "cluster_configuration_exists": False,
                }
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [
                    # no change, addrs defined
                    {"name": "node1", "addrs": ["addr1"]},
                    # no change, addrs defined even though empty
                    {"name": "node2", "addrs": []},
                    # use the name as an address
                    {"name": "node3", "addrs": None},
                    # use the name as an address
                    {"name": "node4"},
                    # no name defined, keep addrs undefined
                    {"addrs": None},
                ],
                transport_type="knet"
            ),
            [
                # no addrs defined
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=8,
                    node_name="node2",
                    node_id=2
                ),
                # no addrs and no name defined
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=8,
                    node_name=None,
                    node_id=5
                ),
                fixture.error(
                    report_codes.REQUIRED_OPTION_IS_MISSING,
                    option_names=["name"],
                    option_type="node 5"
                ),
                # we use this to verify what addrs have been used
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addr1", "node3", "node4"]
                )
            ]
        )

    def test_corosync_validator_basics(self):
        # The validators have their own tests. In here, we are only concerned
        # about calling the validators so we test that all provided options
        # have been validated.
        self.config.http.host.get_host_info([])

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                "",
                [],
                transport_type="tcp"
            ),
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="",
                    option_name="cluster name",
                    allowed_values="a non-empty string"
                ),
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="tcp",
                    option_name="transport",
                    allowed_values=("knet", "udp", "udpu")
                ),
                fixture.error(
                    report_codes.COROSYNC_NODES_MISSING
                )
            ]
        )

    def test_unresolvable_addrs(self):
        (self.config
            .http.host.get_host_info(
                # This is where pcs connects to, it has no relation to the
                # nodelist passed to cluster.setup - that holds addresses for
                # corosync.
                ["node1", "node2", "node3"],
                output_data={
                    "services": self.services_status_ok,
                    "cluster_configuration_exists": False,
                }
            )
        )
        self.resolvable_hosts.extend(["addr1", "addr3"])

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [
                    {"name": "node1", "addrs": ["addr1"]},
                    {"name": "node2", "addrs": ["addr2"]},
                    {"name": "node3", "addrs": ["addr3"]},
                ],
                transport_type="knet"
            ),
            [
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addr2"]
                )
            ]
        )

    def test_unresolvable_addrs_forced(self):
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(
                {"node1": ["addr1"], "node2": ["addr2"], "node3": ["addr3"]}
            ),
        )
        self.resolvable_hosts.extend(["addr1", "addr3"])

        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [
                {"name": "node1", "addrs": ["addr1"]},
                {"name": "node2", "addrs": ["addr2"]},
                {"name": "node3", "addrs": ["addr3"]},
            ],
            transport_type="knet",
            force_unresolvable=True
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addr2"]
                )
            ]
            +
            reports_success_minimal_fixture()
        )



TOTEM_OPTIONS = dict(
    consensus="0",
    downcheck="1",
    fail_recv_const="2",
    heartbeat_failures_allowed="3",
    hold="4",
    join="5",
    max_messages="6",
    max_network_delay="7",
    merge="8",
    miss_count_const="9",
    send_join="10",
    seqno_unchanged_const="11",
    token="12",
    token_coefficient="13",
    token_retransmit="14",
    token_retransmits_before_loss_const="15",
    window_size="16",
)

QUORUM_OPTIONS = dict(
    last_man_standing="1",
    last_man_standing_window="10",
)


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
class TransportKnetSuccess(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(NODE_LIST + ["random_node"])
        self.transport_type = "knet"
        self.resolvable_hosts = patch_getaddrinfo(self, [])

    def test_basic(self):
        node_addrs = {
            node: [f"{node}.addr{i}" for i in range(constants.LINKS_KNET_MAX)]
            for node in NODE_LIST
        }
        self.resolvable_hosts.extend(set(flat_list(node_addrs.values())))
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(
                node_addrs,
                transport_type=self.transport_type
            ),
        )

        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [
                dict(
                    name=node,
                    addrs=addrs,
                ) for node, addrs in node_addrs.items()
            ],
            transport_type=self.transport_type,
        )
        self.env_assist.assert_reports(reports_success_minimal_fixture())

    def test_all_options(self):
        node_addrs = {
            node: [f"{node}.addr{i}" for i in range(constants.LINKS_KNET_MAX)]
            for node in NODE_LIST
        }
        self.resolvable_hosts.extend(set(flat_list(node_addrs.values())))
        link_list = [
            dict(
                linknumber="1",
                ip_version="ipv4",
                link_priority="100",
                mcastport="12345",
                ping_interval="1",
                ping_precision="2",
                ping_timeout="3",
                pong_count="4",
                transport="sctp",
            ),
            dict(ip_version="ipv6"),
            dict(
                linknumber="7",
                transport="udp",
            ),
            dict(
                linknumber="3",
                link_priority="20",
            ),
            dict(ip_version="ipv4"),
            dict(transport="sctp"),
        ]
        links_linknumber = [1, 0, 7, 3, 2, 4]
        transport_options = dict(
            ip_version="ipv4",
            knet_pmtud_interval="0",
            link_mode="passive"
        )
        compression_options = dict(
            level="2",
            model="zlib",
            threshold="10",
        )
        crypto_options = dict(
            cipher="3des",
            hash="sha512",
            model="openssl",
        )
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(
                node_addrs,
                transport_type=self.transport_type,
                link_list=link_list,
                links_numbers=links_linknumber,
                quorum_options=QUORUM_OPTIONS,
                transport_options=transport_options,
                totem_options=TOTEM_OPTIONS,
                compression_options=compression_options,
                crypto_options=crypto_options,
            ),
        )

        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [
                dict(
                    name=node,
                    addrs=addrs,
                ) for node, addrs in node_addrs.items()
            ],
            transport_type=self.transport_type,
            transport_options=transport_options,
            link_list=link_list,
            compression_options=compression_options,
            crypto_options=crypto_options,
            totem_options=TOTEM_OPTIONS,
            quorum_options=QUORUM_OPTIONS,
        )
        self.env_assist.assert_reports(reports_success_minimal_fixture())


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
class TransportUdpSuccess(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(NODE_LIST + ["random_node"])
        self.transport_type = "udp"
        self.resolvable_hosts = patch_getaddrinfo(self, [])

    def test_basic(self):
        node_addrs = {node: [f"{node}.addr"] for node in NODE_LIST}
        self.resolvable_hosts.extend(set(flat_list(node_addrs.values())))
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(
                node_addrs,
                transport_type=self.transport_type
            ),
        )

        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [
                dict(
                    name=node,
                    addrs=addrs,
                ) for node, addrs in node_addrs.items()
            ],
            transport_type=self.transport_type,
        )
        self.env_assist.assert_reports(reports_success_minimal_fixture())

    def test_all_options(self):
        node_addrs = {node: [f"{node}.addr"] for node in NODE_LIST}
        self.resolvable_hosts.extend(set(flat_list(node_addrs.values())))
        link_list = [dict(
            bindnetaddr="127.0.0.1",
            mcastaddr="127.0.0.1",
            mcastport="12345",
            ttl="255",
        )]
        transport_options = dict(
            ip_version="ipv6",
            netmtu="1"
        )
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(
                node_addrs,
                transport_type=self.transport_type,
                link_list=link_list,
                quorum_options=QUORUM_OPTIONS,
                transport_options=transport_options,
                totem_options=TOTEM_OPTIONS,
            ),
        )

        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [
                dict(
                    name=node,
                    addrs=addrs,
                ) for node, addrs in node_addrs.items()
            ],
            transport_type=self.transport_type,
            transport_options=transport_options,
            link_list=link_list,
            totem_options=TOTEM_OPTIONS,
            quorum_options=QUORUM_OPTIONS,
        )
        self.env_assist.assert_reports(reports_success_minimal_fixture())
