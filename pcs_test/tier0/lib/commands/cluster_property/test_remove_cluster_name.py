import os
from unittest import TestCase

from pcs import settings
from pcs.common import reports
from pcs.lib.commands import cluster_property

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


class RemoveClusterName(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.runner_args = [
            settings.cibadmin_exec,
            "--delete-all",
            "--force",
            "--xpath=/cib/configuration/crm_config/cluster_property_set/nvpair[@name='cluster-name']",
        ]
        self.cib_path = os.path.join(settings.cib_dir, "cib.xml")
        self.runner_env = {"CIB_file": self.cib_path}

    def test_success(self):
        self.config.services.is_running("pacemaker", return_value=False)
        self.config.fs.exists(self.cib_path)
        self.config.runner.place(self.runner_args, env=self.runner_env)
        cluster_property.remove_cluster_name(self.env_assist.get_env())

    def test_pacemaker_running(self):
        self.config.services.is_running("pacemaker")
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.remove_cluster_name(
                self.env_assist.get_env()
            )
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.PACEMAKER_RUNNING)]
        )

    def test_no_cib_xml(self):
        self.config.services.is_running("pacemaker", return_value=False)
        self.config.fs.exists(self.cib_path, return_value=False)
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.remove_cluster_name(
                self.env_assist.get_env()
            )
        )
        self.env_assist.assert_reports(
            [fixture.error(reports.codes.CIB_XML_MISSING)]
        )

    def test_runner_failed(self):
        self.config.services.is_running("pacemaker", return_value=False)
        self.config.fs.exists(self.cib_path)
        self.config.runner.place(
            self.runner_args,
            env=self.runner_env,
            returncode=1,
            stdout="foo",
            stderr="bar",
        )
        self.env_assist.assert_raise_library_error(
            lambda: cluster_property.remove_cluster_name(
                self.env_assist.get_env()
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CIB_CLUSTER_NAME_REMOVAL_FAILED,
                    reason="bar\nfoo",
                )
            ]
        )
