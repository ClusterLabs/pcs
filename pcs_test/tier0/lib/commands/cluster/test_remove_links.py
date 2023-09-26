from textwrap import dedent
from unittest import TestCase

from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class RemoveLinks(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.before = dedent(
            """\
            totem {
                interface {
                    linknumber: 0
                    knet_transport: udp
                }
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    ring1_addr: node1-addr1
                    ring2_addr: node1-addr2
                    name: node1
                    nodeid: 1
                }

                node {
                    ring2_addr: node2-addr2
                    ring1_addr: node2-addr1
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }
            """
        )
        self.after = dedent(
            """\
            nodelist {
                node {
                    ring1_addr: node1-addr1
                    name: node1
                    nodeid: 1
                }

                node {
                    ring1_addr: node2-addr1
                    name: node2
                    nodeid: 2
                }
            }
            """
        )

    def test_success(self):
        (
            self.config.env.set_known_nodes(["node1", "node2"])
            .corosync_conf.load_content(self.before)
            .env.push_corosync_conf(corosync_conf_text=self.after)
        )

        cluster.remove_links(self.env_assist.get_env(), ["0", "2"])
        # Reports from pushing corosync.conf are produced in env. That code is
        # hidden in self.config.env.push_corosync_conf.
        self.env_assist.assert_reports([])

    def test_not_live(self):
        (
            self.config.env.set_known_nodes(
                ["node1", "node2"]
            ).env.set_corosync_conf_data(self.before)
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_links(self.env_assist.get_env(), ["0", "2"]),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=["COROSYNC_CONF"],
                ),
            ],
            expected_in_processor=False,
        )

    def test_validation(self):
        before = dedent(
            """\
            totem {
            }

            nodelist {
                node {
                    ring0_addr: node1-addr0
                    name: node1
                    nodeid: 1
                }

                node {
                    ring0_addr: node2-addr0
                    name: node2
                    nodeid: 2
                }
            }
            """
        )

        node_list = ["node1", "node2"]

        (
            self.config.env.set_known_nodes(
                node_list
            ).corosync_conf.load_content(before)
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_links(
                self.env_assist.get_env(), ["0", "0", "3", "abc"]
            ),
            [],
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COROSYNC_LINK_NUMBER_DUPLICATION,
                    link_number_list=["0"],
                ),
                fixture.error(
                    report_codes.COROSYNC_CANNOT_ADD_REMOVE_LINKS_TOO_MANY_FEW_LINKS,
                    links_change_count=1,
                    links_new_count=0,
                    links_limit_count=1,
                    add_or_not_remove=False,
                ),
                fixture.error(
                    report_codes.COROSYNC_LINK_DOES_NOT_EXIST_CANNOT_REMOVE,
                    link_list=sorted(["abc", "3"]),
                    existing_link_list=["0"],
                ),
            ]
        )
