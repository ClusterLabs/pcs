import json
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


class AddExistingClusterLocalNodeNotInCluster(TestCase):
    LOCAL_CLUSTERS = [ClusterEntry("local", ["a", "b"])]

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3"])

    def fixture_get_cluster_info(
        self, new_hosts=True, pcs_settings_exists=True
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
        if new_hosts:
            self.config.http.place_multinode_call(
                node_labels=["node1"],
                action="remote/get_cluster_known_hosts",
                param_list=[],
                output=json.dumps(
                    dict(
                        node5=dict(
                            dest_list=[dict(addr="123", port=456)],
                            token="TOKEN1",
                        ),
                        node6=dict(
                            dest_list=[dict(addr="abc", port=2222)],
                            token="TOKEN2",
                        ),
                    )
                ),
                name="get_cluster_known_hosts",
            )
        else:
            self.config.http.place_multinode_call(
                node_labels=["node1"],
                output="{}",
                action="remote/get_cluster_known_hosts",
                param_list=[],
                name="get_cluster_known_hosts",
            )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="raw_file.exists.corosync_conf",
        )

    def test_success_no_new_hosts(self):
        self.fixture_get_cluster_info(new_hosts=False)
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                data_version=2,
                clusters=[
                    *self.LOCAL_CLUSTERS,
                    ClusterEntry("cluster", ["m", "n", "x", "y"]),
                ],
            ).encode(),
            can_overwrite=True,
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

    def test_success_error_getting_known_hosts_from_node(self):
        self.config.http.status.get_cluster_info_from_status(
            node_labels=["node1"],
            cluster_name="cluster",
            corosync_online_nodes=["m", "n"],
            corosync_offline_nodes=["x", "y"],
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(),
        )
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
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="raw_file.exists.corosync_conf",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                data_version=2,
                clusters=[
                    ClusterEntry("cluster", ["m", "n", "x", "y"]),
                ],
            ).encode(),
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
        self.config.http.status.get_cluster_info_from_status(
            node_labels=["node1"],
            cluster_name="cluster",
            corosync_online_nodes=["m", "n"],
            corosync_offline_nodes=["x", "y"],
        )
        self.config.raw_file.exists(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
        )
        self.config.raw_file.read(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            content=fixture_pcs_settings_file_content(),
        )
        self.config.http.place_multinode_call(
            action="remote/get_cluster_known_hosts",
            communication_list=[dict(label="node1", output="Bad format")],
            param_list=[],
            name="get_cluster_known_hosts",
            output="",
        )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            exists=False,
            name="raw_file.exists.corosync_conf",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                data_version=2,
                clusters=[
                    ClusterEntry("cluster", ["m", "n", "x", "y"]),
                ],
            ).encode(),
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
                data_version=1, known_hosts=known_hosts
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=2,
                known_hosts={
                    **known_hosts,
                    "node5": PcsKnownHost(
                        "node5", "TOKEN1", [Destination("123", 456)]
                    ),
                    "node6": PcsKnownHost(
                        "node6", "TOKEN2", [Destination("abc", 2222)]
                    ),
                },
            ).encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                data_version=2,
                clusters=[
                    *self.LOCAL_CLUSTERS,
                    ClusterEntry("cluster", ["m", "n", "x", "y"]),
                ],
            ).encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_settings_conf",
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

    def test_no_new_hosts_error_writing_settings_file(self):
        self.fixture_get_cluster_info(new_hosts=False)
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                data_version=2,
                clusters=[
                    *self.LOCAL_CLUSTERS,
                    ClusterEntry("cluster", ["m", "n", "x", "y"]),
                ],
            ).encode(),
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
                data_version=1, known_hosts=known_hosts
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            fixture_known_hosts_file_content(
                data_version=2,
                known_hosts={
                    **known_hosts,
                    "node5": PcsKnownHost(
                        "node5", "TOKEN1", [Destination("123", 456)]
                    ),
                    "node6": PcsKnownHost(
                        "node6", "TOKEN2", [Destination("abc", 2222)]
                    ),
                },
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
        self.fixture_get_cluster_info(pcs_settings_exists=False)
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
                data_version=1,
                known_hosts={
                    "node5": PcsKnownHost(
                        "node5", "TOKEN1", [Destination("123", 456)]
                    ),
                    "node6": PcsKnownHost(
                        "node6", "TOKEN2", [Destination("abc", 2222)]
                    ),
                },
            ).encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_known_hosts",
        )
        self.config.raw_file.write(
            file_type_codes.PCS_SETTINGS_CONF,
            settings.pcsd_settings_conf_location,
            fixture_pcs_settings_file_content(
                data_version=1,
                clusters=[
                    ClusterEntry("cluster", ["m", "n", "x", "y"]),
                ],
            ).encode(),
            can_overwrite=True,
            name="raw_file.write.pcs_settings_conf",
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

    def test_error_reading_known_hosts_file(self):
        self.fixture_get_cluster_info()
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


class AddExistingClusterLocalNodeInCluster(TestCase):
    LOCAL_CLUSTERS = [ClusterEntry("local", ["a", "b"])]

    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.config.env.set_known_nodes(["node1", "node2", "node3"])

    def fixture_get_cluster_info(self, new_hosts=True):
        self.config.http.status.get_cluster_info_from_status(
            node_labels=["node1"],
            cluster_name="cluster",
            corosync_online_nodes=["node5", "node6"],
            corosync_offline_nodes=["node7", "node8"],
        )
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
        if new_hosts:
            self.config.http.place_multinode_call(
                node_labels=["node1"],
                action="remote/get_cluster_known_hosts",
                param_list=[],
                output=json.dumps(
                    dict(
                        node5=dict(
                            dest_list=[dict(addr="123", port=456)],
                            token="TOKEN1",
                        ),
                        node6=dict(
                            dest_list=[dict(addr="abc", port=2222)],
                            token="TOKEN2",
                        ),
                    )
                ),
                name="get_cluster_known_hosts",
            )
        else:
            self.config.http.place_multinode_call(
                node_labels=["node1"],
                action="remote/get_cluster_known_hosts",
                param_list=[],
                output="{}",
                name="get_cluster_known_hosts",
            )
        self.config.raw_file.exists(
            file_type_codes.COROSYNC_CONF,
            settings.corosync_conf_file,
            name="raw_file.exists.corosync_conf",
        )
        self.config.corosync_conf.load(["node1", "node2", "node3"])

    def test_success_no_new_hosts(self):
        self.fixture_get_cluster_info(new_hosts=False)
        fixture_save_sync_new_version_success(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: fixture_pcs_settings_file_content(
                    data_version=2,
                    clusters=[
                        *self.LOCAL_CLUSTERS,
                        ClusterEntry(
                            "cluster", ["node5", "node6", "node7", "node8"]
                        ),
                    ],
                )
            },
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
            ]
        )

    def test_success_new_hosts(self):
        known_hosts = {"node1": PcsKnownHost("node1", "TOKEN", dest_list=[])}

        self.fixture_get_cluster_info(new_hosts=True)
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
        fixture_save_sync_new_known_hosts_success(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_data_version=2,
            known_hosts={
                **known_hosts,
                "node5": PcsKnownHost(
                    "node5", "TOKEN1", [Destination("123", 456)]
                ),
                "node6": PcsKnownHost(
                    "node6", "TOKEN2", [Destination("abc", 2222)]
                ),
            },
        )
        fixture_save_sync_new_version_success(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_contents={
                file_type_codes.PCS_SETTINGS_CONF: fixture_pcs_settings_file_content(
                    data_version=2,
                    clusters=[
                        *self.LOCAL_CLUSTERS,
                        ClusterEntry(
                            "cluster", ["node5", "node6", "node7", "node8"]
                        ),
                    ],
                )
            },
        )

        manage_clusters.add_existing_cluster(self.env_assist.get_env(), "node1")

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
            ]
        )

    def test_conflict_syncing_pcs_settings_file(self):
        self.fixture_get_cluster_info(new_hosts=False)
        remote_file = fixture_pcs_settings_file_content(
            data_version=99, clusters=self.LOCAL_CLUSTERS
        )
        fixture_save_sync_new_version_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                data_version=2,
                clusters=[
                    *self.LOCAL_CLUSTERS,
                    ClusterEntry(
                        "cluster", ["node5", "node6", "node7", "node8"]
                    ),
                ],
            ),
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
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
        )

    def test_conflict_syncing_pcs_settings_file_error_writing(self):
        self.fixture_get_cluster_info(new_hosts=False)
        remote_file = fixture_pcs_settings_file_content(
            data_version=99, clusters=self.LOCAL_CLUSTERS
        )
        fixture_save_sync_new_version_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                data_version=2,
                clusters=[
                    *self.LOCAL_CLUSTERS,
                    ClusterEntry(
                        "cluster", ["node5", "node6", "node7", "node8"]
                    ),
                ],
            ),
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
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1", "node2", "node3"],
                ),
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
        self.fixture_get_cluster_info(new_hosts=False)
        fixture_save_sync_new_version_error(
            self.config,
            node_labels=["node1", "node2", "node3"],
            file_type_code=file_type_codes.PCS_SETTINGS_CONF,
            local_file_content=fixture_pcs_settings_file_content(
                data_version=2,
                clusters=[
                    *self.LOCAL_CLUSTERS,
                    ClusterEntry(
                        "cluster", ["node5", "node6", "node7", "node8"]
                    ),
                ],
            ),
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_SAVE_ERROR,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_SETTINGS_CONF,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILURES,
                    file_type_code_list=[file_type_codes.PCS_SETTINGS_CONF],
                    node_name_list=["node1"],
                ),
            ]
        )

    def test_conflict_syncing_known_hosts_file(self):
        known_hosts = {"node1": PcsKnownHost("node1", "TOKEN", dest_list=[])}

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
                data_version=1, known_hosts=known_hosts
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        new_file = fixture_save_sync_new_known_hosts_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_data_version=1,
            known_hosts={
                **known_hosts,
                "node5": PcsKnownHost(
                    "node5", "TOKEN1", [Destination("123", 456)]
                ),
                "node6": PcsKnownHost(
                    "node6", "TOKEN2", [Destination("abc", 2222)]
                ),
            },
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
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION),
            ]
        )

    def test_conflict_syncing_known_hosts_file_error_writing(self):
        known_hosts = {"node1": PcsKnownHost("node1", "TOKEN", dest_list=[])}

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
                data_version=1, known_hosts=known_hosts
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        new_file = fixture_save_sync_new_known_hosts_conflict(
            self.config,
            cluster_name="test99",
            node_labels=["node1", "node2", "node3"],
            file_data_version=1,
            known_hosts={
                **known_hosts,
                "node5": PcsKnownHost(
                    "node5", "TOKEN1", [Destination("123", 456)]
                ),
                "node6": PcsKnownHost(
                    "node6", "TOKEN2", [Destination("abc", 2222)]
                ),
            },
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
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
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
        known_hosts = {"node1": PcsKnownHost("node1", "TOKEN", dest_list=[])}

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
                data_version=1, known_hosts=known_hosts
            ),
            name="raw_file.read.pcs_known_hosts",
        )
        fixture_save_sync_new_known_hosts_error(
            self.config,
            node_labels=["node1", "node2", "node3"],
            file_data_version=2,
            known_hosts={
                **known_hosts,
                "node5": PcsKnownHost(
                    "node5", "TOKEN1", [Destination("123", 456)]
                ),
                "node6": PcsKnownHost(
                    "node6", "TOKEN2", [Destination("abc", 2222)]
                ),
            },
        )

        self.env_assist.assert_raise_library_error(
            lambda: manage_clusters.add_existing_cluster(
                self.env_assist.get_env(), "node1"
            )
        )

        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_SAVE_ERROR,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILURES,
                    file_type_code_list=[file_type_codes.PCS_KNOWN_HOSTS],
                    node_name_list=["node1"],
                ),
            ]
        )
