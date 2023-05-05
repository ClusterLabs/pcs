from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_tmp_file,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

from .common import fixture_corosync_conf_minimal


class UpdateLocal(AssertPcsMixin, TestCase):
    def setUp(self):
        self.corosync_conf_file = get_tmp_file(
            "tier1_cluster_config_update_corosync.conf"
        )
        self.pcs_runner = PcsRunner(
            cib_file=None,
            corosync_conf_opt=self.corosync_conf_file.name,
        )

    def tearDown(self):
        self.corosync_conf_file.close()

    def test_minimal(self):
        write_data_to_tmpfile(
            fixture_corosync_conf_minimal(no_cluster_uuid=True),
            self.corosync_conf_file,
        )
        self.assert_pcs_success(
            "cluster config update transport ip_version=ipv4 totem token=12".split()
        )
        self.assertEqual(
            self.corosync_conf_file.read(),
            dedent(
                """\
                totem {
                    version: 2
                    cluster_name: cluster_name
                    transport: knet
                    ip_version: ipv4
                    crypto_cipher: aes256
                    crypto_hash: sha256
                    token: 12
                }

                nodelist {
                    node {
                        ring0_addr: node1_addr
                        name: node1
                        nodeid: 1
                    }

                    node {
                        ring0_addr: node2_addr
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
        write_data_to_tmpfile(
            fixture_corosync_conf_minimal(), self.corosync_conf_file
        )
        self.assert_pcs_success(
            (
                "cluster config update "
                "transport ip_version= link_mode=passive "
                "compression level=2 model=zlib threshold=10 "
                "crypto cipher=aes256 hash=sha512 model=openssl "
                "totem consensus=0 downcheck=1 token=12"
            ).split()
        )
        self.assertEqual(
            self.corosync_conf_file.read(),
            dedent(
                """\
                totem {
                    version: 2
                    cluster_name: cluster_name
                    cluster_uuid: cluster_uuid
                    transport: knet
                    crypto_cipher: aes256
                    crypto_hash: sha512
                    consensus: 0
                    downcheck: 1
                    token: 12
                    link_mode: passive
                    knet_compression_level: 2
                    knet_compression_model: zlib
                    knet_compression_threshold: 10
                    crypto_model: openssl
                }

                nodelist {
                    node {
                        ring0_addr: node1_addr
                        name: node1
                        nodeid: 1
                    }

                    node {
                        ring0_addr: node2_addr
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

    def test_file_does_not_exist(self):
        file_name = self.corosync_conf_file.name + ".non-existing"
        self.pcs_runner.corosync_conf_opt = file_name
        self.assert_pcs_fail(
            "cluster config update transport ip_version=ipv4 totem token=12".split(),
            (
                f"Error: Unable to read Corosync configuration '{file_name}': "
                f"No such file or directory: '{file_name}'\n"
            ),
        )

    def test_file_parse_error(self):
        write_data_to_tmpfile(
            "this is not\na valid corosync.conf file\n", self.corosync_conf_file
        )
        self.assert_pcs_fail(
            "cluster config update transport ip_version=ipv4 totem token=12".split(),
            (
                "Error: Unable to parse corosync config: a line is not opening "
                "or closing a section or key: value\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_validation_errors(self):
        write_data_to_tmpfile(
            fixture_corosync_conf_minimal(), self.corosync_conf_file
        )
        self.assert_pcs_fail(
            (
                "cluster config update "
                "transport ip_version=ipvx link_mode=passive "
                "compression level=2 model=zlib threshold=NaN "
                "crypto hash= model=openssl "
                "totem consensus=0 down_check=1 token=12"
            ).split(),
            (
                "Error: invalid totem option 'down_check', allowed options "
                "are: 'block_unlisted_ips', 'consensus', 'downcheck', 'fail_recv_const', "
                "'heartbeat_failures_allowed', 'hold', 'join', 'max_messages', "
                "'max_network_delay', 'merge', 'miss_count_const', "
                "'send_join', 'seqno_unchanged_const', 'token', "
                "'token_coefficient', 'token_retransmit', "
                "'token_retransmits_before_loss_const', 'window_size'\n"
                "Error: 'ipvx' is not a valid ip_version value, use 'ipv4', "
                "'ipv4-6', 'ipv6', 'ipv6-4'\n"
                "Error: 'NaN' is not a valid threshold value, use a "
                "non-negative integer\n"
                "Error: If crypto option 'cipher' is enabled, crypto option "
                "'hash' must be enabled as well\n"
                "Error: Errors have occurred, therefore pcs is unable to "
                "continue\n"
            ),
        )
        self.assertEqual(
            self.corosync_conf_file.read(),
            fixture_corosync_conf_minimal(),
        )
