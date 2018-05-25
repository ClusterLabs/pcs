from textwrap import dedent
from unittest import TestCase

from pcs.test.tools import fixture
from pcs.test.tools.command_env import get_env_tools
from pcs.test.tools.custom_mock import patch_getaddrinfo

from pcs import settings
from pcs.common import report_codes
from pcs.lib.commands import cluster


class AddNodesSuccessMinimal(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_corosync_conf_data(dedent("""\
            totem {
                version: 2
                cluster_name: myCluster
                transport: knet
            }

            nodelist {
                node {
                    ring0_addr: node1-corosync1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-corosync1
                    name: node2
                    nodeid: 2
                }

                node {
                    ring0_addr: node3-corosync1
                    name: node3
                    nodeid: 3
                }
            }

            quorum {
                provider: corosync_votequorum
            }

            logging {
                to_logfile: yes
                logfile: /var/log/cluster/corosync.log
                to_syslog: yes
            }
            """
        ))
        self.config.env.set_known_nodes(f"node{i}" for i in range(1, 5))
        patch_getaddrinfo(self, ["node4"])

    def test_minimal(self):
        (self.config
            .runner.systemctl.is_enabled("sbd", is_enabled=False)
            .runner.cib.load()
            .http.host.check_auth(
                communication_list=[
                    {"label": "node1"},
                    {"label": "node2"},
                    {"label": "node3"},
                ]
            )
            # SBD not installed
            .runner.systemctl.list_unit_files({})
            .http.host.get_host_info(
                communication_list=[
                    {"label": "node4"},
                ],
                output_data=dict(
                    services={
                        service: dict(
                            installed=True, enabled=False, running=False
                        ) for service in ("corosync", "pacemaker", "pcsd")
                    },
                    cluster_configuration_exists=False,
                ),
            )
            .http.host.update_known_hosts(
                communication_list=[
                    {"label": "node4"},
                ],
                to_add_hosts=["node1", "node2", "node3", "node4"]
            )
            .http.sbd.disable_sbd(
                communication_list=[
                    {"label": "node4"},
                ]
            )
            .fs.isfile(
                settings.corosync_authkey_file, return_value=False,
                name="fs.isfile.corosync_authkey"
            )
            .fs.isfile(
                settings.pacemaker_authkey_file, return_value=False,
                name="fs.isfile.pacemaker_authkey"
            )
            .fs.isfile(
                settings.pcsd_settings_conf_location, return_value=False,
                name="fs.isfile.pcsd_settings"
            )
            .http.corosync.set_corosync_conf(
                dedent("""\
                    totem {
                        version: 2
                        cluster_name: myCluster
                        transport: knet
                    }

                    nodelist {
                        node {
                            ring0_addr: node1-corosync1
                            name: node1
                            nodeid: 1
                        }

                        node {
                            ring0_addr: node2-corosync1
                            name: node2
                            nodeid: 2
                        }

                        node {
                            ring0_addr: node3-corosync1
                            name: node3
                            nodeid: 3
                        }

                        node {
                            ring0_addr: node4
                            name: node4
                            nodeid: 4
                        }
                    }

                    quorum {
                        provider: corosync_votequorum
                    }

                    logging {
                        to_logfile: yes
                        logfile: /var/log/cluster/corosync.log
                        to_syslog: yes
                    }
                    """
                ),
                communication_list=[
                    {"label": "node1"},
                    {"label": "node2"},
                    {"label": "node3"},
                    {"label": "node4"},
                ]
            )
            .http.corosync.reload_corosync_conf(
                communication_list=[
                    {"label": "node1"},
                ]
            )
        )

        cluster.add_nodes(
            self.env_assist.get_env(),
            [{"name": "node4"}]
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    report_codes.USING_KNOWN_HOST_ADDRESS_FOR_HOST,
                    host_name="node4",
                    address="node4"
                ),
                fixture.info(report_codes.SBD_DISABLING_STARTED),
                fixture.info(
                    report_codes.SERVICE_DISABLE_SUCCESS,
                    service="sbd",
                    node="node4",
                    instance=None,
                ),
                fixture.info(report_codes.COROSYNC_CONFIG_DISTRIBUTION_STARTED),
            ]
            +
            [
                fixture.info(
                    report_codes.COROSYNC_CONFIG_ACCEPTED_BY_NODE,
                    node=node
                ) for node in ["node1", "node2", "node3", "node4"]
            ]
        )
