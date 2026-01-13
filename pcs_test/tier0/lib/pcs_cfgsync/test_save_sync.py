import json
from typing import Mapping, Optional
from unittest import TestCase

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.communication.const import COM_STATUS_SUCCESS
from pcs.common.communication.dto import InternalCommunicationResultDto
from pcs.common.communication.types import CommunicationResultStatus
from pcs.common.file_type_codes import PCS_KNOWN_HOSTS
from pcs.common.host import PcsKnownHost
from pcs.common.interface.dto import to_dict
from pcs.common.node_communicator import RequestTarget
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.lib.host.config.exporter import Exporter as KnownHostsExporter
from pcs.lib.host.config.facade import Facade as KnownHostsFacade
from pcs.lib.host.config.types import KnownHosts
from pcs.lib.pcs_cfgsync import save_sync

from pcs_test.tools import fixture
from pcs_test.tools.command_env import get_env_tools


def fixture_communication_result_string(
    status: CommunicationResultStatus = COM_STATUS_SUCCESS,
    status_msg: Optional[str] = None,
    report_list: Optional[reports.dto.ReportItemDto] = None,
    data="",
) -> str:
    return json.dumps(
        to_dict(
            InternalCommunicationResultDto(
                status=status,
                status_msg=status_msg,
                report_list=report_list or [],
                data=data,
            )
        )
    )


def fixture_known_hosts_file_content(
    data_version: int = 1,
    known_hosts: Optional[Mapping[str, PcsKnownHost]] = None,
) -> str:
    return KnownHostsExporter.export(
        KnownHosts(
            format_version=1,
            data_version=data_version,
            known_hosts=known_hosts or {},
        )
    ).decode("utf-8")


def fixture_known_hosts_facade(
    data_version: int = 1,
    known_hosts: Optional[Mapping[str, PcsKnownHost]] = None,
) -> KnownHostsFacade:
    return KnownHostsFacade(
        KnownHosts(
            format_version=1,
            data_version=data_version,
            known_hosts=known_hosts or {},
        )
    )


class FixtureFetchNewestFileMixin:
    def fixture_fetch_newest_file(
        self,
        local_file_content,
        remote_file_content,
        call_name_suffix="",
        cluster_name="cluster",
    ):
        self.config.http.place_multinode_call(
            f"fetch.get_configs{call_name_suffix}",
            node_labels=["node1", "node2"],
            output=fixture_communication_result_string(
                data=SyncConfigsDto(
                    cluster_name=cluster_name,
                    configs={
                        file_type_codes.PCS_KNOWN_HOSTS: remote_file_content
                    },
                )
            ),
            action="api/v1/cfgsync-get-configs/v1",
            raw_data=json.dumps({"cluster_name": cluster_name}),
        )
        # the lib.pcs_cfgsync.fetcher.ConfigFetcher reads the file to decide
        # if the files from cluster are newer than the local file
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            name=f"fetch.raw_file.exists{call_name_suffix}",
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            content=local_file_content,
            name=f"fetch.raw_file.read{call_name_suffix}",
        )


