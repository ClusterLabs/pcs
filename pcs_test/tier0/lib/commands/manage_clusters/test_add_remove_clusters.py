from typing import Callable
from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.lib.commands import manage_clusters
from pcs.lib.permissions.config.types import ClusterEntry

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools
from pcs_test.tools.fixture_pcs_cfgsync import (
    fixture_expected_save_sync_reports,
    fixture_pcs_settings_file_content,
    fixture_save_sync_new_version_conflict,
    fixture_save_sync_new_version_error,
    fixture_save_sync_new_version_success,
)


class AddRemoveNotInClusterBase:
    LOCAL_CLUSTERS = [
        ClusterEntry("CLUSTER-X", ["A", "B", "C"]),
        ClusterEntry("CLUSTER-Y", ["X", "Y", "Z"]),
        ClusterEntry("CLUSTER-Z", ["1", "2", "3"]),
    ]

    # Change accordingly in subclasses
    CLUSTERS_AFTER_OPERATION = LOCAL_CLUSTERS

    def get_lib_command_call(self) -> Callable[[], None]:
        raise NotImplementedError()

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3"])

    def fixture_read_local_file(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(
                1, clusters=self.LOCAL_CLUSTERS
            ),
            name="raw_file.read.pcs_known_hosts",
        )

    def test_error_reading_pcs_settings(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            name="raw_file.exists.pcs_known_hosts",
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            exception_msg="Something bad",
            name="raw_file.read.pcs_known_hosts",
        )

        self.env_assist.assert_raise_library_error(self.get_lib_command_call())

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

    def test_success(self):
        self.fixture_read_local_file()
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                2, clusters=self.CLUSTERS_AFTER_OPERATION
            ).encode(),
            can_overwrite=True,
        )

        self.get_lib_command_call()()
        self.env_assist.assert_reports([])

    def test_error_writing_pcs_settings_conf(self):
        self.fixture_read_local_file()
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="corosync.exists",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                2, clusters=self.CLUSTERS_AFTER_OPERATION
            ).encode(),
            exception_msg="Something bad",
            can_overwrite=True,
        )

        self.env_assist.assert_raise_library_error(self.get_lib_command_call())
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


class AddClusterLocalNodeNotInCluster(AddRemoveNotInClusterBase, TestCase):
    CLUSTERS_AFTER_OPERATION = AddRemoveNotInClusterBase.LOCAL_CLUSTERS + [
        ClusterEntry("CLUSTER", ["NODE1", "NODE2"])
    ]

    def get_lib_command_call(self):
        return lambda: manage_clusters.add_cluster(
            self.env_assist.get_env(), "CLUSTER", ["NODE1", "NODE2"]
        )

    def test_input_validation_failed(self):
        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_cluster(
                self.env_assist.get_env(), "", ["NODE1"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="cluster name",
                    option_value="",
                    allowed_values=None,
                    cannot_be_empty=True,
                    forbidden_characters=None,
                )
            ]
        )

    def test_cluster_name_already_used(self):
        self.fixture_read_local_file()
        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_cluster(
                self.env_assist.get_env(), "CLUSTER-X", ["NODE1"]
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.CLUSTER_NAME_ALREADY_IN_USE,
                    cluster_name="CLUSTER-X",
                )
            ]
        )


class RemoveClustersLocalNodeNotInCluster(AddRemoveNotInClusterBase, TestCase):
    CLUSTERS_AFTER_OPERATION = AddRemoveNotInClusterBase.LOCAL_CLUSTERS[:1]

    def get_lib_command_call(self):
        return lambda: manage_clusters.remove_clusters(
            self.env_assist.get_env(), ["CLUSTER-Y", "CLUSTER-Z"]
        )

    def test_input_validation_failed(self):
        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.remove_clusters(
                self.env_assist.get_env(), []
            )
        )
        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.ADD_REMOVE_ITEMS_NOT_SPECIFIED,
                    container_type=None,
                    item_type=reports.const.ADD_REMOVE_ITEM_TYPE_CLUSTER,
                    container_id=None,
                )
            ]
        )


