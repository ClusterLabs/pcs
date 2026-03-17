from unittest import TestCase

from pcs.common import file_type_codes, reports
from pcs.lib.commands import cluster as lib

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


def _corosync_conf(
    node1_name, node2_name, node1_addr0=None, node1_addr1=None, node2_addr=None
):
    return f"""\
        totem {{
            version: 2
            cluster_name: test
            transport: udpu
        }}

        nodelist {{
            node {{
                ring0_addr: {node1_addr0 or "10.0.0.1"}
                ring1_addr: {node1_addr1 or "10.0.0.2"}
                nodeid: 1
                name: {node1_name}
            }}

            node {{
                ring0_addr: {node2_addr or "10.0.0.3"}
                nodeid: 2
                name: {node2_name}
            }}
        }}

        quorum {{
            provider: corosync_votequorum
        }}
    """


class RenameNodeCorosync(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.old_name = "node1"
        self.new_name = "node1-new"
        self.other_node = "node2"

    def push_corosync_conf(
        self,
        skip_offline_targets=False,
        node1_addr0=None,
        node1_addr1=None,
        node2_addr=None,
    ):
        self.config.env.push_corosync_conf(
            corosync_conf_text=_corosync_conf(
                self.new_name,
                self.other_node,
                node1_addr0=node1_addr0,
                node1_addr1=node1_addr1,
                node2_addr=node2_addr,
            ),
            skip_offline_targets=skip_offline_targets,
            need_stopped_cluster=True,
        )

    def load_corosync_conf(
        self,
        node1_name,
        node2_name,
        node1_addr0=None,
        node1_addr1=None,
        node2_addr=None,
    ):
        self.config.corosync_conf.load_content(
            _corosync_conf(
                node1_name,
                node2_name,
                node1_addr0,
                node1_addr1,
                node2_addr,
            )
        )

    def rename_node_corosync(self, old_name, new_name, force_flags=()):
        lib.rename_node_corosync(
            self.env_assist.get_env(),
            old_name,
            new_name,
            force_flags=force_flags,
        )

    def test_success(self):
        self.load_corosync_conf(self.old_name, self.other_node)
        self.push_corosync_conf(skip_offline_targets=True)
        self.rename_node_corosync(
            self.old_name,
            self.new_name,
            force_flags=[reports.codes.SKIP_OFFLINE_NODES],
        )
        self.env_assist.assert_reports([])

    def test_names_equal(self):
        self.env_assist.assert_raise_library_error(
            lambda: self.rename_node_corosync(self.old_name, self.old_name),
            [
                fixture.error(
                    reports.codes.NODE_RENAME_NAMES_EQUAL,
                    name=self.old_name,
                ),
            ],
            expected_in_processor=False,
        )

    def test_not_live_env_corosync(self):
        self.config.env.set_corosync_conf_data(
            _corosync_conf(self.old_name, self.other_node)
        )
        self.env_assist.assert_raise_library_error(
            lambda: self.rename_node_corosync(self.old_name, self.new_name),
            [
                fixture.error(
                    reports.codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=[file_type_codes.COROSYNC_CONF],
                ),
            ],
            expected_in_processor=False,
        )

    def test_corosync_conf_not_consistent_with_changes(self):
        self.load_corosync_conf(self.new_name, self.other_node)
        self.env_assist.assert_raise_library_error(
            lambda: self.rename_node_corosync(self.old_name, self.new_name),
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.COROSYNC_NODE_RENAME_NEW_NODE_ALREADY_EXISTS,
                    new_name=self.new_name,
                ),
                fixture.error(
                    reports.codes.COROSYNC_NODE_RENAME_OLD_NODE_NOT_FOUND,
                    old_name=self.old_name,
                ),
            ],
        )

    def test_warning_addr_matches_old_name_on_renamed_node(self):
        self.load_corosync_conf(
            self.old_name,
            self.other_node,
            node1_addr1=self.old_name,
            node2_addr=self.old_name,
        )
        self.push_corosync_conf(
            node1_addr1=self.old_name, node2_addr=self.old_name
        )
        self.rename_node_corosync(self.old_name, self.new_name)
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.COROSYNC_NODE_RENAME_ADDRS_MATCH_OLD_NAME,
                    old_name=self.old_name,
                    new_name=self.new_name,
                    node_addrs={
                        self.new_name: ["ring1_addr"],
                        self.other_node: ["ring0_addr"],
                    },
                ),
            ],
        )
