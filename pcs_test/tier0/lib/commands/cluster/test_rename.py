import json
import os
from typing import Optional
from unittest import TestCase

from pcs import settings
from pcs.common import reports
from pcs.common.reports import codes as report_codes
from pcs.lib.commands import cluster

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.command_env.config_http_corosync import (
    corosync_running_check_response,
)

from .common import corosync_conf_fixture, node_fixture

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


class FixtureMixin:
    node_labels = ["node-1", "node-2"]

    @staticmethod
    def fixture_corosync_conf(cluster_name: Optional[str] = None) -> str:
        return corosync_conf_fixture(
            node_list=[node_fixture("node-1", 1), node_fixture("node-2", 2)],
            cluster_name=cluster_name,
        )

    def fixture_remove_name_prop_call(
        self, communication_list=None, output=None
    ):
        self.config.http.place_multinode_call(
            "cluster.remove-name",
            communication_list=(
                communication_list
                if communication_list
                else [{"label": node} for node in self.node_labels]
            ),
            action="api/v1/cluster-property-remove-name/v1",
            raw_data=json.dumps({}),
            output=(
                output
                if output
                else json.dumps(
                    {
                        "status": "success",
                        "status_msg": None,
                        "report_list": [],
                        "data": "",
                    }
                )
            ),
        )

    def fixture_corosync_offline_check_reports(self):
        reports = [
            fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED)
        ]
        reports.extend(
            fixture.info(
                report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED, node=n
            )
            for n in self.node_labels
        )
        return reports

    def fixture_remove_name_prop_reports(self):
        reports = [fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVAL_STARTED)]
        reports.extend(
            fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVED, node=n)
            for n in self.node_labels
        )
        return reports

    def _offline_node_communication_list(self):
        return [
            {
                "label": self.node_labels[0],
                "response_code": 400,
                "output": "Fail",
            }
        ] + [{"label": node} for node in self.node_labels[1:]]


