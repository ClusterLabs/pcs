from textwrap import dedent
from unittest import TestCase

from pcs.common.corosync_conf import (
    CorosyncConfDto,
    CorosyncNodeAddressDto,
    CorosyncNodeAddressType,
    CorosyncNodeDto,
    CorosyncQuorumDeviceSettingsDto,
)
from pcs.common.reports import codes as report_codes
from pcs.common.types import CorosyncTransportType
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .common import fixture_totem


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
                cluster_uuid=None,
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

    def test_corosync_conf_with_uuid(self):
        self.config.corosync_conf.load_content(
            dedent(
                """\
                totem {
                    version: 2
                    cluster_name: HACluster
                    cluster_uuid: uuid
                    transport: knet
                    crypto_cipher: aes256
                    crypto_hash: sha256
                }
                
                nodelist {
                    node {
                        ring0_addr: node1-addr
                        name: node1
                        nodeid: 1
                    }

                    node {
                        ring0_addr: node2-addr
                        name: node2
                        nodeid: 2
                    }
                }
                
                quorum {
                    provider: corosync_votequorum
                    two_node: 1
                }
                """
            )
        )
        self.assertEqual(
            CorosyncConfDto(
                cluster_name="HACluster",
                cluster_uuid="uuid",
                transport=CorosyncTransportType.KNET,
                totem_options={},
                transport_options={},
                compression_options={},
                crypto_options={"cipher": "aes256", "hash": "sha256"},
                nodes=[
                    CorosyncNodeDto(
                        name="node1",
                        nodeid="1",
                        addrs=[
                            CorosyncNodeAddressDto(
                                addr="node1-addr",
                                link="0",
                                type=CorosyncNodeAddressType.FQDN,
                            ),
                        ],
                    ),
                    CorosyncNodeDto(
                        name="node2",
                        nodeid="2",
                        addrs=[
                            CorosyncNodeAddressDto(
                                addr="node2-addr",
                                link="0",
                                type=CorosyncNodeAddressType.FQDN,
                            ),
                        ],
                    ),
                ],
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
                cluster_uuid=None,
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
                                addr="node1-addr",
                                link="0",
                                type=CorosyncNodeAddressType.FQDN,
                            ),
                            CorosyncNodeAddressDto(
                                addr="10.0.0.1",
                                link="1",
                                type=CorosyncNodeAddressType.IPV4,
                            ),
                        ],
                    ),
                    CorosyncNodeDto(
                        name="node2",
                        nodeid="2",
                        addrs=[
                            CorosyncNodeAddressDto(
                                addr="node2-addr",
                                link="0",
                                type=CorosyncNodeAddressType.FQDN,
                            ),
                            CorosyncNodeAddressDto(
                                addr="10.0.0.2",
                                link="1",
                                type=CorosyncNodeAddressType.IPV4,
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
