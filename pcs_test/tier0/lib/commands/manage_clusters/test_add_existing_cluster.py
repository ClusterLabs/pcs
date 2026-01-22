import json
from typing import Literal
from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.host import Destination, PcsKnownHost
from pcs.lib.commands import manage_clusters
from pcs.lib.permissions.config.types import ClusterEntry

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.fixture_pcs_cfgsync import (
    fixture_known_hosts_file_content,
    fixture_pcs_settings_file_content,
    fixture_save_sync_new_known_hosts_conflict,
    fixture_save_sync_new_known_hosts_error,
    fixture_save_sync_new_known_hosts_success,
    fixture_save_sync_new_version_conflict,
    fixture_save_sync_new_version_error,
    fixture_save_sync_new_version_success,
)


class AddExistingClusterBasicErrors(TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3"])

    def test_cannot_get_cluster_info(self):
        self.config.http.status.get_cluster_info_from_status(
            communication_list=[
                dict(
                    label="node1",
                    response_code=400,
                    output="Unable to fetch",
                )
            ],
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="node1",
                    command="remote/status",
                    reason="Unable to fetch",
                ),
                fixture.error(
                    reports.codes.UNABLE_TO_GET_CLUSTER_INFO_FROM_STATUS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
            ]
        )

    def test_invalid_cluster_info_format(self):
        self.config.http.status.get_cluster_info_from_status(
            communication_list=[dict(label="node1", output="Bad format")],
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_RESPONSE_FORMAT, node="node1"
                ),
                fixture.error(
                    reports.codes.UNABLE_TO_GET_CLUSTER_INFO_FROM_STATUS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
            ]
        )

    def test_target_node_not_in_cluster(self):
        self.config.http.status.get_cluster_info_from_status(
            node_labels=["node1"], cluster_name=""
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.NODE_NOT_IN_CLUSTER,
                    context=reports.dto.ReportItemContextDto("node1"),
                )
            ]
        )

    def test_cannot_read_pcs_settings_conf(self):
        self.config.http.status.get_cluster_info_from_status(
            node_labels=["node1"], cluster_name="cluster"
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    operation="read",
                    reason="Something bad",
                    file_path=settings.pcsd_settings_conf_location,
                )
            ]
        )

    def test_cluster_name_is_already_used(self):
        self.config.http.status.get_cluster_info_from_status(
            node_labels=["node1"], cluster_name="cluster"
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(
                clusters=[ClusterEntry("cluster", nodes=[])]
            ),
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CLUSTER_NAME_ALREADY_IN_USE,
                    cluster_name="cluster",
                )
            ]
        )


