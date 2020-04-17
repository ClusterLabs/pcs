import tempfile
from unittest import TestCase
from textwrap import dedent

from pcs_test.tools.assertions import AssertPcsMixin

from pcs_test.tools.pcs_runner import PcsRunner


# TODO: switch check of created corosync.conf with a new command for displaying
# corosync.conf once avalable
class SetupLocal(AssertPcsMixin, TestCase):
    def setUp(self):
        self.corosync_conf_file = tempfile.NamedTemporaryFile("r")
        self.pcs_runner = PcsRunner(
            cib_file=None, corosync_conf_opt=self.corosync_conf_file.name
        )

    def tearDown(self):
        self.corosync_conf_file.close()

    def test_minimal(self):
        _, code = self.pcs_runner.run(
            # need to use --froce for not failing on unresolvable addresses
            "cluster setup cluster_name node1 node2 --force",
        )
        self.assertEqual(code, 0)
        self.assertEqual(
            self.corosync_conf_file.read(),
            dedent(
                """\
                totem {
                    version: 2
                    cluster_name: cluster_name
                    transport: knet
                    crypto_cipher: aes256
                    crypto_hash: sha256
                }

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

                quorum {
                    provider: corosync_votequorum
                    two_node: 1
                }

                logging {
                    to_logfile: yes
                    logfile: /var/log/cluster/corosync.log
                    to_syslog: yes
                    timestamp: on
                }
                """
            ),
        )

    def test_multiple_options(self):
        self.assert_pcs_success(
            "cluster setup cluster_name node1 addr=127.0.0.1 addr=127.0.1.1 "
            "addr=127.0.2.3 node2 addr=127.0.0.2 addr=127.0.1.2 addr=127.0.2.2 "
            "node3 addr=127.0.0.3 addr=127.0.1.3 addr=127.0.2.1 transport knet "
            "ip_version=ipv4 link_mode=passive link linknumber=2 "
            "link_priority=100 mcastport=12345 ping_interval=1 "
            "ping_precision=2 ping_timeout=3 pong_count=4 transport=sctp "
            "link linknumber=1 transport=udp compression level=2 model=zlib "
            "threshold=10 crypto cipher=aes256 hash=sha512 model=openssl totem "
            "consensus=0 downcheck=1 token=12 quorum last_man_standing=1 "
            "last_man_standing_window=10",
        )
        self.assertEqual(
            self.corosync_conf_file.read(),
            dedent(
                """\
                totem {
                    version: 2
                    cluster_name: cluster_name
                    transport: knet
                    consensus: 0
                    downcheck: 1
                    token: 12
                    ip_version: ipv4
                    link_mode: passive
                    knet_compression_level: 2
                    knet_compression_model: zlib
                    knet_compression_threshold: 10
                    crypto_cipher: aes256
                    crypto_hash: sha512
                    crypto_model: openssl

                    interface {
                        knet_transport: udp
                        linknumber: 1
                    }

                    interface {
                        knet_link_priority: 100
                        knet_ping_interval: 1
                        knet_ping_precision: 2
                        knet_ping_timeout: 3
                        knet_pong_count: 4
                        knet_transport: sctp
                        linknumber: 2
                        mcastport: 12345
                    }
                }

                nodelist {
                    node {
                        ring0_addr: 127.0.0.1
                        ring1_addr: 127.0.1.1
                        ring2_addr: 127.0.2.3
                        name: node1
                        nodeid: 1
                    }

                    node {
                        ring0_addr: 127.0.0.2
                        ring1_addr: 127.0.1.2
                        ring2_addr: 127.0.2.2
                        name: node2
                        nodeid: 2
                    }

                    node {
                        ring0_addr: 127.0.0.3
                        ring1_addr: 127.0.1.3
                        ring2_addr: 127.0.2.1
                        name: node3
                        nodeid: 3
                    }
                }

                quorum {
                    provider: corosync_votequorum
                    last_man_standing: 1
                    last_man_standing_window: 10
                }

                logging {
                    to_logfile: yes
                    logfile: /var/log/cluster/corosync.log
                    to_syslog: yes
                    timestamp: on
                }
                """
            ),
        )

    def test_failure(self):
        # pylint: disable=line-too-long
        self.assert_pcs_fail(
            "cluster setup cluster_name node1 addr=127.0.0.1 addr=127.0.1.1.2 "
            "addr=127.0.2.3 node2 addr=127.0.0.2 addr=127.0.2.2 "
            "node3 addr=127.0.0.3 addr=127.0.1.3 addr=127.0.2.1 transport knet "
            "ip_version=ipv4 link_mode=passive link linknumber=2 "
            "link_priority=100 mcastport=123450 ping_interval=1 "
            "ping_precision=2 ping_timeout=3 pong__count=4 transport=sctp "
            "link linknumber=3 transport=udp compression level=2 model=zlib "
            "threshold=10 crypto hash=sha512 model=openssl totem "
            "consensus=0 downcheck=1 token=12 quorum lst_man_standing=1 "
            "last_man_standing_window=10",
            stdout_full=dedent(
                """\
                Error: Unable to resolve addresses: '127.0.1.1.2', use --force to override
                Error: All nodes must have the same number of addresses; nodes 'node1', 'node3' have 3 addresses; node 'node2' has 2 addresses
                Error: invalid link option 'pong__count', allowed options are: 'link_priority', 'linknumber', 'mcastport', 'ping_interval', 'ping_precision', 'ping_timeout', 'pong_count', 'transport'
                Error: '123450' is not a valid mcastport value, use a port number (1..65535)
                Error: Cannot set options for non-existent link '3', existing links: '0', '1', '2'
                Error: invalid quorum option 'lst_man_standing', allowed options are: 'auto_tie_breaker', 'last_man_standing', 'last_man_standing_window', 'wait_for_all'
                Error: If quorum option 'last_man_standing_window' is enabled, quorum option 'last_man_standing' must be enabled as well
                Error: Errors have occurred, therefore pcs is unable to continue
                """
            ),
        )
        self.assertEqual(self.corosync_conf_file.read(), "")
