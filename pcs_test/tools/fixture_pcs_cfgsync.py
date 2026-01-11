import json
from typing import Mapping, Optional

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

from pcs_test.tools.command_env.config import Config as EnvConfig


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


def fixture_pcs_settings_file_content(data_version=1, clusters=None):
    return ExporterV2.export(
        ConfigV2(
            data_version=data_version,
            clusters=clusters or [],
            permissions=ClusterPermissions([]),
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
) -> None:
    config.http.pcs_cfgsync.set_configs(
        cluster_name=cluster_name,
        node_labels=node_labels,
        file_contents=file_contents,
        name="save_sync_new_version.set_configs",
    )


def fixture_save_sync_new_version_conflict(
    config: EnvConfig,
    node_labels: list[str],
    cluster_name: str = "test99",
    file_type_code: file_type_codes.FileTypeCode = file_type_codes.PCS_SETTINGS_CONF,
    local_file_content: str = "",
    fetch_after_conflict: bool = True,
    remote_file_content: str = "",
    name_prefix: str = "",
) -> None:
    config.http.pcs_cfgsync.set_configs(
        "test99",
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
    file_type_code: file_type_codes.FileTypeCode = file_type_codes.PCS_SETTINGS_CONF,
    local_file_content: str = "",
    name_prefix: str = "",
) -> None:
    config.http.pcs_cfgsync.set_configs(
        "test99",
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
    )


def fixture_save_sync_new_known_hosts_success(
    config: EnvConfig,
    node_labels: list[str],
    cluster_name: str = "test99",
    file_data_version: int = 1,
    known_hosts: Optional[Mapping[str, PcsKnownHost]] = None,
) -> None:
    config.http.pcs_cfgsync.set_configs(
        cluster_name=cluster_name,
        file_contents={
            file_type_codes.PCS_KNOWN_HOSTS: fixture_known_hosts_file_content(
                file_data_version, known_hosts or {}
            )
        },
        node_labels=node_labels,
        name="save_sync_new_known_hosts.set_configs",
    )


def fixture_save_sync_new_known_hosts_conflict(
    config: EnvConfig,
    node_labels: list[str],
    cluster_name: str = "test99",
    file_data_version: int = 1,
    known_hosts: Optional[Mapping[str, PcsKnownHost]] = None,
) -> str:
    local_file = fixture_known_hosts_file_content(
        file_data_version + 1, known_hosts
    )

    remote_file_data_version = file_data_version + 42
    newer_remote_file = fixture_known_hosts_file_content(
        remote_file_data_version, known_hosts
    )

    merged_file = fixture_known_hosts_file_content(
        remote_file_data_version + 1, known_hosts
    )

    even_more_new_file_data_version = remote_file_data_version + 42
    even_more_new_remote_file = fixture_known_hosts_file_content(
        even_more_new_file_data_version, known_hosts
    )

    fixture_save_sync_new_version_conflict(
        config,
        cluster_name=cluster_name,
        node_labels=node_labels,
        file_type_code=file_type_codes.PCS_KNOWN_HOSTS,
        local_file_content=local_file,
        fetch_after_conflict=True,
        remote_file_content=newer_remote_file,
        name_prefix="sync_initial",
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
    )

    return even_more_new_remote_file


def fixture_save_sync_new_known_hosts_error(
    config: EnvConfig,
    node_labels: list[str],
    file_data_version: int = 1,
    known_hosts: Optional[Mapping[str, PcsKnownHost]] = None,
) -> None:
    fixture_save_sync_new_version_error(
        config,
        node_labels,
        file_type_codes.PCS_KNOWN_HOSTS,
        fixture_known_hosts_file_content(file_data_version, known_hosts or {}),
    )