class FixtureMixin:
    LOCAL_CLUSTERS = [ClusterEntry("local", ["a", "b"])]
    REMOTE_CLUSTERS = [ClusterEntry("cluster", ["m", "n", "x", "y"])]

    def fixture_expected_pcs_settings_file_content(self) -> str:
        return fixture_pcs_settings_file_content(
            data_version=2, clusters=self.LOCAL_CLUSTERS + self.REMOTE_CLUSTERS
        )

    LOCAL_KNOWN_HOSTS = {"node1": PcsKnownHost("node1", "TOKEN", dest_list=[])}
    REMOTE_KNOWN_HOSTS = {
        "node5": PcsKnownHost(
            "node5", "TOKEN1", dest_list=[Destination("123", 456)]
        ),
        "node6": PcsKnownHost(
            "node6", "TOKEN2", dest_list=[Destination("abc", 2222)]
        ),
    }

    EXPECTED_KNOWN_HOSTS = LOCAL_KNOWN_HOSTS | REMOTE_KNOWN_HOSTS

    def fixture_get_cluster_info(
        self,
        new_hosts_mode: Literal["error", "bad_format", "success"] = "success",
        new_hosts=REMOTE_KNOWN_HOSTS,
        pcs_settings_exists=True,
        corosync_conf_exists=True,
    ):
        self.config.http.status.get_cluster_info_from_status(
            node_labels=["node1"],
            cluster_name="cluster",
            corosync_online_nodes=["m", "n"],
            corosync_offline_nodes=["x", "y"],
        )
        if pcs_settings_exists:
            self.config.raw_file.exists(
                file_type_codes.PCS_SETTINGS_CONF,
                settings.pcsd_settings_conf_location,
                name="raw_file.exists.pcs_settings",
            )
            self.config.raw_file.read(
                file_type_codes.PCS_SETTINGS_CONF,
                settings.pcsd_settings_conf_location,
                content=fixture_pcs_settings_file_content(
                    data_version=1, clusters=self.LOCAL_CLUSTERS
                ),
            )
        else:
            self.config.raw_file.exists(
                file_type_codes.PCS_SETTINGS_CONF,
                settings.pcsd_settings_conf_location,
                exists=False,
                name="raw_file.exists.pcs_settings",
            )

        if new_hosts_mode == "success":
            self.config.http.place_multinode_call(
                node_labels=["node1"],
                action="remote/get_cluster_known_hosts",
                param_list=[],
                output=json.dumps(
                    dict(
                        host.to_known_host_dict() for host in new_hosts.values()
                    )
                ),
                name="get_cluster_known_hosts",
            )
        elif new_hosts_mode == "error":
            self.config.http.place_multinode_call(
                action="remote/get_cluster_known_hosts",
                communication_list=[
                    dict(
                        label="node1",
                        response_code=400,
                        output="Unable to fetch",
                    )
                ],
                param_list=[],
                name="get_cluster_known_hosts",
                output="",
            )
        else:
            self.config.http.place_multinode_call(
                node_labels=["node1"],
                action="remote/get_cluster_known_hosts",
                param_list=[],
                output=json.dumps({"foo": "bar"}),
                name="get_cluster_known_hosts",
            )

        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=corosync_conf_exists,
            name="raw_file.exists.corosync_conf",
        )
        if corosync_conf_exists:
            self.config.corosync_conf.load(["node1", "node2", "node3"])


class AddExistingClusterLocalNodeNotInCluster(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3"])

    def test_success_no_new_hosts(self):
        self.fixture_get_cluster_info(new_hosts={}, corosync_conf_exists=False)
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            self.fixture_expected_pcs_settings_file_content().encode(),
            can_overwrite=True,
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

    def test_success_error_getting_known_hosts_from_node(self):
        self.fixture_get_cluster_info(
            new_hosts_mode="error", corosync_conf_exists=False
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            self.fixture_expected_pcs_settings_file_content().encode(),
            can_overwrite=True,
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.NODE_COMMUNICATION_COMMAND_UNSUCCESSFUL,
                    node="node1",
                    command="remote/get_cluster_known_hosts",
                    reason="Unable to fetch",
                ),
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_CLUSTER_KNOWN_HOSTS,
                    cluster_name="cluster",
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
            ]
        )

    def test_success_invalid_get_cluster_known_hosts_response(self):
        self.fixture_get_cluster_info(
            new_hosts_mode="bad_format", corosync_conf_exists=False
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            self.fixture_expected_pcs_settings_file_content().encode(),
            can_overwrite=True,
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

        self.env_assist.assert_reports(
            [
                fixture.warn(
                    reports.codes.INVALID_RESPONSE_FORMAT, node="node1"
                ),
                fixture.warn(
                    reports.codes.UNABLE_TO_GET_CLUSTER_KNOWN_HOSTS,
                    cluster_name="cluster",
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
            ]
        )

    def test_success_new_hosts(self):
        known_hosts = {"node1": PcsKnownHost("node1", "TOKEN", dest_list=[])}

        self.fixture_get_cluster_info(corosync_conf_exists=False)
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=1, known_hosts=known_hosts
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=2, known_hosts=self.EXPECTED_KNOWN_HOSTS
            ).encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            self.fixture_expected_pcs_settings_file_content().encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_settings_conf",
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

    def test_no_new_hosts_error_writing_settings_file(self):
        self.fixture_get_cluster_info(new_hosts={}, corosync_conf_exists=False)
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            self.fixture_expected_pcs_settings_file_content().encode(),
            can_overwrite=True,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    operation="write",
                    reason="Something bad",
                    file_path=settings.pcsd_settings_conf_location,
                )
            ]
        )

    def test_new_hosts_error_writing_known_hosts(self):
        known_hosts = {"node1": PcsKnownHost("node1", "TOKEN", dest_list=[])}

        self.fixture_get_cluster_info(corosync_conf_exists=False)
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=1, known_hosts=known_hosts
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=2, known_hosts=self.EXPECTED_KNOWN_HOSTS
            ).encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_known_hosts",
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="Something bad",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ]
        )

    def test_success_files_did_not_exist(self):
        self.fixture_get_cluster_info(
            pcs_settings_exists=False, corosync_conf_exists=False
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            exists=False,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=1, known_hosts=self.REMOTE_KNOWN_HOSTS
            ).encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                data_version=1, clusters=self.REMOTE_CLUSTERS
            ).encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_settings_conf",
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

    def test_error_reading_known_hosts_file(self):
        self.fixture_get_cluster_info(corosync_conf_exists=False)
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            exception_msg="Something bad",
            name="raw_file.read.pcs_known_hosts",
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    operation="read",
                    reason="Something bad",
                    file_path=settings.pcsd_known_hosts_location,
                )
            ]
        )