class AddRemoveInClusterBase:
    NODE_LABELS = ["node1", "node2", "node3"]

    LOCAL_CLUSTERS = [
        ClusterEntry("CLUSTER-X", ["A", "B", "C"]),
        ClusterEntry("CLUSTER-Y", ["X", "Y", "Z"]),
        ClusterEntry("CLUSTER-Z", ["1", "2", "3"]),
    ]

    # Change accordingly in subclasses
    CLUSTERS_AFTER_OPERATION = LOCAL_CLUSTERS

    def get_lib_command_call(self) -> Callable[[], None]:
        raise NotImplementedError()

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(self.NODE_LABELS)

    def fixture_read_local_files(self):
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(
                data_version=1, clusters=self.LOCAL_CLUSTERS
            ),
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="corosync.exists",
        )
        self.config.corosync_conf.load(self.NODE_LABELS)

    def test_success(self):
        self.fixture_read_local_files()
        fixture_save_sync_new_version_success(
            self.config,
            node_labels=self.NODE_LABELS,
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: fixture_pcs_settings_file_content(
                    data_version=2, clusters=self.CLUSTERS_AFTER_OPERATION
                )
            },
        )

        self.get_lib_command_call()()

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=self.NODE_LABELS,
            )
        )

    def test_sync_conflict(self):
        self.fixture_read_local_files()
        cluster_newest_file = fixture_pcs_settings_file_content(
            data_version=300, clusters=[]
        )
        fixture_save_sync_new_version_conflict(
            self.config,
            node_labels=self.NODE_LABELS,
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                2, clusters=self.CLUSTERS_AFTER_OPERATION
            ),
            fetch_after_conflict=True,
            remote_file_content=cluster_newest_file,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            cluster_newest_file.encode(),
            can_overwrite=True,
        )

        self.env_assist.assert_raise_library_error(self.get_lib_command_call())

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=self.NODE_LABELS,
                expected_result="conflict",
            )
        )

    def test_sync_conflict_error_writing_file(self):
        self.fixture_read_local_files()
        cluster_newest_file = fixture_pcs_settings_file_content(
            data_version=300, clusters=[]
        )
        fixture_save_sync_new_version_conflict(
            self.config,
            node_labels=self.NODE_LABELS,
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                2, clusters=self.CLUSTERS_AFTER_OPERATION
            ),
            fetch_after_conflict=True,
            remote_file_content=cluster_newest_file,
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            cluster_newest_file.encode(),
            can_overwrite=True,
            exception_msg="Something bad",
        )

        self.env_assist.assert_raise_library_error(self.get_lib_command_call())

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=self.NODE_LABELS,
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
            ]
        )

    def test_sync_error(self):
        self.fixture_read_local_files()
        fixture_save_sync_new_version_error(
            self.config,
            self.NODE_LABELS,
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                2, clusters=self.CLUSTERS_AFTER_OPERATION
            ),
        )

        self.env_assist.assert_raise_library_error(self.get_lib_command_call())

        self.env_assist.assert_reports(
            fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=self.NODE_LABELS,
                expected_result="error",
            )
        )

    def test_some_cluster_nodes_not_known_to_pcs(self):
        self.config.env.set_known_nodes(["node1"])
        self.fixture_read_local_files()
        fixture_save_sync_new_version_success(
            self.config,
            node_labels=["node1"],
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: fixture_pcs_settings_file_content(
                    data_version=2, clusters=self.CLUSTERS_AFTER_OPERATION
                )
            },
        )

        self.env_assist.assert_raise_library_error(self.get_lib_command_call())

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND, host_list=["node2", "node3"]
                ),
            ]
            + fixture_expected_save_sync_reports(
                file_type=file_type_codes.PCS_SETTINGS_CONF,
                node_labels=["node1"],
            )
            + [
                fixture.error(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILED,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node2", "node3"],
                ),
            ]
        )

    def test_no_cluster_nodes_known_to_pcs(self):
        self.config.env.set_known_nodes([])
        self.fixture_read_local_files()

        self.env_assist.assert_raise_library_error(self.get_lib_command_call())

        self.env_assist.assert_reports(
            [
                fixture.error(
                    reports.codes.HOST_NOT_FOUND,
                    host_list=["node1", "node2", "node3"],
                ),
                fixture.error(reports.codes.NONE_HOST_FOUND),
            ]
        )


class AddClusterLocalNodeInCluster(AddRemoveInClusterBase, TestCase):
    CLUSTERS_AFTER_OPERATION = AddRemoveNotInClusterBase.LOCAL_CLUSTERS + [
        ClusterEntry("CLUSTER", ["NODE1", "NODE2"])
    ]

    def get_lib_command_call(self):
        return lambda: manage_clusters.add_cluster(
            self.env_assist.get_env(), "CLUSTER", ["NODE1", "NODE2"]
        )


class RemoveClusterLocalNodeInCluster(AddRemoveInClusterBase, TestCase):
    CLUSTERS_AFTER_OPERATION = AddRemoveNotInClusterBase.LOCAL_CLUSTERS[:1]

    def get_lib_command_call(self):
        return lambda: manage_clusters.remove_clusters(
            self.env_assist.get_env(), ["CLUSTER-Y", "CLUSTER-Z"]
        )