class SaveSyncNewVersion(TestCase, FixtureFetchNewestFileMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)
        self.local_file_version = 1
        self.local_file = fixture_known_hosts_file_content(1)
        self.local_known_hosts_facade = KnownHostsFacade(
            KnownHosts(
                format_version=1,
                data_version=self.local_file_version,
                known_hosts={},
            )
        )

    def test_success_first_try(self):
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    self.local_file_version + 1
                )
            },
            node_labels=["node1", "node2"],
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_version(
                PCS_KNOWN_HOSTS,
                self.local_known_hosts_facade,
                "cluster",
                [RequestTarget("node1"), RequestTarget("node2")],
                env.get_node_communicator(),
                env.report_processor,
                False,
            )
        )
        self.assertFalse(conflict_detected)
        self.assertIsNone(new_file)
        self.assertEqual(failed_nodes, set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
            ]
        )

    def test_conflict_no_fetch(self):
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    self.local_file_version + 1
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {
                    "label": "node2",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "error"},
                        }
                    ),
                },
                {"label": "node3"},
            ],
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_version(
                PCS_KNOWN_HOSTS,
                self.local_known_hosts_facade,
                "cluster",
                [
                    RequestTarget("node1"),
                    RequestTarget("node2"),
                    RequestTarget("node3"),
                ],
                env.get_node_communicator(),
                env.report_processor,
                fetch_on_conflict=False,
            )
        )
        self.assertTrue(conflict_detected)
        self.assertIsNone(new_file)
        self.assertEqual(failed_nodes, {"node2"})
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_SAVE_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
            ]
        )

    def test_reject_not_error(self):
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    self.local_file_version + 1
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {
                    "label": "node2",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "error"},
                        }
                    ),
                },
                {"label": "node3"},
            ],
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_version(
                PCS_KNOWN_HOSTS,
                self.local_known_hosts_facade,
                "cluster",
                [
                    RequestTarget("node1"),
                    RequestTarget("node2"),
                    RequestTarget("node3"),
                ],
                env.get_node_communicator(),
                env.report_processor,
                fetch_on_conflict=False,
                reject_is_error=False,
            )
        )
        self.assertTrue(conflict_detected)
        self.assertIsNone(new_file)
        self.assertEqual(failed_nodes, {"node2"})
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2", "node3"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_SAVE_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node3"),
                ),
            ]
        )

    def test_conflict_fetch_success(self):
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    self.local_file_version + 1
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
        )
        remote_file = fixture_known_hosts_file_content(42)
        self.fixture_fetch_newest_file(self.local_file, remote_file)

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_version(
                PCS_KNOWN_HOSTS,
                self.local_known_hosts_facade,
                "cluster",
                [RequestTarget("node1"), RequestTarget("node2")],
                env.get_node_communicator(),
                env.report_processor,
                fetch_on_conflict=True,
            )
        )
        self.assertTrue(conflict_detected)
        self.assertEqual(
            new_file.config, KnownHosts(1, data_version=42, known_hosts={})
        )
        self.assertEqual(failed_nodes, set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
            ]
        )


