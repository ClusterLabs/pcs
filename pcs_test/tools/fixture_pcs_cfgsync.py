import json
from typing import Literal, Mapping, Optional, Sequence

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.communication.const import COM_STATUS_SUCCESS
from pcs.common.communication.dto import InternalCommunicationResultDto
from pcs.common.communication.types import CommunicationResultStatus
from pcs.common.host import PcsKnownHost
from pcs.common.interface.dto import to_dict
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.lib.host.config.exporter import Exporter as KnownHostsExporter
from pcs.lib.host.config.types import KnownHosts
from pcs.lib.permissions.config.exporter import ExporterV2
from pcs.lib.permissions.config.types import ClusterPermissions, ConfigV2

from pcs_test.tools import fixture
from pcs_test.tools.command_env.config import Config as EnvConfig
from pcs_test.tools.command_env.mock_node_communicator import (
    NodeCommunicatorType,
)


def fixture_communication_result_string(
    status: CommunicationResultStatus = COM_STATUS_SUCCESS,
    status_msg: Optional[str] = None,
    report_list: Optional[list[reports.ReportItemDto]] = None,
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


def fixture_pcs_settings_file_content(
    data_version=1, clusters=None, permissions=None
):
    return ExporterV2.export(
        ConfigV2(
            data_version=data_version,
            clusters=clusters or [],
            permissions=ClusterPermissions(permissions or []),
        )
    ).decode("utf-8")


__FILE_PATH_MAP = {
    file_type_codes.PCS_SETTINGS_CONF: settings.pcsd_settings_conf_location,
    file_type_codes.PCS_KNOWN_HOSTS: settings.pcsd_known_hosts_location,
}


def fixture_save_sync_new_version_success(
    config: EnvConfig,
    node_labels: list[str],
    cluster_name: str = "test99",
    file_contents: str = "",
    communicator_type: NodeCommunicatorType = (
        NodeCommunicatorType.NO_PRIVILEGE_TRANSITION
    ),
) -> None:
    config.http.pcs_cfgsync.set_configs(
        cluster_name=cluster_name,
        node_labels=node_labels,
        file_contents=file_contents,
        name="save_sync_new_version.set_configs",
        communicator_type=communicator_type,
    )


def fixture_save_sync_new_version_conflict(  # noqa: PLR0913
    config: EnvConfig,
    node_labels: list[str],
    cluster_name: str = "test99",
    file_type_code: file_type_codes.FileTypeCode = (
        file_type_codes.PCS_SETTINGS_CONF
    ),
    local_file_content: str = "",
    fetch_after_conflict: bool = True,
    remote_file_content: str = "",
    name_prefix: str = "",
    communicator_type: NodeCommunicatorType = (
        NodeCommunicatorType.NO_PRIVILEGE_TRANSITION
    ),
) -> None:
    config.http.pcs_cfgsync.set_configs(
        cluster_name,
        file_contents={file_type_code: local_file_content},
        communication_list=[
            {
                "label": node_labels[0],
                "output": json.dumps(
                    {
                        "status": "ok",
                        "result": {file_type_code: "rejected"},
                    }
                ),
            },
        ]
        + [{"label": node} for node in node_labels[1:]],
        name=f"{name_prefix}save_sync_new_version.set_configs",
        communicator_type=communicator_type,
    )
    if not fetch_after_conflict:
        return

    config.http.place_multinode_call(
        node_labels=node_labels,
        output=fixture_communication_result_string(
            data=SyncConfigsDto(
                cluster_name=cluster_name,
                configs={file_type_code: remote_file_content},
            )
        ),
        action="api/v1/cfgsync-get-configs/v1",
        raw_data=json.dumps({"cluster_name": cluster_name}),
        name=f"{name_prefix}save_sync_new_version.fetch_after_conflict",
        communicator_type=communicator_type,
    )
    config.raw_file.exists(
        file_type_code,
        __FILE_PATH_MAP.get(file_type_code),
        name=f"{name_prefix}save_sync_new_version.raw_file.exists",
    )
    config.raw_file.read(
        file_type_code,
        __FILE_PATH_MAP.get(file_type_code),
        content=local_file_content,
        name=f"{name_prefix}save_sync_new_version.raw_file.read",
    )


def fixture_save_sync_new_version_error(
    config: EnvConfig,
    node_labels: list[str],
    cluster_name: str = "test99",
    file_type_code: file_type_codes.FileTypeCode = (
        file_type_codes.PCS_SETTINGS_CONF
    ),
    local_file_content: str = "",
    name_prefix: str = "",
    communicator_type: NodeCommunicatorType = (
        NodeCommunicatorType.NO_PRIVILEGE_TRANSITION
    ),
) -> None:
    config.http.pcs_cfgsync.set_configs(
        cluster_name,
        file_contents={file_type_code: local_file_content},
        communication_list=[
            {
                "label": node_labels[0],
                "output": json.dumps(
                    {
                        "status": "ok",
                        "result": {file_type_code: "error"},
                    }
                ),
            },
        ]
        + [{"label": node} for node in node_labels[1:]],
        name=f"{name_prefix}save_sync_new_version.set_configs",
        communicator_type=communicator_type,
    )


def fixture_save_sync_new_known_hosts_success(
    config: EnvConfig,
    node_labels: list[str],
    cluster_name: str = "test99",
    file_data_version: int = 1,
    known_hosts: Optional[Mapping[str, PcsKnownHost]] = None,
    communicator_type: NodeCommunicatorType = (
        NodeCommunicatorType.NO_PRIVILEGE_TRANSITION
    ),
) -> None:
    config.http.pcs_cfgsync.set_configs(
        cluster_name=cluster_name,
        file_contents={
            file_type_codes.PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                file_data_version, known_hosts or {}
            )
        },
        communicator_type=communicator_type,
        node_labels=node_labels,
        name="save_sync_new_known_hosts.set_configs",
    )


