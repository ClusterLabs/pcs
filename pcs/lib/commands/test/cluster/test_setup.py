# pylint: disable=too-many-lines
import json
from copy import deepcopy

from unittest import mock, TestCase

from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.command_env.mock_node_communicator import (
    create_communication
)
from pcs.test.tools.custom_mock import patch_getaddrinfo

from pcs import settings
from pcs.common import report_codes
from pcs.common.host import Destination
from pcs.common.ssl import (
    dump_cert,
    dump_key,
    generate_cert,
    generate_key,
)
from pcs.lib.commands import cluster
from pcs.lib.corosync import constants

PCSD_SSL_KEY = generate_key()
PCSD_SSL_CERT = generate_cert(PCSD_SSL_KEY, "servername")
PCSD_SSL_KEY_DUMP = dump_key(PCSD_SSL_KEY)
PCSD_SSL_CERT_DUMP = dump_cert(PCSD_SSL_CERT)
RANDOM_KEY = "I'm so random!".encode()
CLUSTER_NAME = "myCluster"
NODE_LIST = ["node1", "node2", "node3"]
COMMAND_NODE_LIST = [dict(name=node, addrs=None) for node in NODE_LIST]
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
    timestamp: on
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

def options_fixture(options, template=OPTION_TEMPLATE):
    options = options or {}
    return "".join([
        template.format(option=o, value=v)
        for o, v in sorted(options.items())
    ])

def corosync_conf_fixture(
    node_addrs, transport_type="knet", link_list=None,
    links_numbers=None, quorum_options=None, totem_options=None,
    transport_options=None, compression_options=None, crypto_options=None,
):
    # pylint: disable=too-many-arguments, too-many-locals
    if transport_type == "knet" and not crypto_options:
        crypto_options = {
            "cipher": "aes256",
            "hash": "sha256",
        }
    interface_list = ""
    if link_list:
        knet_options = {
            "link_priority",
            "ping_interval",
            "ping_precision",
            "ping_timeout",
            "pong_count",
            "transport",
        }

        link_list = [dict(link) for link in link_list]
        links_numbers = links_numbers if links_numbers else list(
            range(constants.LINKS_KNET_MAX)
        )
        for i, link in enumerate(link_list):
            link["linknumber"] = links_numbers[i]
            link_translated = {}
            for name, value in link.items():
                if name in knet_options:
                    name = f"knet_{name}"
                link_translated[name] = value
            link_list[i] = link_translated

        interface_list = "".join([
            INTERFACE_TEMPLATE.format(
                option_list=options_fixture(link, INTERFACE_OPTION_TEMPLATE)
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

def config_succes_minimal_fixture(
    config, corosync_conf=None, node_labels=None, communication_list=None,
    known_hosts=None
):
    if node_labels is None and communication_list is None:
        node_labels = NODE_LIST
    if known_hosts is None:
        known_hosts = {
            name: {
                "dest_list": [
                    {"addr": name, "port": settings.pcsd_default_port}
                ]
            }
            for name in node_labels
        }
    services_status = {
        service: dict(
            installed=True, enabled=False, running=False, version="1.0",
        ) for service in SERVICE_LIST
    }
    (config
        .http.host.get_host_info(
            node_labels=node_labels,
            output_data=dict(
                services=services_status,
                cluster_configuration_exists=False,
            ),
            communication_list=communication_list,
        )
        .http.host.cluster_destroy(
            node_labels=node_labels,
            communication_list=communication_list,
        )
        .http.host.update_known_hosts(
            node_labels=node_labels,
            to_add=known_hosts,
            communication_list=communication_list,
        )
        .http.files.remove_files(
            node_labels=node_labels,
            pcsd_settings=True,
            communication_list=communication_list,
        )
        .http.files.put_files(
            node_labels=node_labels,
            pcmk_authkey=RANDOM_KEY,
            corosync_authkey=RANDOM_KEY,
            communication_list=communication_list,
        )
        .http.host.send_pcsd_cert(
            cert=PCSD_SSL_CERT_DUMP,
            key=PCSD_SSL_KEY_DUMP,
            node_labels=node_labels,
            communication_list=communication_list,
        )
        .http.files.put_files(
            node_labels=node_labels,
            corosync_conf=corosync_conf,
            name="distribute_corosync_conf",
            communication_list=communication_list,
        )
    )

def reports_success_minimal_fixture(
    node_list=None, using_known_hosts_addresses=True, keys_sync=True,
):
    node_list = node_list or NODE_LIST
    auth_file_list = ["corosync authkey", "pacemaker authkey"]
    pcsd_settings_file = "pcsd settings"
    corosync_conf_file = "corosync.conf"
    report_list = (
        [
            fixture.info(
                report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                host_name=node,
                address=node
            ) for node in node_list if using_known_hosts_addresses
        ]
        +
        [
            fixture.info(
                report_codes.CLUSTER_DESTROY_STARTED,
                host_name_list=node_list,
            ),
        ]
        +
        [
            fixture.info(
                report_codes.CLUSTER_DESTROY_SUCCESS,
                node=node
            ) for node in node_list
        ]
        +
        [
            fixture.info(
                report_codes.FILES_REMOVE_FROM_NODES_STARTED,
                file_list=[pcsd_settings_file],
                node_list=node_list,
            )
        ]
        +
        [
            fixture.info(
                report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
                node=node,
                file_description=pcsd_settings_file,
            ) for node in node_list
        ]
    )
    if keys_sync:
        report_list.extend(
            [
                fixture.info(
                    report_codes.FILES_DISTRIBUTION_STARTED,
                    file_list=auth_file_list,
                    node_list=node_list,
                )
            ]
            +
            [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    node=node,
                    file_description=file,
                ) for node in node_list for file in auth_file_list
            ]
            +
            [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_DISTRIBUTION_STARTED,
                    node_name_list=node_list,
                )
            ]
            +
            [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS,
                    node=node,
                ) for node in node_list
            ]
        )
    report_list.extend(
        [
            fixture.info(
                report_codes.FILES_DISTRIBUTION_STARTED,
                file_list=[corosync_conf_file],
                node_list=node_list,
            )
        ]
        +
        [
            fixture.info(
                report_codes.FILE_DISTRIBUTION_SUCCESS,
                file_description=corosync_conf_file,
                node=node,
            ) for node in node_list
        ]
        +
        [
            fixture.info(report_codes.CLUSTER_SETUP_SUCCESS)
        ]
    )
    return report_list