class SaveSyncNewKnownHosts(TestCase, FixtureFetchNewestFileMixin):
    def setUp(self):
        self.env_assist, self.config = get_env_tools(self)

    def test_success_first_try(self):
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    2, {"NODE": PcsKnownHost("NODE", "TOKEN", [])}
                )
            },
            node_labels=["node1", "node2"],
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_known_hosts(
                fixture_known_hosts_facade(1),
                [PcsKnownHost("NODE", "TOKEN", [])],
                [],
                "cluster",
                [
                    RequestTarget("node1"),
                    RequestTarget("node2"),
                ],
                env.get_node_communicator(),
                env.report_processor,
            )
        )
        self.assertFalse(conflict_detected)
        self.assertIsNone(new_file)
        self.assertEqual(failed_nodes, set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
            ]
        )

    def test_success_first_try_removing_tokens(self):
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    2, {"NODE-B": PcsKnownHost("NODE-B", "TOKEN", [])}
                )
            },
            node_labels=["node1", "node2"],
        )

        local_file = fixture_known_hosts_facade(
            1,
            {
                "NODE-A": PcsKnownHost("NODE-A", "TOKEN", []),
                "NODE-B": PcsKnownHost("NODE-B", "TOKEN", []),
            },
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_known_hosts(
                local_file,
                [],
                ["NODE-A"],
                "cluster",
                [
                    RequestTarget("node1"),
                    RequestTarget("node2"),
                ],
                env.get_node_communicator(),
                env.report_processor,
            )
        )
        self.assertFalse(conflict_detected)
        self.assertIsNone(new_file)
        self.assertEqual(failed_nodes, set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
            ]
        )

    def test_conflict_success_after_merge(self):
        local_file_version = 1
        remote_file_version = 42
        local_tokens = {"LOCAL": PcsKnownHost("LOCAL", "LOCAL", [])}
        remote_tokens = {"REMOTE": PcsKnownHost("REMOTE", "REMOTE", [])}
        new_tokens = {"NEW": PcsKnownHost("NEW", "NEW", [])}

        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    local_file_version + 1, local_tokens | new_tokens
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.1",
        )

        local_file = fixture_known_hosts_file_content(
            local_file_version, local_tokens
        )
        remote_file = fixture_known_hosts_file_content(
            remote_file_version, remote_tokens
        )
        self.fixture_fetch_newest_file(local_file, remote_file)
        # sending the merged tokens
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    remote_file_version + 1,
                    local_tokens | new_tokens | remote_tokens,
                )
            },
            node_labels=["node1", "node2"],
            name="set_configs.2",
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_known_hosts(
                fixture_known_hosts_facade(local_file_version, local_tokens),
                list(new_tokens.values()),
                [],
                "cluster",
                [
                    RequestTarget("node1"),
                    RequestTarget("node2"),
                ],
                env.get_node_communicator(),
                env.report_processor,
            )
        )
        self.assertFalse(conflict_detected)
        self.assertIsNone(new_file)
        self.assertEqual(failed_nodes, set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
            ]
        )

    def test_conflict_even_more_conflict(self):
        local_file_version = 1
        local_tokens = {"LOCAL": PcsKnownHost("LOCAL", "LOCAL", [])}

        remote_file_version = 42
        remote_tokens = {"REMOTE": PcsKnownHost("REMOTE", "REMOTE", [])}

        new_tokens = {"NEW": PcsKnownHost("NEW", "NEW", [])}

        even_more_new_remote_file_version = 69
        even_more_new_remote_tokens = {"WHAT": PcsKnownHost("WHAT", "WHAT", [])}

        local_file = fixture_known_hosts_file_content(
            local_file_version, local_tokens
        )
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    local_file_version + 1, local_tokens | new_tokens
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.1",
        )

        # fetching the newest config from cluster
        remote_file = fixture_known_hosts_file_content(
            remote_file_version, remote_tokens
        )
        self.fixture_fetch_newest_file(
            local_file, remote_file, call_name_suffix="1"
        )

        # sending the merged tokens
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    remote_file_version + 1,
                    local_tokens | new_tokens | remote_tokens,
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.2",
        )

        # fetching the even more newest config from cluster
        even_more_new_remote_file = fixture_known_hosts_file_content(
            even_more_new_remote_file_version, even_more_new_remote_tokens
        )
        self.fixture_fetch_newest_file(
            local_file, even_more_new_remote_file, call_name_suffix="2"
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_known_hosts(
                fixture_known_hosts_facade(local_file_version, local_tokens),
                list(new_tokens.values()),
                [],
                "cluster",
                [
                    RequestTarget("node1"),
                    RequestTarget("node2"),
                ],
                env.get_node_communicator(),
                env.report_processor,
            )
        )
        self.assertTrue(conflict_detected)
        self.assertEqual(
            new_file.config,
            KnownHosts(
                format_version=1,
                data_version=even_more_new_remote_file_version,
                known_hosts=even_more_new_remote_tokens,
            ),
        )
        self.assertEqual(failed_nodes, set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
            ]
        )

    def test_conflict_success_after_merge_remove_tokens(self):
        local_file_version = 1
        remote_file_version = 42
        local_tokens = {
            "LOCAL-A": PcsKnownHost("LOCAL-A", "LOCAL-A", []),
            "LOCAL-B": PcsKnownHost("LOCAL-B", "LOCAL-B", []),
        }
        local_tokens_after_remove = {
            "LOCAL-B": PcsKnownHost("LOCAL-B", "LOCAL-B", []),
        }
        remote_tokens = {"REMOTE": PcsKnownHost("REMOTE", "REMOTE", [])}

        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    local_file_version + 1, local_tokens_after_remove
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.1",
        )

        local_file = fixture_known_hosts_file_content(
            local_file_version, local_tokens
        )
        remote_file = fixture_known_hosts_file_content(
            remote_file_version, remote_tokens
        )
        self.fixture_fetch_newest_file(local_file, remote_file)

        # sending the merged tokens
        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    remote_file_version + 1,
                    local_tokens_after_remove | remote_tokens,
                )
            },
            node_labels=["node1", "node2"],
            name="set_configs.2",
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_known_hosts(
                fixture_known_hosts_facade(local_file_version, local_tokens),
                [],
                ["LOCAL-A"],
                "cluster",
                [
                    RequestTarget("node1"),
                    RequestTarget("node2"),
                ],
                env.get_node_communicator(),
                env.report_processor,
            )
        )
        self.assertFalse(conflict_detected)
        self.assertIsNone(new_file)
        self.assertEqual(failed_nodes, set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
            ]
        )

    def test_conflict_error_reading_file_in_fetch(self):
        local_file_version = 1
        remote_file_version = 42
        local_tokens = {"LOCAL": PcsKnownHost("LOCAL", "LOCAL", [])}
        remote_tokens = {"REMOTE": PcsKnownHost("REMOTE", "REMOTE", [])}
        new_tokens = {"NEW": PcsKnownHost("NEW", "NEW", [])}

        self.config.http.pcs_cfgsync.set_configs(
            "cluster",
            {
                PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                    local_file_version + 1, local_tokens | new_tokens
                )
            },
            communication_list=[
                {
                    "label": "node1",
                    "output": json.dumps(
                        {
                            "status": "ok",
                            "result": {PCS_KNOWN_HOSTS: "rejected"},
                        }
                    ),
                },
                {"label": "node2"},
            ],
            name="set_configs.1",
        )

        # fetching the newest config from cluster
        remote_file = fixture_known_hosts_file_content(
            remote_file_version, remote_tokens
        )
        self.config.http.place_multinode_call(
            node_labels=["node1", "node2"],
            output=fixture_communication_result_string(
                data=SyncConfigsDto(
                    cluster_name="cluster",
                    configs={file_type_codes.PCS_KNOWN_HOSTS: remote_file},
                )
            ),
            action="api/v1/cfgsync-get-configs/v1",
            raw_data=json.dumps({"cluster_name": "cluster"}),
            name="get_configs",
        )
        self.config.raw_file.exists(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
        )
        self.config.raw_file.read(
            PCS_KNOWN_HOSTS,
            settings.pcsd_known_hosts_location,
            exception_msg="error reading during fetch",
        )

        env = self.env_assist.get_env()
        conflict_detected, failed_nodes, new_file = (
            save_sync.save_sync_new_known_hosts(
                fixture_known_hosts_facade(local_file_version, local_tokens),
                list(new_tokens.values()),
                [],
                "cluster",
                [
                    RequestTarget("node1"),
                    RequestTarget("node2"),
                ],
                env.get_node_communicator(),
                env.report_processor,
            )
        )
        self.assertTrue(conflict_detected)
        self.assertIsNone(new_file)
        self.assertEqual(failed_nodes, set())
        self.env_assist.assert_reports(
            [
                fixture.info(
                    reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node1"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                    file_type_code=PCS_KNOWN_HOSTS,
                    context=reports.dto.ReportItemContextDto("node2"),
                ),
                fixture.info(
                    reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                    file_type_code_list=[PCS_KNOWN_HOSTS],
                    node_name_list=["node1", "node2"],
                ),
                fixture.error(
                    reports.codes.FILE_IO_ERROR,
                    file_type_code=PCS_KNOWN_HOSTS,
                    operation="read",
                    reason="error reading during fetch",
                    file_path=settings.pcsd_known_hosts_location,
                ),
            ]
        )
