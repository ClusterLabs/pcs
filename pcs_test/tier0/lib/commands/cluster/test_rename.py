import os
from typing import Optional
from unittest import TestCase

from pcs import settings
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools

from .common import (
    corosync_conf_fixture,
    node_fixture,
)

_FIXTURE_NEW_NAME = "new"
_FIXTURE_GFS2_INVALID_NAME = "a.b"

_FIXTURE_GENERIC_FS_RESOURCE = """
    <primitive id="FS" class="ocf" provider="heartbeat" type="Filesystem">
        <instance_attributes id="fs-instance_attributes">
            <nvpair id="fs-fstype" name="fstype" value="xfs"/>
            <nvpair id="bogus" name="attribute" value="gfs2"/>
        </instance_attributes>
    </primitive>
"""

_FIXTURE_GFS2_FS_RESOURCE = """
    <primitive id="GFS" class="ocf" provider="heartbeat" type="Filesystem">
        <instance_attributes id="fs-instance_attributes">
            <nvpair id="gfs-fstype" name="fstype" value="gfs2"/>
        </instance_attributes>
    </primitive>
"""

_FIXTURE_DLM_RESOURCE = """
    <primitive id="D" class="ocf" provider="pacemaker" type="controld"/>
"""


class CorosyncFixtureMixin:
    @staticmethod
    def fixture_corosync_conf(cluster_name: Optional[str] = None) -> str:
        return corosync_conf_fixture(
            node_list=[node_fixture("node", 1)], cluster_name=cluster_name
        )


class RenameCluster(CorosyncFixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.cib_path = os.path.join(settings.cib_dir, "cib.xml")
        self.runner_env = {"CIB_file": self.cib_path}

    def test_success(self):
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.fixture_corosync_conf(_FIXTURE_NEW_NAME),
            need_stopped_cluster=True,
        )
        cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)

    def test_no_cib(self):
        self.config.fs.exists(self.cib_path, False)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.fixture_corosync_conf(_FIXTURE_NEW_NAME),
            need_stopped_cluster=True,
        )
        cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)

    def test_invalid_name(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), "")
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.INVALID_OPTION_VALUE,
                    option_name="cluster name",
                    option_value="",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ]
        )

    def test_gfs2_invalid_name(self):
        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(
                self.env_assist.get_env(), _FIXTURE_GFS2_INVALID_NAME
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    report_codes.COROSYNC_CLUSTER_NAME_INVALID_FOR_GFS2,
                    force_code=report_codes.FORCE,
                    cluster_name=_FIXTURE_GFS2_INVALID_NAME,
                    max_length=32,
                    allowed_characters="a-z A-Z 0-9 _-",
                )
            ]
        )

    def test_gfs2_invalid_name_forced(self):
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.fixture_corosync_conf(
                _FIXTURE_GFS2_INVALID_NAME
            ),
            need_stopped_cluster=True,
        )
        cluster.rename(
            self.env_assist.get_env(),
            _FIXTURE_GFS2_INVALID_NAME,
            force_flags=[report_codes.FORCE],
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(
                    report_codes.COROSYNC_CLUSTER_NAME_INVALID_FOR_GFS2,
                    cluster_name=_FIXTURE_GFS2_INVALID_NAME,
                    max_length=32,
                    allowed_characters="a-z A-Z 0-9 _-",
                )
            ]
        )

    def test_skip_offline(self):
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.fixture_corosync_conf(_FIXTURE_NEW_NAME),
            need_stopped_cluster=True,
            skip_offline_targets=True,
        )
        cluster.rename(
            self.env_assist.get_env(),
            _FIXTURE_NEW_NAME,
            force_flags=[report_codes.SKIP_OFFLINE_NODES],
        )


class ClusterRenameCheckGfs2Resources(CorosyncFixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.cib_path = os.path.join(settings.cib_dir, "cib.xml")
        self.runner_env = {"CIB_file": self.cib_path}

    def fixture_env(self, resources):
        self.config.runner.cib.load(
            filename="cib-empty.xml",
            env=self.runner_env,
            resources=resources,
        )
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.fixture_corosync_conf(_FIXTURE_NEW_NAME),
            need_stopped_cluster=True,
        )

    def test_no_gfs2_in_cib(self):
        self.fixture_env(
            f"<resources>{_FIXTURE_GENERIC_FS_RESOURCE}</resources>"
        )
        cluster.rename(
            self.env_assist.get_env(), _FIXTURE_NEW_NAME, force_flags=[]
        )

    def test_gfs2_in_cib(self):
        self.fixture_env(f"<resources>{_FIXTURE_GFS2_FS_RESOURCE}</resources>")
        cluster.rename(
            self.env_assist.get_env(), _FIXTURE_NEW_NAME, force_flags=[]
        )
        self.env_assist.assert_reports(
            [fixture.warn(report_codes.GFS2_LOCK_TABLE_RENAME_NEEDED)]
        )

    def test_gfs2_cloned_in_cib(self):
        self.fixture_env(
            f"""
                <resources>
                    <clone id="fs-clone">
                        {_FIXTURE_GFS2_FS_RESOURCE}
                    </clone>
                </resources>
            """
        )
        cluster.rename(
            self.env_assist.get_env(), _FIXTURE_NEW_NAME, force_flags=[]
        )
        self.env_assist.assert_reports(
            [fixture.warn(report_codes.GFS2_LOCK_TABLE_RENAME_NEEDED)]
        )

    def test_dlm_in_cib(self):
        self.fixture_env(f"<resources>{_FIXTURE_DLM_RESOURCE}</resources>")
        cluster.rename(
            self.env_assist.get_env(), _FIXTURE_NEW_NAME, force_flags=[]
        )
        self.env_assist.assert_reports(
            [fixture.warn(report_codes.DLM_CLUSTER_RENAME_NEEDED)]
        )

    def test_dlm_cloned_in_cib(self):
        self.fixture_env(
            f"""
                <resources>
                    <clone id="dlm-clone">
                        {_FIXTURE_DLM_RESOURCE}
                    </clone>
                </resources>
            """
        )
        cluster.rename(
            self.env_assist.get_env(), _FIXTURE_NEW_NAME, force_flags=[]
        )
        self.env_assist.assert_reports(
            [fixture.warn(report_codes.DLM_CLUSTER_RENAME_NEEDED)]
        )

    def test_dlm_and_gfs2(self):
        self.fixture_env(
            f"""
                <resources>
                    {_FIXTURE_GFS2_FS_RESOURCE}
                    {_FIXTURE_DLM_RESOURCE}
                </resources>
            """
        )
        cluster.rename(
            self.env_assist.get_env(), _FIXTURE_NEW_NAME, force_flags=[]
        )
        self.env_assist.assert_reports(
            [
                fixture.warn(report_codes.DLM_CLUSTER_RENAME_NEEDED),
                fixture.warn(report_codes.GFS2_LOCK_TABLE_RENAME_NEEDED),
            ]
        )