class CheckLive(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_names = ["node1", "node2", "node3"]

    def assert_live_required(self, forbidden_options):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [{"name": name} for name in self.node_names],
            ),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=forbidden_options
                )
            ],
            expected_in_processor=False
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


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_key",
    lambda: PCSD_SSL_KEY
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_cert",
    lambda ssl_key, server_name: PCSD_SSL_CERT
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
            COMMAND_NODE_LIST,
        )
        self.env_assist.assert_reports(reports_success_minimal_fixture())

    def test_enable(self):
        self.config.http.host.enable_cluster(NODE_LIST)
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            COMMAND_NODE_LIST,
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
            COMMAND_NODE_LIST,
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
            COMMAND_NODE_LIST,
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
            COMMAND_NODE_LIST,
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
            COMMAND_NODE_LIST,
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

    def test_no_keys_sync(self):
        self.config.calls.remove("http.files.put_files_requests")
        self.config.calls.remove("http.files.put_files_responses")
        self.config.calls.remove("http.host.send_pcsd_cert_requests")
        self.config.calls.remove("http.host.send_pcsd_cert_responses")
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            COMMAND_NODE_LIST,
            no_keys_sync=True,
        )

        self.env_assist.assert_reports(
            reports_success_minimal_fixture(keys_sync=False)
        )


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_key",
    lambda: PCSD_SSL_KEY
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_cert",
    lambda ssl_key, server_name: PCSD_SSL_CERT
)
class SetupSuccessAddresses(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_names = ["node1", "node2", "node3"]
        self.node_dests = [
            [Destination("node1-addr", 2225)],
            [Destination("node2-addr", 2226)],
            [Destination("node3-addr", 2227)],
        ]
        self.node_coros = ["node1-corosync", "node2-corosync", "node3-corosync"]
        self.config.env.set_known_hosts_dests({
            name: dest
            for name, dest in zip(self.node_names, self.node_dests)
        })
        patch_getaddrinfo(self, self.node_coros)
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture({
                name: [addr]
                for name, addr in zip(self.node_names, self.node_coros)
            }),
            communication_list=[
                {"label": name, "dest_list": dest}
                for name, dest in zip(self.node_names, self.node_dests)
            ],
            known_hosts={
                name: {
                    "dest_list": [
                        {"addr": dest.addr, "port": dest.port}
                        for dest in dest_list
                    ]
                }
                for name, dest_list in zip(self.node_names, self.node_dests)
            }
        )

    def test_communication_addresses(self):
        # Test that addresses don't mix up:
        # - node names are put into corosync.conf and used to get pcs addresses
        #   from known-hosts
        # - pcs addresses are used for pcs node-to-node communication
        # - corosync addresses are put into corosync.conf
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [
                {"name": name, "addrs": [addr]}
                for name, addr in zip(self.node_names, self.node_coros)
            ],
        )
        self.env_assist.assert_reports(reports_success_minimal_fixture(
            using_known_hosts_addresses=False
        ))


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_key",
    lambda: PCSD_SSL_KEY
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_cert",
    lambda ssl_key, server_name: PCSD_SSL_CERT
)
class Setup2NodeSuccessMinimal(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.node_list = NODE_LIST[:2]
        self.config.env.set_known_nodes(self.node_list)
        patch_getaddrinfo(self, self.node_list)
        services_status = {
            service: dict(
                installed=True, enabled=False, running=False, version="1.0",
            ) for service in SERVICE_LIST
        }
        (self.config
            .http.host.get_host_info(
                self.node_list,
                output_data=dict(
                    services=services_status,
                    cluster_configuration_exists=False,
                ),
            )
            .http.host.cluster_destroy(self.node_list)
            .http.host.update_known_hosts(
                self.node_list,
                to_add_hosts=self.node_list
            )
            .http.files.remove_files(self.node_list, pcsd_settings=True)
            .http.files.put_files(
                self.node_list,
                pcmk_authkey=RANDOM_KEY,
                corosync_authkey=RANDOM_KEY,
            )
            .http.host.send_pcsd_cert(
                cert=PCSD_SSL_CERT_DUMP,
                key=PCSD_SSL_KEY_DUMP,
                node_labels=self.node_list,
            )
        )

    def test_two_node(self):
        corosync_conf = corosync_conf_fixture(
            {node: [node] for node in self.node_list},
            quorum_options=dict(two_node="1"),
        )
        self.config.http.files.put_files(
            self.node_list,
            corosync_conf=corosync_conf,
            name="distribute_corosync_conf",
        )
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in self.node_list],
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture(node_list=self.node_list)
        )

    def test_auto_tie_breaker(self):
        corosync_conf = corosync_conf_fixture(
            {node: [node] for node in self.node_list},
            quorum_options=dict(auto_tie_breaker="1"),
        )
        self.config.http.files.put_files(
            self.node_list,
            corosync_conf=corosync_conf,
            name="distribute_corosync_conf",
        )
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in self.node_list],
            quorum_options=dict(auto_tie_breaker="1")
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture(node_list=self.node_list)
        )


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_key",
    lambda: PCSD_SSL_KEY
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_cert",
    lambda ssl_key, server_name: PCSD_SSL_CERT
)
class Validation(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3", "node4"])
        self.resolvable_hosts = patch_getaddrinfo(
            self,
            [f"{node}.addr" for node in NODE_LIST]
        )
        self.command_node_list = [
            dict(name=node, addrs=[f"{node}.addr"]) for node in NODE_LIST
        ]
        self.get_host_info_ok = {
            "services": {
                service: {
                    "installed": True,
                    "enabled": False,
                    "running": False,
                    "version": "1.0",
                } for service in SERVICE_LIST
            },
            "cluster_configuration_exists": False,
        }
        self.totem_allowed_options = [
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
        self.quorum_allowed_options = [
            "auto_tie_breaker",
            "last_man_standing",
            "last_man_standing_window",
            "wait_for_all",
        ]

    def test_default_node_addrs(self):
        (self.config
            .http.host.get_host_info(
                ["node1", "node2", "node3", "node4"],
                output_data=self.get_host_info_ok
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
                    # use a default address
                    {"name": "node3", "addrs": None},
                    # use a default address
                    {"name": "node4"},
                ],
                transport_type="knet"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node
                ) for node in ["node3", "node4"]
            ]
            +
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=0,
                    min_count=1,
                    max_count=8,
                    node_name="node2",
                    node_index=2
                ),
                fixture.error(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    force_code=report_codes.FORCE_NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addr1", "node3", "node4"]
                ),
                fixture.error(
                    report_codes.COROSYNC_NODE_ADDRESS_COUNT_MISMATCH,
                    node_addr_count={
                        "node1": 1,
                        "node2": 0,
                        "node3": 1,
                        "node4": 1,
                    }
                ),
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
            )
        )
        self.env_assist.assert_reports(
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
                output_data=self.get_host_info_ok
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
            )
        )
        self.env_assist.assert_reports(
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
        self.resolvable_hosts.clear()
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
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.NODE_ADDRESSES_UNRESOLVABLE,
                    address_list=["addr2"]
                )
            ]
            +
            reports_success_minimal_fixture(using_known_hosts_addresses=False)
        )

    def assert_corosync_validators_udp_udpu(self, transport):
        # The validators have their own tests. In here, we are only concerned
        # about calling the validators so we test that all provided options
        # have been validated.
        (self.config
            .http.host.get_host_info(
                NODE_LIST,
                output_data=self.get_host_info_ok
            )
        )
        self.resolvable_hosts.extend(NODE_LIST)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                self.command_node_list,
                transport_type=transport,
                transport_options={"a": "A"},
                link_list=[{"b": "B"}],
                compression_options={"c": "C"},
                crypto_options={"d": "D"},
                totem_options={"e": "E"},
                quorum_options={"f": "F"}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["a"],
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
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["b"],
                    option_type="link",
                    allowed=[
                        "bindnetaddr",
                        "broadcast",
                        "mcastaddr",
                        "mcastport",
                        "ttl",
                    ],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["e"],
                    option_type="totem",
                    allowed=self.totem_allowed_options,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["f"],
                    option_type="quorum",
                    allowed=self.quorum_allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_corosync_validators_udp(self):
        self.assert_corosync_validators_udp_udpu("udp")

    def test_corosync_validators_udpu(self):
        self.assert_corosync_validators_udp_udpu("udpu")

    def test_corosync_validators_knet(self):
        # The validators have their own tests. In here, we are only concerned
        # about calling the validators so we test that all provided options
        # have been validated.
        (self.config
            .http.host.get_host_info(
                NODE_LIST,
                output_data=self.get_host_info_ok
            )
        )
        self.resolvable_hosts.extend(NODE_LIST)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                self.command_node_list,
                transport_type="knet",
                transport_options={"a": "A"},
                link_list=[{"b": "B"}],
                compression_options={"c": "C"},
                crypto_options={"d": "D"},
                totem_options={"e": "E"},
                quorum_options={"f": "F"}
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["a"],
                    option_type="knet transport",
                    allowed=["ip_version", "knet_pmtud_interval", "link_mode"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["c"],
                    option_type="compression",
                    allowed=["level", "model", "threshold"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["d"],
                    option_type="crypto",
                    allowed=["cipher", "hash", "model"],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["b"],
                    option_type="link",
                    allowed=[
                        "link_priority",
                        "linknumber",
                        "mcastport",
                        "ping_interval",
                        "ping_precision",
                        "ping_timeout",
                        "pong_count",
                        "transport",
                    ],
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["e"],
                    option_type="totem",
                    allowed=self.totem_allowed_options,
                    allowed_patterns=[],
                ),
                fixture.error(
                    report_codes.INVALID_OPTIONS,
                    option_names=["f"],
                    option_type="quorum",
                    allowed=self.quorum_allowed_options,
                    allowed_patterns=[],
                ),
            ]
        )

    def test_too_many_addrs_knet(self):
        (self.config
            .http.host.get_host_info(
                NODE_LIST,
                output_data=self.get_host_info_ok
            )
        )
        nodelist = []
        for i, node in enumerate(NODE_LIST, 1):
            addrs = [f"addr{i}-{j}" for j in range(10)]
            self.resolvable_hosts.extend(addrs)
            nodelist.append({"name": node, "addrs": addrs})

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                nodelist,
                transport_type="knet",
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COROSYNC_BAD_NODE_ADDRESSES_COUNT,
                    actual_count=10,
                    min_count=1,
                    max_count=8,
                    node_name=name,
                    node_index=id
                )
                for id, name in enumerate(NODE_LIST, 1)
            ]
        )

    def test_all_nodes_unknown(self):
        self.config.env.set_known_nodes([])
        self.config.http.host.get_host_info([])
        self.resolvable_hosts.extend(NODE_LIST)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                self.command_node_list,
                transport_type="knet",
                force_flags=[report_codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    host_list=NODE_LIST
                ),
                fixture.error(report_codes.NONE_HOST_FOUND),
            ]
        )

    def test_some_nodes_unknown(self):
        # This also tests that corosync addresses do not matter for pcs-pcsd
        # communication.
        self.config.env.set_known_nodes(["node1"]) # pcs does not know addrX
        self.config.http.host.get_host_info(
            ["node1"],
            output_data=self.get_host_info_ok
        )
        self.resolvable_hosts.extend(["addr1", "addr2"])

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [
                    {"name": "node1", "addrs": ["addr1"]},
                    {"name": "node2", "addrs": ["addr2"]},
                ],
                transport_type="knet",
                force_flags=[report_codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.HOST_NOT_FOUND,
                    host_list=["node2"]
                ),
            ]
        )

    def test_node_ready_check(self):
        node3_response = deepcopy(self.get_host_info_ok)
        node3_response["cluster_configuration_exists"] = True
        node4_response = deepcopy(self.get_host_info_ok)
        for service_info in node4_response["services"].values():
            service_info["installed"] = False
        node5_response = deepcopy(self.get_host_info_ok)
        node5_response["services"]["corosync"]["running"] = True
        node5_response["services"]["pacemaker"]["running"] = True
        node6_response = deepcopy(self.get_host_info_ok)
        node6_response["services"]["pacemaker_remote"]["running"] = True
        node7_response = deepcopy(self.get_host_info_ok)
        for service_info in node7_response["services"].values():
            service_info["version"] = "1.1"

        nodelist = [f"node{i}" for i in range(10)]
        self.config.env.set_known_nodes(nodelist)
        self.config.http.host.get_host_info(
            communication_list=[
                {"label": "node0", "output": "bad json"},
                {"label": "node1", "output": json.dumps(self.get_host_info_ok)},
                {"label": "node2", "output": json.dumps({"services": {}})},
                {"label": "node3", "output": json.dumps(node3_response)},
                {"label": "node4", "output": json.dumps(node4_response)},
                {"label": "node5", "output": json.dumps(node5_response)},
                {"label": "node6", "output": json.dumps(node6_response)},
                {"label": "node7", "output": json.dumps(node7_response)},
                {"label": "node8", "response_code": 400, "output": "errA"},
                {"label": "node9", "was_connected": False, "error_msg": "errB"},
            ]
        )
        self.resolvable_hosts.extend(nodelist)
        host_version = {
            node: "1.0"
            for node in ["node1", "node3", "node4", "node5", "node6"]
        }
        host_version["node7"] = "1.1"

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [{"name": name, "addrs": None} for name in nodelist],
                transport_type="knet"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node
                ) for node in nodelist
            ]
            +
            [
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node="node0"
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="node8",
                    command="remote/check_host",
                    reason="errA"
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="node9",
                    command="remote/check_host",
                    reason="errB"
                ),
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node="node2"
                ),
                fixture.error(
                    report_codes.HOST_ALREADY_IN_CLUSTER_CONFIG,
                    host_name="node3",
                    force_code=report_codes.FORCE_ALREADY_IN_CLUSTER,
                ),
                fixture.error(
                    report_codes.SERVICE_NOT_INSTALLED,
                    node="node4",
                    service_list=["corosync", "pacemaker"]
                ),
                fixture.error(
                    report_codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
                    host_name="node5",
                    service_list=["corosync", "pacemaker"],
                    force_code=report_codes.FORCE_ALREADY_IN_CLUSTER,
                ),
                fixture.error(
                    report_codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
                    host_name="node6",
                    service_list=["pacemaker_remote"],
                    force_code=report_codes.FORCE_ALREADY_IN_CLUSTER,
                ),
                fixture.error(
                    report_codes.SERVICE_VERSION_MISMATCH,
                    service="pcsd",
                    hosts_version=host_version
                ),
                fixture.error(
                    report_codes.SERVICE_VERSION_MISMATCH,
                    service="corosync",
                    hosts_version=host_version
                ),
                fixture.error(
                    report_codes.SERVICE_VERSION_MISMATCH,
                    service="pacemaker",
                    hosts_version=host_version
                ),
                fixture.error(
                    report_codes.CLUSTER_WILL_BE_DESTROYED,
                    force_code=report_codes.FORCE_ALREADY_IN_CLUSTER
                ),
            ]
        )

    def test_node_ready_check_nonforceable(self):
        node3_response = deepcopy(self.get_host_info_ok)
        for service_info in node3_response["services"].values():
            service_info["installed"] = False
        node4_response = deepcopy(self.get_host_info_ok)
        for service_info in node4_response["services"].values():
            service_info["version"] = "1.1"

        nodelist = [f"node{i}" for i in range(7)]
        self.config.env.set_known_nodes(nodelist)
        self.config.http.host.get_host_info(
            communication_list=[
                {"label": "node0", "output": "bad json"},
                {"label": "node1", "output": json.dumps(self.get_host_info_ok)},
                {"label": "node2", "output": json.dumps({"services": {}})},
                {"label": "node3", "output": json.dumps(node3_response)},
                {"label": "node4", "output": json.dumps(node4_response)},
                {"label": "node5", "response_code": 400, "output": "errA"},
                {"label": "node6", "was_connected": False, "error_msg": "errB"},
            ]
        )
        self.resolvable_hosts.extend(nodelist)
        host_version = {node: "1.0" for node in ["node1", "node3"]}
        host_version["node4"] = "1.1"

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [{"name": name, "addrs": None} for name in nodelist],
                transport_type="knet",
                force_flags=[report_codes.FORCE],
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name=node,
                    address=node
                ) for node in nodelist
            ]
            +
            [
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node="node0"
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="node5",
                    command="remote/check_host",
                    reason="errA"
                ),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node="node6",
                    command="remote/check_host",
                    reason="errB"
                ),
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node="node2"
                ),
                fixture.error(
                    report_codes.SERVICE_NOT_INSTALLED,
                    node="node3",
                    service_list=["corosync", "pacemaker"]
                ),
                fixture.error(
                    report_codes.SERVICE_VERSION_MISMATCH,
                    service="pcsd",
                    hosts_version=host_version
                ),
                fixture.error(
                    report_codes.SERVICE_VERSION_MISMATCH,
                    service="corosync",
                    hosts_version=host_version
                ),
                fixture.error(
                    report_codes.SERVICE_VERSION_MISMATCH,
                    service="pacemaker",
                    hosts_version=host_version
                ),
            ]
        )

    def test_node_ready_check_forceable_forced(self):
        node1_response = deepcopy(self.get_host_info_ok)
        node1_response["cluster_configuration_exists"] = True
        node2_response = deepcopy(self.get_host_info_ok)
        node2_response["services"]["corosync"]["running"] = True
        node2_response["services"]["pacemaker"]["running"] = True
        node3_response = deepcopy(self.get_host_info_ok)
        node3_response["services"]["pacemaker_remote"]["running"] = True

        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(COROSYNC_NODE_LIST)
        )
        dummy_requests, get_host_info_responses = create_communication(
            [
                {"label": "node1", "output": json.dumps(node1_response)},
                {"label": "node2", "output": json.dumps(node2_response)},
                {"label": "node3", "output": json.dumps(node3_response)},
            ],
            action="remote/check_host"
        )
        self.config.calls.get(
            "http.host.get_host_info_responses"
        ).response_list = get_host_info_responses
        self.resolvable_hosts.extend(NODE_LIST)

        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            COMMAND_NODE_LIST,
            transport_type="knet",
            force_flags=[report_codes.FORCE],
        )

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.HOST_ALREADY_IN_CLUSTER_CONFIG,
                    host_name="node1"
                ),
                fixture.warn(
                    report_codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
                    host_name="node2",
                    service_list=["corosync", "pacemaker"]
                ),
                fixture.warn(
                    report_codes.HOST_ALREADY_IN_CLUSTER_SERVICES,
                    host_name="node3",
                    service_list=["pacemaker_remote"]
                ),
            ]
            +
            reports_success_minimal_fixture()
        )

    def test_wait_not_valid(self):
        self.config.http.host.get_host_info(
            NODE_LIST,
            output_data=self.get_host_info_ok
        )
        self.resolvable_hosts.extend(NODE_LIST)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                self.command_node_list,
                transport_type="knet",
                start=True,
                wait="abcd"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_TIMEOUT_VALUE,
                    timeout="abcd"
                )
            ]
        )

    def test_wait_without_start(self):
        self.config.http.host.get_host_info(
            NODE_LIST,
            output_data=self.get_host_info_ok
        )
        self.resolvable_hosts.extend(NODE_LIST)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                self.command_node_list,
                transport_type="knet",
                wait="10"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.WAIT_FOR_NODE_STARTUP_WITHOUT_START,
                )
            ]
        )

    def test_errors_from_all_validators(self):
        node3_response = deepcopy(self.get_host_info_ok)
        node3_response["cluster_configuration_exists"] = True
        self.config.http.host.get_host_info(
            communication_list=[
                {"label": "node1", "output": json.dumps(self.get_host_info_ok)},
                {"label": "node2", "output": json.dumps(self.get_host_info_ok)},
                {"label": "node3", "output": json.dumps(node3_response)},
            ]
        )
        self.resolvable_hosts.extend(NODE_LIST)

        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                self.command_node_list,
                transport_type="tcp",
                wait="abcd"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_value="tcp",
                    option_name="transport",
                    allowed_values=("knet", "udp", "udpu")
                ),
                fixture.error(
                    report_codes.WAIT_FOR_NODE_STARTUP_WITHOUT_START,
                ),
                fixture.error(
                    report_codes.INVALID_TIMEOUT_VALUE,
                    timeout="abcd"
                ),
                fixture.error(
                    report_codes.HOST_ALREADY_IN_CLUSTER_CONFIG,
                    host_name="node3",
                    force_code=report_codes.FORCE_ALREADY_IN_CLUSTER
                ),
                fixture.error(
                    report_codes.CLUSTER_WILL_BE_DESTROYED,
                    force_code=report_codes.FORCE_ALREADY_IN_CLUSTER
                ),
            ]
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
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_key",
    lambda: PCSD_SSL_KEY
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_cert",
    lambda ssl_key, server_name: PCSD_SSL_CERT
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
        self.env_assist.assert_reports(reports_success_minimal_fixture(
            using_known_hosts_addresses=False
        ))

    def test_all_options(self):
        node_addrs = {
            node: [f"{node}.addr{i}" for i in range(constants.LINKS_KNET_MAX)]
            for node in NODE_LIST
        }
        self.resolvable_hosts.extend(set(flat_list(node_addrs.values())))
        link_list = [
            dict(
                linknumber="1",
                link_priority="100",
                mcastport="12345",
                ping_interval="1",
                ping_precision="2",
                ping_timeout="3",
                pong_count="4",
                transport="sctp",
            ),
            dict(mcastport="23456"),
            dict(
                linknumber="7",
                transport="udp",
            ),
            dict(
                linknumber="3",
                link_priority="20",
            ),
            dict(mcastport="34567"),
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
        self.env_assist.assert_reports(reports_success_minimal_fixture(
            using_known_hosts_addresses=False
        ))

    def test_disable_crypto(self):
        node_addrs = {node: [f"{node}.addr"] for node in NODE_LIST}
        self.resolvable_hosts.extend(set(flat_list(node_addrs.values())))
        crypto_options = dict(
            cipher="none",
            hash="none",
        )
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(
                node_addrs,
                transport_type=self.transport_type,
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
            crypto_options=crypto_options,
        )
        self.env_assist.assert_reports(reports_success_minimal_fixture(
            using_known_hosts_addresses=False
        ))


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_key",
    lambda: PCSD_SSL_KEY
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_cert",
    lambda ssl_key, server_name: PCSD_SSL_CERT
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
        self.env_assist.assert_reports(reports_success_minimal_fixture(
            using_known_hosts_addresses=False
        ))

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
        self.env_assist.assert_reports(reports_success_minimal_fixture(
            using_known_hosts_addresses=False
        ))


def get_time_mock(step=1):
    _counter = 0
    def time():
        nonlocal _counter
        _counter += step
        return _counter
    return time


@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_key",
    lambda: PCSD_SSL_KEY
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_cert",
    lambda ssl_key, server_name: PCSD_SSL_CERT
)
class SetupWithWait(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(NODE_LIST + ["random_node"])
        patch_getaddrinfo(self, NODE_LIST)
        services_status = {
            service: dict(
                installed=True, enabled=False, running=False, version="1.0",
            ) for service in SERVICE_LIST
        }
        (self.config
            .http.host.get_host_info(
                NODE_LIST,
                output_data=dict(
                    services=services_status,
                    cluster_configuration_exists=False,
                ),
            )
            .http.host.cluster_destroy(NODE_LIST)
            .http.host.update_known_hosts(NODE_LIST, to_add_hosts=NODE_LIST)
            .http.files.remove_files(NODE_LIST, pcsd_settings=True)
            .http.files.put_files(
                NODE_LIST,
                pcmk_authkey=RANDOM_KEY,
                corosync_authkey=RANDOM_KEY,
            )
            .http.host.send_pcsd_cert(
                cert=PCSD_SSL_CERT_DUMP,
                key=PCSD_SSL_KEY_DUMP,
                node_labels=NODE_LIST
            )
            .http.files.put_files(
                NODE_LIST,
                corosync_conf=corosync_conf_fixture(
                    {node: [node] for node in NODE_LIST}
                ),
                name="distribute_corosync_conf",
            )
            .http.host.start_cluster(NODE_LIST)
        )

    @mock.patch("time.sleep", lambda secs: None)
    @mock.patch("time.time", get_time_mock())
    def test_some_success(self):
        self.config.http.host.check_pacemaker_started(
            pacemaker_started_node_list=NODE_LIST[:1],
            pacemaker_not_started_node_list=NODE_LIST[1:],
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                start=True,
                wait=1,
            ),
            [
                fixture.error(report_codes.WAIT_FOR_NODE_STARTUP_TIMED_OUT),
                fixture.error(report_codes.WAIT_FOR_NODE_STARTUP_ERROR),
            ]
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
                ) for node in NODE_LIST[:1]
            ]
        )

    @mock.patch("time.sleep", lambda secs: None)
    @mock.patch("time.time", get_time_mock(step=2))
    def test_timed_out_right_away(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                start=True,
                wait=1,
            ),
            [
                fixture.error(report_codes.WAIT_FOR_NODE_STARTUP_TIMED_OUT),
                fixture.error(report_codes.WAIT_FOR_NODE_STARTUP_ERROR),
            ]
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
        )

    @mock.patch("time.sleep", lambda secs: None)
    @mock.patch("time.time", get_time_mock())
    def test_multiple_tries(self):
        (self.config
            .http.host.check_pacemaker_started(
                pacemaker_started_node_list=NODE_LIST[:1],
                pacemaker_not_started_node_list=NODE_LIST[1:],
            )
            .http.host.check_pacemaker_started(
                pacemaker_not_started_node_list=NODE_LIST[1:],
                name="pcmk_status_check_1"
            )
            .http.host.check_pacemaker_started(
                pacemaker_started_node_list=NODE_LIST[1:2],
                pacemaker_not_started_node_list=NODE_LIST[2:],
                name="pcmk_status_check_2"
            )
            .http.host.check_pacemaker_started(
                pacemaker_started_node_list=NODE_LIST[2:3],
                name="pcmk_status_check_3"
            )
        )
        cluster.setup(
            self.env_assist.get_env(),
            CLUSTER_NAME,
            [dict(name=node, addrs=None) for node in NODE_LIST],
            start=True,
            wait=5,
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

    @mock.patch("time.sleep", lambda secs: None)
    @mock.patch("time.time", get_time_mock())
    def test_fails(self):
        node_not_started = dict(
            label=NODE_LIST[2],
            output=json.dumps(dict(
                pending=True,
                online=False,
            )),
        )
        (self.config
            .http.host.check_pacemaker_started(
                communication_list=[
                    dict(
                        label=NODE_LIST[0],
                        was_connected=False,
                        error_msg="error"
                    ),
                    dict(
                        label=NODE_LIST[1],
                        output="not json"
                    ),
                    node_not_started,
                ],
            )
            .http.host.check_pacemaker_started(
                communication_list=[
                    dict(
                        label=NODE_LIST[0],
                        response_code=400,
                    ),
                    node_not_started,
                ],
                name="pcmk_status_check_2"
            )
            .http.host.check_pacemaker_started(
                pacemaker_started_node_list=NODE_LIST[2:3],
                name="pcmk_status_check_3"
            )
        )
        error_reports = [
            fixture.error(
                report_codes.INVALID_RESPONSE_FORMAT, node=NODE_LIST[1]
            ),
            fixture.error(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                node=NODE_LIST[0],
                command="remote/pacemaker_node_status",
                reason="",
            ),
        ]
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                start=True,
                wait=5,
            ),
            (
                [fixture.error(report_codes.WAIT_FOR_NODE_STARTUP_ERROR)]
                +
                error_reports
            ),
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
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=NODE_LIST[0],
                    command="remote/pacemaker_node_status",
                    reason="error",
                )
            ]
            +
            [
                fixture.info(
                    report_codes.CLUSTER_START_SUCCESS,
                    node=node,
                ) for node in NODE_LIST[2:3]
            ]
            +
            error_reports
        )

    @mock.patch("time.sleep", lambda secs: None)
    @mock.patch("time.time", get_time_mock())
    def test_fails_and_timed_out(self):
        (self.config
            .http.host.check_pacemaker_started(
                communication_list=[
                    dict(
                        label=NODE_LIST[0],
                        was_connected=False,
                        error_msg="error"
                    ),
                    dict(
                        label=NODE_LIST[1],
                        output="not json"
                    ),
                    dict(
                        label=NODE_LIST[2],
                        output=json.dumps(dict(
                            pending=True,
                            online=False,
                        )),
                    ),
                ],
            )
            .http.host.check_pacemaker_started(
                pacemaker_started_node_list=[NODE_LIST[0]],
                pacemaker_not_started_node_list=[NODE_LIST[2]],
                name="pcmk_status_check_1"
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                start=True,
                wait=2,
            ),
            [
                fixture.error(report_codes.WAIT_FOR_NODE_STARTUP_ERROR),
                fixture.error(report_codes.WAIT_FOR_NODE_STARTUP_TIMED_OUT),
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT, node=NODE_LIST[1]
                ),
            ]
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
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                    node=NODE_LIST[0],
                    command="remote/pacemaker_node_status",
                    reason="error",
                ),
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node=NODE_LIST[1],
                ),
            ]
            +
            [
                fixture.info(
                    report_codes.CLUSTER_START_SUCCESS,
                    node=node,
                ) for node in NODE_LIST[:1]
            ]
        )