def fixture_save_sync_new_known_hosts_conflict(
    config: EnvConfig,
    node_labels: list[str],
    initial_local_known_hosts: dict[str, PcsKnownHost],
    new_hosts: dict[str, PcsKnownHost],
    hosts_to_remove: Sequence[str] = (),
    cluster_name: str = "test99",
    file_data_version: int = 1,
    communicator_type: NodeCommunicatorType = (
        NodeCommunicatorType.NO_PRIVILEGE_TRANSITION
    ),
) -> str:
    if new_hosts and hosts_to_remove:
        raise AssertionError(
            "Do not use this fixture to add and remove hosts at the same time"
        )

    def __construct_expected_hosts(
        initial: dict[str, PcsKnownHost],
    ) -> dict[str, PcsKnownHost]:
        expected_hosts = {
            k: v for k, v in initial.items() if k not in hosts_to_remove
        }
        return expected_hosts | new_hosts

    expected_hosts = __construct_expected_hosts(initial_local_known_hosts)
    first_push_file = fixture_known_hosts_file_content(
        file_data_version + 1, expected_hosts
    )

    remote_known_hosts = {
        "NODE-FIRST-CONFLICT": PcsKnownHost("NODE-FIRST-CONFLICT", "TOKEN", [])
    }
    remote_file_data_version = file_data_version + 42
    remote_file = fixture_known_hosts_file_content(
        remote_file_data_version, remote_known_hosts
    )

    merged_known_hosts = __construct_expected_hosts(
        initial_local_known_hosts | remote_known_hosts
    )
    merged_file_data_version = remote_file_data_version + 1
    merged_file = fixture_known_hosts_file_content(
        merged_file_data_version, merged_known_hosts
    )

    even_more_new_remote_hosts = {
        "NODE-SECOND-CONFLICT": PcsKnownHost(
            "NODE-SECOND-CONFLICT", "TOKEN", []
        )
    }
    even_more_new_remote_file_data_version = merged_file_data_version + 42
    even_more_new_remote_file = fixture_known_hosts_file_content(
        even_more_new_remote_file_data_version, even_more_new_remote_hosts
    )

    fixture_save_sync_new_version_conflict(
        config,
        cluster_name=cluster_name,
        node_labels=node_labels,
        file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
        local_file_content=first_push_file,
        fetch_after_conflict=True,
        remote_file_content=remote_file,
        name_prefix="sync_initial",
        communicator_type=communicator_type,
    )

    fixture_save_sync_new_version_conflict(
        config,
        cluster_name=cluster_name,
        node_labels=node_labels,
        file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
        local_file_content=merged_file,
        fetch_after_conflict=True,
        remote_file_content=even_more_new_remote_file,
        name_prefix="sync_after_merge",
        communicator_type=communicator_type,
    )

    return even_more_new_remote_file


