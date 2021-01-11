import json

from textwrap import dedent
from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import (
    get_tmp_file,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner

from .common import fixture_corosync_conf_minimal


class ClusterConfigMixin(AssertPcsMixin):
    # pylint: disable=invalid-name
    command = None

    @staticmethod
    def fixture_text_output():
        return dedent(
            """\
            Cluster Name: cluster_name
            Transport: knet
            Nodes:
              node1:
                Link 0 address: node1_addr
                nodeid: 1
              node2:
                Link 0 address: node2_addr
                nodeid: 2
            Transport Options:
              ip_version: ipv6
            Crypto Options:
              cipher: aes256
              hash: sha256
          """
        )

    @staticmethod
    def fixture_json_output():
        return (
            json.dumps(
                {
                    "cluster_name": "cluster_name",
                    "transport": "KNET",
                    "totem_options": {},
                    "transport_options": {"ip_version": "ipv6"},
                    "compression_options": {},
                    "crypto_options": {"cipher": "aes256", "hash": "sha256"},
                    "nodes": [
                        {
                            "name": "node1",
                            "nodeid": "1",
                            "addrs": [
                                {
                                    "addr": "node1_addr",
                                    "link": "0",
                                    "type": "FQDN",
                                }
                            ],
                        },
                        {
                            "name": "node2",
                            "nodeid": "2",
                            "addrs": [
                                {
                                    "addr": "node2_addr",
                                    "link": "0",
                                    "type": "FQDN",
                                }
                            ],
                        },
                    ],
                    "links_options": {},
                    "quorum_options": {},
                    "quorum_device": None,
                }
            )
            + "\n"
        )

    @staticmethod
    def fixture_cmd_output():
        return dedent(
            """\
            pcs cluster setup cluster_name \\
              node1 addr=node1_addr \\
              node2 addr=node2_addr \\
              transport \\
              knet \\
                  ip_version=ipv6 \\
                crypto \\
                  cipher=aes256 \\
                  hash=sha256
            """
        )

    def setUp(self):
        self.corosync_conf_file = get_tmp_file(
            "tier1_cluster_config_show_corosync.conf"
        )
        self.pcs_runner = PcsRunner(
            cib_file=None,
            corosync_conf_opt=self.corosync_conf_file.name,
        )
        write_data_to_tmpfile(
            fixture_corosync_conf_minimal(), self.corosync_conf_file
        )

    def tearDown(self):
        self.corosync_conf_file.close()

    def test_default_output(self):
        self.assert_pcs_success(
            self.command.split(),
            stdout_full=self.fixture_text_output(),
        )

    def test_text_output(self):
        self.assert_pcs_success(
            (self.command + " --output-format=text").split(),
            stdout_full=self.fixture_text_output(),
        )

    def test_json_output(self):
        self.assert_pcs_success(
            (self.command + " --output-format=json").split(),
            stdout_full=self.fixture_json_output(),
        )

    def test_cmd_output(self):
        self.assert_pcs_success(
            (self.command + " --output-format=cmd").split(),
            stdout_full=self.fixture_cmd_output(),
        )

    def test_output_format_unsupported_value(self):
        self.assert_pcs_fail(
            (self.command + " --output-format=xml").split(),
            stdout_full=(
                "Error: Unknown value 'xml' for '--output-format' option. "
                "Supported values are: 'cmd', 'json', 'text'\n"
            ),
        )

    def test_unsupported_option(self):
        self.assert_pcs_fail(
            (self.command + " --corosync").split(),
            stdout_full=dedent(
                """\
                Error: Specified option '--corosync' is not supported in this command
                """
            ),
        )


class ClusterConfig(ClusterConfigMixin, TestCase):
    command = "cluster config"


class ClusterConfigShow(ClusterConfigMixin, TestCase):
    command = "cluster config show"