REASON = "error msg"

@mock.patch(
    "pcs.lib.commands.cluster.generate_binary_key",
    lambda random_bytes_count: RANDOM_KEY,
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_key",
    lambda: PCSD_SSL_KEY
)
@mock.patch(
    "pcs.lib.commands.cluster.ssl.generate_cert",
    lambda ssl_key, server_name: PCSD_SSL_CERT
)
class Failures(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(NODE_LIST + ["random_node"])
        self.nodes_failed = NODE_LIST[:1]
        self.nodes_offline = NODE_LIST[1:2]
        self.nodes_success = NODE_LIST[2:]
        self.communication_list = [
            dict(
                label=node,
                response_code=400,
                output=REASON,
            ) for node in self.nodes_failed
        ] + [
            dict(
                label=node,
                was_connected=False,
                error_msg=REASON,
            ) for node in self.nodes_offline
        ] + [
            dict(label=node) for node in self.nodes_success
        ]
        patch_getaddrinfo(self, NODE_LIST)
        config_succes_minimal_fixture(
            self.config,
            corosync_conf=corosync_conf_fixture(COROSYNC_NODE_LIST),
        )

    def _get_failure_reports(self, command):
        return [
            fixture.error(
                report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                node=node,
                command=command,
                reason=REASON,
            ) for node in self.nodes_failed
        ] + [
            fixture.error(
                report_codes.NODE_COMMUNICATION_ERROR_UNABLE_TO_CONNECT,
                node=node,
                command=command,
                reason=REASON,
            ) for node in self.nodes_offline
        ]

    def test_start_failure(self):
        (self.config
            .http.host.enable_cluster(NODE_LIST)
            .http.host.start_cluster(
                communication_list=self.communication_list,
            )
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
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
            +
            self._get_failure_reports("remote/cluster_start")
        )

    def test_enable_failure(self):
        self.config.http.host.enable_cluster(
            communication_list=self.communication_list,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()
            +
            [fixture.info(report_codes.CLUSTER_ENABLE_STARTED)]
            +
            self._get_failure_reports("remote/cluster_enable")
            +
            [
                fixture.info(report_codes.CLUSTER_ENABLE_SUCCESS, node=node)
                for node in self.nodes_success
            ]
        )

    def _remove_calls(self, count):
        for name in self.config.calls.names[-count:]:
            self.config.calls.remove(name)

    def test_corosync_conf_distribution_communication_failure(self):
        self._remove_calls(2)
        self.config.http.files.put_files(
            communication_list=self.communication_list,
            corosync_conf=corosync_conf_fixture(COROSYNC_NODE_LIST),
            name="distribute_corosync_conf",
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-4]
            +
            [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    file_description="corosync.conf",
                    node=node,
                ) for node in self.nodes_success
            ]
            +
            self._get_failure_reports("remote/put_file")
        )

    def test_corosync_conf_distribution_failure(self):
        self._remove_calls(2)
        self.config.http.files.put_files(
            communication_list=[
                dict(
                    label=NODE_LIST[0],
                    output=json.dumps(dict(
                        files={
                            "corosync.conf": dict(
                                code="unexpected",
                                message=REASON
                            )
                        }
                    ))
                )
            ] + [
                dict(label=node) for node in NODE_LIST[1:]
            ],
            corosync_conf=corosync_conf_fixture(COROSYNC_NODE_LIST),
            name="distribute_corosync_conf",
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-4]
            +
            [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    file_description="corosync.conf",
                    node=node,
                ) for node in NODE_LIST[1:]
            ]
            +
            [
                fixture.error(
                    report_codes.FILE_DISTRIBUTION_ERROR,
                    file_description="corosync.conf",
                    node=NODE_LIST[0],
                    reason=REASON,
                )
            ]
        )

    def test_corosync_conf_distribution_invalid_response(self):
        self._remove_calls(2)
        self.config.http.files.put_files(
            communication_list=[
                dict(
                    label=NODE_LIST[0],
                    output="invalid json",
                )
            ] + [
                dict(label=node) for node in NODE_LIST[1:]
            ],
            corosync_conf=corosync_conf_fixture(COROSYNC_NODE_LIST),
            name="distribute_corosync_conf",
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-4]
            +
            [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    file_description="corosync.conf",
                    node=node,
                ) for node in NODE_LIST[1:]
            ]
            +
            [
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node=NODE_LIST[0],
                )
            ]
        )

    def test_sending_pcsd_ssl_cert_and_key_failure(self):
        self._remove_calls(4)
        self.config.http.host.send_pcsd_cert(
            cert=PCSD_SSL_CERT_DUMP,
            key=PCSD_SSL_KEY_DUMP,
            communication_list=[
                {
                    "label": NODE_LIST[0],
                    "response_code": 400,
                    "output": REASON,
                }
            ] + [
                dict(label=node) for node in NODE_LIST[1:]
            ]
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-8]
            +
            [
                fixture.info(
                    report_codes.PCSD_SSL_CERT_AND_KEY_SET_SUCCESS,
                    node=node,
                ) for node in NODE_LIST[1:]
            ]
            +
            [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=NODE_LIST[0],
                    command="remote/set_certs",
                    reason=REASON
                )
            ]
        )

    def test_removing_files_communication_failure(self):
        self._remove_calls(8)
        self.config.http.files.remove_files(
            communication_list=self.communication_list,
            pcsd_settings=True,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-19]
            +
            [
                fixture.info(
                    report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
                    node=node,
                    file_description="pcsd settings",
                ) for node in self.nodes_success
            ]
            +
            self._get_failure_reports("remote/remove_file")
        )

    def test_removing_files_failure(self):
        self._remove_calls(8)
        self.config.http.files.remove_files(
            communication_list=[
                dict(
                    label=NODE_LIST[0],
                    output=json.dumps(dict(
                        files={
                            "pcsd settings": dict(
                                code="unexpected",
                                message=REASON
                            )
                        }
                    ))
                )
            ] + [
                dict(label=node) for node in NODE_LIST[1:]
            ],
            pcsd_settings=True,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-19]
            +
            [
                fixture.info(
                    report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
                    node=node,
                    file_description="pcsd settings",
                ) for node in NODE_LIST[1:]
            ]
            +
            [
                fixture.error(
                    report_codes.FILE_REMOVE_FROM_NODE_ERROR,
                    node=NODE_LIST[0],
                    file_description="pcsd settings",
                    reason=REASON,
                )
            ]
        )

    def test_removing_files_invalid_response(self):
        self._remove_calls(8)
        self.config.http.files.remove_files(
            communication_list=[
                dict(
                    label=NODE_LIST[0],
                    output="invalid json",
                )
            ] + [
                dict(label=node) for node in NODE_LIST[1:]
            ],
            pcsd_settings=True,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-19]
            +
            [
                fixture.info(
                    report_codes.FILE_REMOVE_FROM_NODE_SUCCESS,
                    node=node,
                    file_description="pcsd settings",
                ) for node in NODE_LIST[1:]
            ]
            +
            [
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node=NODE_LIST[0],
                )
            ]
        )

    def test_distibution_of_authkey_files_communication_failure(self):
        self._remove_calls(6)
        self.config.http.files.put_files(
            communication_list=[
                dict(
                    label=NODE_LIST[0],
                    output=json.dumps(dict(
                        files={
                            "pacemaker_remote authkey": dict(
                                code="unexpected",
                                message=REASON
                            ),
                            "corosync authkey": dict(
                                code="written",
                                message=""
                            ),
                        }
                    ))
                ),
                dict(
                    label=NODE_LIST[1],
                    output=json.dumps(dict(
                        files={
                            "pacemaker_remote authkey": dict(
                                code="written",
                                message=""
                            ),
                            "corosync authkey": dict(
                                code="unexpected",
                                message=REASON
                            ),
                        }
                    ))
                ),
            ] + [
                dict(label=node) for node in NODE_LIST[2:]
            ],
            pcmk_authkey=RANDOM_KEY,
            corosync_authkey=RANDOM_KEY,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-15]
            +
            [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    node=node,
                    file_description=file,
                )
                for node in NODE_LIST[2:]
                for file in ["corosync authkey", "pacemaker authkey"]
            ]
            +
            [
                fixture.error(
                    report_codes.FILE_DISTRIBUTION_ERROR,
                    node=NODE_LIST[0],
                    reason=REASON,
                    file_description="pacemaker authkey",
                ),
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    node=NODE_LIST[0],
                    file_description="corosync authkey",
                ),
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    node=NODE_LIST[1],
                    file_description="pacemaker authkey",
                ),
                fixture.error(
                    report_codes.FILE_DISTRIBUTION_ERROR,
                    node=NODE_LIST[1],
                    reason=REASON,
                    file_description="corosync authkey",
                ),
            ]
        )

    def test_distibution_of_authkey_files_invalid_response(self):
        self._remove_calls(6)
        self.config.http.files.put_files(
            communication_list=[
                dict(
                    label=NODE_LIST[0],
                    output="invalid json",
                ),
            ] + [
                dict(label=node) for node in NODE_LIST[1:]
            ],
            pcmk_authkey=RANDOM_KEY,
            corosync_authkey=RANDOM_KEY,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-15]
            +
            [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    node=node,
                    file_description=file,
                )
                for node in NODE_LIST[1:]
                for file in ["corosync authkey", "pacemaker authkey"]
            ]
            +
            [
                fixture.error(
                    report_codes.INVALID_RESPONSE_FORMAT,
                    node=NODE_LIST[0],
                ),
            ]
        )

    def test_distibution_of_authkey_files_failure(self):
        self._remove_calls(6)
        self.config.http.files.put_files(
            communication_list=self.communication_list,
            pcmk_authkey=RANDOM_KEY,
            corosync_authkey=RANDOM_KEY,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-15]
            +
            [
                fixture.info(
                    report_codes.FILE_DISTRIBUTION_SUCCESS,
                    node=node,
                    file_description=file,
                )
                for node in self.nodes_success
                for file in ["corosync authkey", "pacemaker authkey"]
            ]
            +
            self._get_failure_reports("remote/put_file")
        )

    def test_distibution_known_hosts_failure(self):
        self._remove_calls(10)
        self.config.http.host.update_known_hosts(
            communication_list=self.communication_list,
            to_add_hosts=NODE_LIST
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-20]
            +
            self._get_failure_reports("remote/known_hosts_change")
        )

    def test_cluster_destroy_failure(self):
        self._remove_calls(12)
        self.config.http.host.cluster_destroy(
            communication_list=self.communication_list,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.setup(
                self.env_assist.get_env(),
                CLUSTER_NAME,
                [dict(name=node, addrs=None) for node in NODE_LIST],
                enable=True,
                start=True,
            ),
            []
        )
        self.env_assist.assert_reports(
            reports_success_minimal_fixture()[:-23]
            +
            [
                fixture.info(
                    report_codes.CLUSTER_DESTROY_SUCCESS,
                    node=node
                )
                for node in self.nodes_success
            ]
            +
            self._get_failure_reports("remote/cluster_destroy")
        )