class RenameCluster(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.cib_path = os.path.join(settings.cib_dir, "cib.xml")
        self.runner_env = {"CIB_file": self.cib_path}
        self.config.env.set_known_nodes(self.node_labels)

    def test_success(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call()
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.fixture_corosync_conf(_FIXTURE_NEW_NAME),
            need_stopped_cluster=True,
        )

        cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
        )

    def test_no_cib(self):
        self.config.fs.exists(self.cib_path, False)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call()
        self.config.env.push_corosync_conf(
            corosync_conf_text=self.fixture_corosync_conf(_FIXTURE_NEW_NAME),
            need_stopped_cluster=True,
        )

        cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
        )

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
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call()
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
            + self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
        )

    def test_node_offline_corosync_check(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(
            communication_list=self._offline_node_communication_list()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        )
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_labels[0],
                    command="remote/status",
                    reason="Fail",
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                ),
                fixture.error(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node=self.node_labels[0],
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                ),
                fixture.info(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=self.node_labels[1],
                ),
            ]
        )

    def test_node_offline_property_removal(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call(
            communication_list=self._offline_node_communication_list()
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        )
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + [
                fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVAL_STARTED),
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_labels[0],
                    command="api/v1/cluster-property-remove-name/v1",
                    reason="Fail",
                    force_code=report_codes.SKIP_OFFLINE_NODES,
                ),
                fixture.info(
                    report_codes.CIB_CLUSTER_NAME_REMOVED,
                    node=self.node_labels[1],
                ),
            ]
        )

    def test_skip_offline(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(
            communication_list=self._offline_node_communication_list()
        )
        self.fixture_remove_name_prop_call(
            communication_list=self._offline_node_communication_list()
        )
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
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_labels[0],
                    command="remote/status",
                    reason="Fail",
                ),
                fixture.warn(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_ERROR,
                    node=self.node_labels[0],
                ),
                fixture.info(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=self.node_labels[1],
                ),
                fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVAL_STARTED),
                fixture.warn(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=self.node_labels[0],
                    command="api/v1/cluster-property-remove-name/v1",
                    reason="Fail",
                ),
                fixture.info(
                    report_codes.CIB_CLUSTER_NAME_REMOVED,
                    node=self.node_labels[1],
                ),
            ]
        )

    def test_cluster_name_property_remove_invalid_response(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call(output="Invalid json")

        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        )
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + [
                fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVAL_STARTED),
            ]
            + [
                fixture.error(report_codes.INVALID_RESPONSE_FORMAT, node=n)
                for n in self.node_labels
            ]
        )

    def test_cluster_name_property_remove_error_report(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call(
            output=json.dumps(
                {
                    "status": "error",
                    "status_msg": None,
                    "report_list": [
                        {
                            "severity": {"level": "ERROR", "force_code": None},
                            "message": {
                                "code": "CIB_XML_MISSING",
                                "message": "CIB XML file cannot be found",
                                "payload": {},
                            },
                            "context": None,
                        }
                    ],
                    "data": "",
                }
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        )
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + [
                fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVAL_STARTED),
            ]
            + [
                fixture.error(
                    report_codes.CIB_XML_MISSING,
                    context=reports.dto.ReportItemContextDto(node=n),
                )
                for n in self.node_labels
            ]
        )

    def test_cluster_name_property_remove_error_status_msg(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call(
            output=json.dumps(
                {
                    "status": "error",
                    "status_msg": "very bad error",
                    "report_list": [],
                    "data": "",
                }
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        )
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + [
                fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVAL_STARTED),
            ]
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=n,
                    command="api/v1/cluster-property-remove-name/v1",
                    reason="very bad error",
                )
                for n in self.node_labels
            ]
        )

    def test_cluster_name_property_remove_error_report_status_msg(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call(
            output=json.dumps(
                {
                    "status": "error",
                    "status_msg": "very bad error",
                    "report_list": [
                        {
                            "severity": {"level": "ERROR", "force_code": None},
                            "message": {
                                "code": "CIB_XML_MISSING",
                                "message": "CIB XML file cannot be found",
                                "payload": {},
                            },
                            "context": None,
                        }
                    ],
                    "data": "",
                }
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        )
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + [
                fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVAL_STARTED),
            ]
            + [
                fixture.error(
                    report_codes.CIB_XML_MISSING,
                    context=reports.dto.ReportItemContextDto(node=n),
                )
                for n in self.node_labels
            ]
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=n,
                    command="api/v1/cluster-property-remove-name/v1",
                    reason="very bad error",
                )
                for n in self.node_labels
            ]
        )

    def test_cluster_name_property_remove_error_no_report_no_message(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call(
            output=json.dumps(
                {
                    "status": "error",
                    "status_msg": None,
                    "report_list": [],
                    "data": "",
                }
            )
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        )
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + [
                fixture.info(report_codes.CIB_CLUSTER_NAME_REMOVAL_STARTED),
            ]
            + [
                fixture.error(
                    report_codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node=n,
                    command="api/v1/cluster-property-remove-name/v1",
                    reason="Unknown error",
                )
                for n in self.node_labels
            ]
        )

    def test_corosync_running_on_node(self):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(env=self.runner_env)
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.http.corosync.check_corosync_offline(
            communication_list=[
                {
                    "label": self.node_labels[0],
                    "output": corosync_running_check_response(True),
                }
            ]
            + [{"label": node} for node in self.node_labels[1:]]
        )

        self.env_assist.assert_raise_library_error(
            lambda: cluster.rename(self.env_assist.get_env(), _FIXTURE_NEW_NAME)
        )
        self.env_assist.assert_reports(
            [
                fixture.info(report_codes.COROSYNC_NOT_RUNNING_CHECK_STARTED),
                fixture.error(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_RUNNING,
                    node=self.node_labels[0],
                ),
                fixture.info(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_NODE_STOPPED,
                    node=self.node_labels[1],
                ),
                fixture.error(
                    report_codes.COROSYNC_NOT_RUNNING_CHECK_FINISHED_RUNNING,
                    node_list=[self.node_labels[0]],
                ),
            ]
        )


class ClusterRenameCheckGfs2Resources(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.cib_path = os.path.join(settings.cib_dir, "cib.xml")
        self.runner_env = {"CIB_file": self.cib_path}

    def fixture_env(self, resources):
        self.config.fs.exists(self.cib_path, return_value=True)
        self.config.runner.cib.load(
            filename="cib-empty.xml",
            env=self.runner_env,
            resources=resources,
        )
        self.config.corosync_conf.load_content(self.fixture_corosync_conf())
        self.config.env.set_known_nodes(self.node_labels)
        self.config.http.corosync.check_corosync_offline(self.node_labels)
        self.fixture_remove_name_prop_call()
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
        self.env_assist.assert_reports(
            self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
        )

    def test_gfs2_in_cib(self):
        self.fixture_env(f"<resources>{_FIXTURE_GFS2_FS_RESOURCE}</resources>")
        cluster.rename(
            self.env_assist.get_env(), _FIXTURE_NEW_NAME, force_flags=[]
        )
        self.env_assist.assert_reports(
            [fixture.warn(report_codes.GFS2_LOCK_TABLE_RENAME_NEEDED)]
            + self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
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
            + self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
        )

    def test_dlm_in_cib(self):
        self.fixture_env(f"<resources>{_FIXTURE_DLM_RESOURCE}</resources>")
        cluster.rename(
            self.env_assist.get_env(), _FIXTURE_NEW_NAME, force_flags=[]
        )
        self.env_assist.assert_reports(
            [fixture.warn(report_codes.DLM_CLUSTER_RENAME_NEEDED)]
            + self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
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
            + self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
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
            + self.fixture_corosync_offline_check_reports()
            + self.fixture_remove_name_prop_reports()
        )