def fixture_save_sync_new_known_hosts_error(
    config: EnvConfig,
    node_labels: list[str],
    cluster_name: str = "test99",
    file_data_version: int = 1,
    known_hosts: Optional[Mapping[str, PcsKnownHost]] = None,
    communicator_type: NodeCommunicatorType = (
        NodeCommunicatorType.NO_PRIVILEGE_TRANSITION
    ),
) -> None:
    fixture_save_sync_new_version_error(
        config,
        node_labels,
        cluster_name,
        file_type_codes.PCS_KNOWN_HOSTS,
        fixture_known_hosts_file_content(file_data_version, known_hosts or {}),
        communicator_type=communicator_type,
    )


def fixture_expected_save_sync_reports(
    file_type: file_type_codes.FileTypeCode,
    node_labels: list[str],
    expected_result: Literal["ok", "conflict", "error"] = "ok",
    conflict_is_error: bool = True,
) -> list[fixture.ReportItemFixture]:
    _report_code_map = {
        "ok": reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
        "conflict": reports.codes.PCS_CFGSYNC_CONFIG_REJECTED,
        "error": reports.codes.PCS_CFGSYNC_CONFIG_SAVE_ERROR,
    }

    first_node_report = (
        fixture.error(
            _report_code_map[expected_result],
            file_type_code=file_type,
            context=reports.dto.ReportItemContextDto(
                node_labels[0],
            ),  # type: ignore [arg-type]
        )
        if expected_result == "error"
        or (expected_result == "conflict" and conflict_is_error)
        else fixture.info(
            _report_code_map[expected_result],
            file_type_code=file_type,
            context=reports.dto.ReportItemContextDto(
                node_labels[0],
            ),  # type: ignore [arg-type]
        )
    )

    report_list = (
        [
            fixture.info(
                reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES,
                file_type_code_list=[file_type],
                node_name_list=node_labels,
            ),
            first_node_report,
        ]
        + [
            fixture.info(
                reports.codes.PCS_CFGSYNC_CONFIG_ACCEPTED,
                file_type_code=file_type,
                context=reports.dto.ReportItemContextDto(
                    node_label,
                ),  # type: ignore [arg-type]
            )
            for node_label in node_labels[1:]
        ]
    )

    if expected_result == "conflict":
        report_list.append(
            fixture.info(
                reports.codes.PCS_CFGSYNC_FETCHING_NEWEST_CONFIG,
                file_type_code_list=[file_type],
                node_name_list=node_labels,
            )
        )
        if conflict_is_error:
            report_list.append(
                fixture.error(reports.codes.PCS_CFGSYNC_CONFLICT_REPEAT_ACTION)
            )
        return report_list

    if expected_result == "error":
        return report_list + [
            fixture.error(
                reports.codes.PCS_CFGSYNC_SENDING_CONFIGS_TO_NODES_FAILED,
                file_type_code_list=[file_type],
                node_name_list=[node_labels[0]],
            )
        ]

    return report_list