class AddExistingClusterLocalNodeInCluster(FixtureMixin, TestCase):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3"])

    def fixture_cfgsync_send_files_reports(
        self,
        file_type: file_type_codes.FileTypeCode,
        expected_result: Literal["ok", "conflict", "error"] = "ok",
        conflict_is_error: bool = True,
    ):
        _report_code_map = {
            "ok": reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
            "conflict": reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
            "error": reports.codes.PCS_CFGSYNC_CONFIG_SAVE_ERROR,
        }

        first_node_report = (
            fixture.error(
                _report_code_map[expected_result],
                file_type_code=file_type,
                context=reports.dto.ReportItemContextDto("node1"),
            )
            if expected_result == "error"
            or (expected_result == "conflict" and conflict_is_error)
            else fixture.info(
                _report_code_map[expected_result],
                file_type_code=file_type,
                context=reports.dto.ReportItemContextDto("node1"),
            )
        )

        report_list = [
            fixture.info(
                reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                file_type_code_list=[file_type],
                node_name_list=["node1", "node2", "node3"],
            ),
            first_node_report,
        ] + [
            fixture.info(
                reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                file_type_code=file_type,
                context=reports.dto.ReportItemContextDto(node),
            )
            for node in ["node2", "node3"]
        ]
        if expected_result == "conflict":
            return report_list + [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[file_type],
                    node_name_list=["node1", "node2", "node3"],
                )
            ]
        return report_list

    def test_success_no_new_hosts(self):
        self.fixture_get_cluster_info(new_hosts={})
        fixture_save_sync_new_version_success(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: self.fixture_expected_pcs_settings_file_content()
            },
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

        self.env_assist.assert_reports(
            self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF
            )
        )

    def test_success_new_hosts(self):
        self.fixture_get_cluster_info()
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=1, known_hosts=self.LOCAL_KNOWN_HOSTS
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        fixture_save_sync_new_known_hosts_success(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_data_version=2,
            known_hosts=self.EXPECTED_KNOWN_HOSTS,
        )
        fixture_save_sync_new_version_success(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: self.fixture_expected_pcs_settings_file_content()
            },
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

        self.env_assist.assert_reports(
            self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_KNOWN_HOSTS
            )
            + self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF
            )
        )

    def test_conflict_syncing_pcs_settings_file(self):
        self.fixture_get_cluster_info(new_hosts={})
        remote_file = fixture_pcs_settings_file_content(
            data_version=99, clusters=self.LOCAL_CLUSTERS
        )
        fixture_save_sync_new_version_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=self.fixture_expected_pcs_settings_file_content(),
            fetch_after_conflict=True,
            remote_file_content=remote_file,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            can_overwrite=True,
            file_data=remote_file.encode(),
            name="after_fetch.write",
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                expected_result="conflict",
            )
            + [
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
        )

    def test_conflict_syncing_pcs_settings_file_error_writing(self):
        self.fixture_get_cluster_info(new_hosts={})
        remote_file = fixture_pcs_settings_file_content(
            data_version=99, clusters=self.LOCAL_CLUSTERS
        )
        fixture_save_sync_new_version_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=self.fixture_expected_pcs_settings_file_content(),
            fetch_after_conflict=True,
            remote_file_content=remote_file,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            can_overwrite=True,
            file_data=remote_file.encode(),
            exception_msg="Something bad",
            name="after_fetch.write",
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                expected_result="conflict",
            )
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    operation="write",
                    reason="Something bad",
                    file_path=settings.pcsd_settings_conf_location,
                ),
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
        )

    def test_error_syncing_pcs_settings_file(self):
        self.fixture_get_cluster_info(new_hosts={})
        fixture_save_sync_new_version_error(
            self.config,
            node_labels=["node1", "node2", "node3"],
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=self.fixture_expected_pcs_settings_file_content(),
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                expected_result="error",
            )
            + [
                fixture.error(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILED,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1"],
                ),
            ]
        )

    def test_conflict_syncing_known_hosts_file(self):
        self.fixture_get_cluster_info()
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=1, known_hosts=self.LOCAL_KNOWN_HOSTS
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        new_file = fixture_save_sync_new_known_hosts_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            initial_local_known_hosts=self.LOCAL_KNOWN_HOSTS,
            new_hosts=self.REMOTE_KNOWN_HOSTS,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=new_file.encode(),
            can_overwrite=True,
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_KNOWN_HOSTS,
                expected_result="conflict",
                conflict_is_error=False,
            )
            + self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_KNOWN_HOSTS,
                expected_result="conflict",
                conflict_is_error=True,
            )
            + [
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
        )

    def test_conflict_syncing_known_hosts_file_error_writing(self):
        self.fixture_get_cluster_info()
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=1, known_hosts=self.LOCAL_KNOWN_HOSTS
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        new_file = fixture_save_sync_new_known_hosts_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            initial_local_known_hosts=self.EXPECTED_KNOWN_HOSTS,
            new_hosts=self.REMOTE_KNOWN_HOSTS,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            file_data=new_file.encode(),
            can_overwrite=True,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_KNOWN_HOSTS,
                expected_result="conflict",
                conflict_is_error=False,
            )
            + self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_KNOWN_HOSTS,
                expected_result="conflict",
                conflict_is_error=True,
            )
            + [
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    operation="write",
                    reason="Something bad",
                    file_path=settings.pcsd_known_hosts_location,
                ),
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
        )

    def test_error_syncing_known_hosts_file(self):
        self.fixture_get_cluster_info()
        self.config.raw_file.exists(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=1, known_hosts=self.LOCAL_KNOWN_HOSTS
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        fixture_save_sync_new_known_hosts_error(
            self.config,
            node_labels=["node1", "node2", "node3"],
            file_data_version=2,
            known_hosts=self.EXPECTED_KNOWN_HOSTS,
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            self.fixture_cfgsync_send_files_reports(
                file_type=file_type_codes.PCS_KNOWN_HOSTS,
                expected_result="error",
            )
            + [
                fixture.error(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILED,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1"],
                )
            ]
        )
