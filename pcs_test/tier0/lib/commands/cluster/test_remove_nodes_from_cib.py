import os.path
from unittest import TestCase

from pcs import settings
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class SuccessMinimal(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.nodes = [f"node{i}" for i in range(3)]

    def test_live_cib_required(self):
        self.config.env.set_cib_data("<cib />")
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes_from_cib(
                self.env_assist.get_env(),
                self.nodes,
            ),
            [
                fixture.error(
                    report_codes.LIVE_ENVIRONMENT_REQUIRED,
                    forbidden_options=["CIB"],
                )
            ],
            expected_in_processor=False,
        )

    def test_success_pcmk_running(self):
        self.config.services.is_running("pacemaker")
        for node in self.nodes:
            self.config.runner.pcmk.remove_node(
                node,
                name=f"remove_node.{node}",
            )
        cluster.remove_nodes_from_cib(self.env_assist.get_env(), self.nodes)

    def test_failure_pcmk_running(self):
        err_msg = "an error"
        self.config.services.is_running("pacemaker")
        self.config.runner.pcmk.remove_node(
            self.nodes[0],
        )
        self.config.runner.pcmk.remove_node(
            self.nodes[1],
            returncode=1,
            stderr=err_msg,
            name="remove_node_failure",
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes_from_cib(
                self.env_assist.get_env(),
                self.nodes,
            ),
            [
                fixture.error(
                    report_codes.NODE_REMOVE_IN_PACEMAKER_FAILED,
                    node_list_to_remove=[self.nodes[1]],
                    node="",
                    reason=err_msg,
                )
            ],
            expected_in_processor=False,
        )

    def test_success_pcmk_not_running(self):
        cmd_env = dict(CIB_file=os.path.join(settings.cib_dir, "cib.xml"))
        self.config.services.is_running("pacemaker", return_value=False)
        for node in self.nodes:
            self.config.runner.place(
                [
                    settings.cibadmin_exec,
                    "--delete-all",
                    "--force",
                    f"--xpath=/cib/configuration/nodes/node[@uname='{node}']",
                ],
                name=f"remove_node.{node}",
                env=cmd_env,
            )
        cluster.remove_nodes_from_cib(self.env_assist.get_env(), self.nodes)

    def test_failure_pcmk_not_running(self):
        err_msg = "an error"
        cmd_env = dict(CIB_file=os.path.join(settings.cib_dir, "cib.xml"))
        cmd = [settings.cibadmin_exec, "--delete-all", "--force"]
        cmd_xpath = "--xpath=/cib/configuration/nodes/node[@uname='{}']"
        self.config.services.is_running("pacemaker", return_value=False)
        self.config.runner.place(
            cmd + [cmd_xpath.format(self.nodes[0])],
            name="remove_node_success",
            env=cmd_env,
        )
        self.config.runner.place(
            cmd + [cmd_xpath.format(self.nodes[1])],
            returncode=1,
            stderr=err_msg,
            name="remove_node_failure",
            env=cmd_env,
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster.remove_nodes_from_cib(
                self.env_assist.get_env(),
                self.nodes,
            ),
            [
                fixture.error(
                    report_codes.NODE_REMOVE_IN_PACEMAKER_FAILED,
                    node_list_to_remove=[self.nodes[1]],
                    node="",
                    reason=err_msg,
                )
            ],
            expected_in_processor=False,
        )
