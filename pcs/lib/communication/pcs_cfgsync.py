import json
from collections import defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any

from dacite import DaciteError

from pcs.common import reports
from pcs.common.communication.const import (
    COM_STATUS_SUCCESS,
    COM_STATUS_UNKNOWN_CMD,
)
from pcs.common.communication.dto import InternalCommunicationResultDto
from pcs.common.file_type_codes import (
    PCS_KNOWN_HOSTS,
    PCS_SETTINGS_CONF,
    FileTypeCode,
)
from pcs.common.interface.dto import PayloadConversionError, from_dict
from pcs.common.node_communicator import (
    Request,
    RequestData,
    RequestTarget,
    Response,
)
from pcs.common.pcs_cfgsync_dto import SyncConfigsDto
from pcs.common.reports import ReportProcessor
from pcs.common.reports.processor import has_errors
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SkipOfflineMixin,
)

_LEGACY_FILE_NAME_TO_FILETYPECODE_MAP = {
    "known-hosts": PCS_KNOWN_HOSTS,
    "pcs_settings.conf": PCS_SETTINGS_CONF,
}
_FILETYPECODE_TO_LEGACY_FILE_NAME_MAP = {
    PCS_KNOWN_HOSTS: "known-hosts",
    PCS_SETTINGS_CONF: "pcs_settings.conf",
}


@dataclass(frozen=True)
class ConfigInfo:
    cfg_origin: str
    cfg_content: str


@dataclass(frozen=True)
class GetConfigsResult:
    was_successful: bool
    config_files: dict[FileTypeCode, list[ConfigInfo]]


class GetConfigs(
    SkipOfflineMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    _LEGACY_ENDPOINT = "remote/get_configs"

    def __init__(
        self,
        report_processor: ReportProcessor,
        cluster_name: str,
        skip_offline_targets: bool = False,
    ):
        super().__init__(report_processor)
        self._cluster_name = cluster_name
        self._successful_connections = 0
        self._received_configs: dict[FileTypeCode, list[ConfigInfo]] = (
            defaultdict(list)
        )
        self._set_skip_offline(skip_offline_targets)

    def _get_request_data(self) -> RequestData:
        return RequestData(
            "api/v1/cfgsync-get-configs/v1",
            data=json.dumps({"cluster_name": self._cluster_name}),
        )

    def _get_legacy_request(self, target: RequestTarget) -> Request:
        return Request(
            target,
            RequestData(
                self._LEGACY_ENDPOINT, [("cluster_name", self._cluster_name)]
            ),
        )

    def _process_response(self, response: Response) -> list[Request]:  # noqa: PLR0911
        if response.request.action == self._LEGACY_ENDPOINT:
            self._process_legacy_response(response)
            return []

        request_target = response.request.target

        if response.response_code == 404:
            # If we communicate with older node, that does not support
            # the new endpoint, then try using the old endpoint
            return [self._get_legacy_request(request_target)]

        report_item = self._get_response_report(response)
        if report_item:
            self._report(report_item)
            return []

        try:
            com_result: InternalCommunicationResultDto = from_dict(
                InternalCommunicationResultDto, json.loads(response.data)
            )
        except (json.JSONDecodeError, DaciteError):
            self._report(
                reports.ReportItem.error(
                    reports.messages.InvalidResponseFormat(request_target.label)
                )
            )
            return []

        if com_result.status == COM_STATUS_UNKNOWN_CMD:
            # If we communicate with older node, that does not support
            # the new endpoint, then try using the old one
            return [self._get_legacy_request(request_target)]

        context = reports.ReportItemContext(response.request.target.label)
        report_list = [
            reports.report_dto_to_item(report, context)
            for report in com_result.report_list
        ]
        self._report_list(report_list)
        errors_in_report_list = has_errors(report_list)

        if (
            not errors_in_report_list
            and com_result.status == COM_STATUS_SUCCESS
        ):
            try:
                config_data: SyncConfigsDto = from_dict(
                    SyncConfigsDto, com_result.data
                )
            except (DaciteError, PayloadConversionError):
                self._report(
                    reports.ReportItem.error(
                        reports.messages.InvalidResponseFormat(
                            request_target.label
                        )
                    )
                )
                return []
            if config_data.cluster_name != self._cluster_name:
                self._report(
                    reports.ReportItem.error(
                        reports.messages.NodeReportsUnexpectedClusterName(
                            self._cluster_name
                        ),
                        context=context,
                    )
                )
                return []

            self._successful_connections += 1
            for cfg_type, cfg_content in config_data.configs.items():
                self._received_configs[cfg_type].append(
                    ConfigInfo(request_target.label, cfg_content)
                )
            return []

        # Make sure we report an error when the command was not successful
        if com_result.status_msg or not errors_in_report_list:
            self._report(
                reports.ReportItem.error(
                    reports.messages.NodeCommunicationCommandUnsuccessful(
                        request_target.label,
                        response.request.action,
                        com_result.status_msg or "Unknown error",
                    )
                )
            )
        return []

    def _process_legacy_response(self, response: Response) -> None:
        """
        format of the `response.data`:
        {
            "status": str -> ("ok"|"not_in_cluster"|"wrong_cluster_name")
            "cluster_name": str
            "configs": {
                "pcs_settings.conf": {
                    "type": str -> ("file"),
                    "text": Optional[str]
                },
                "known-hosts": {
                    "type": str -> ("file"),
                    "text": Optional[str]
                }
            }
        }
        """
        report_item = self._get_response_report(response)
        if report_item:
            self._report(report_item)
            return
        context = reports.ReportItemContext(response.request.target.label)

        try:
            parsed_data = json.loads(response.data)
            if (
                parsed_data["status"] == "wrong_cluster_name"
                or parsed_data["status"] == "not_in_cluster"
                or parsed_data["cluster_name"] != self._cluster_name
            ):
                self._report(
                    reports.ReportItem.error(
                        reports.messages.NodeReportsUnexpectedClusterName(
                            self._cluster_name
                        ),
                        context=context,
                    )
                )
                return

            for cfg_name in parsed_data["configs"]:
                if cfg_name not in _LEGACY_FILE_NAME_TO_FILETYPECODE_MAP:
                    continue
                cfg_file = parsed_data["configs"][cfg_name]["text"]
                if (
                    parsed_data["configs"][cfg_name]["type"] == "file"
                    and cfg_file is not None
                ):
                    self._received_configs[
                        _LEGACY_FILE_NAME_TO_FILETYPECODE_MAP[cfg_name]
                    ].append(
                        ConfigInfo(response.request.target.label, cfg_file)
                    )

            self._successful_connections += 1
        except (json.JSONDecodeError, KeyError):
            self._report(
                reports.ReportItem.error(
                    reports.messages.InvalidResponseFormat(
                        response.request.target.label
                    )
                )
            )

    def on_complete(self) -> GetConfigsResult:
        return GetConfigsResult(
            was_successful=self._successful_connections >= 2,
            config_files=self._received_configs,
        )


class SetConfigsResult(Enum):
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    NOT_SUPPORTED = "not_supported"
    ERROR = "error"


class SetConfigs(
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def __init__(
        self,
        report_processor: ReportProcessor,
        cluster_name: str,
        configs: dict[FileTypeCode, str],
        rejection_severity: reports.ReportItemSeverity,
        force: bool = False,
    ):
        super().__init__(report_processor)
        self._cluster_name = cluster_name
        self._configs = configs
        self._rejection_severity = rejection_severity
        self._force = force
        self._node_results: dict[str, dict[FileTypeCode, SetConfigsResult]] = {}

    def before(self) -> None:
        self._report(
            reports.ReportItem.info(
                reports.messages.PcsCfgsyncSendingConfigsToNodes(
                    sorted(self._configs.keys()), self._target_label_list
                )
            )
        )

    def _get_request_data(self) -> RequestData:
        data: dict[str, Any] = {}
        data["cluster_name"] = self._cluster_name
        data["force"] = self._force
        data["configs"] = {
            _FILETYPECODE_TO_LEGACY_FILE_NAME_MAP.get(
                filetype_code, filetype_code
            ): {
                "type": "file",
                "text": config_content,
            }
            for filetype_code, config_content in self._configs.items()
        }
        return RequestData(
            "remote/set_configs", [("configs", json.dumps(data))]
        )

    def _process_response(self, response: Response) -> list[Request]:
        report_item = self._get_response_report(response)
        if report_item:
            self._report(report_item)
            return []

        node_label = response.request.target.label
        context = reports.ReportItemContext(node_label)

        try:
            parsed_data = json.loads(response.data)
            if parsed_data["status"] == "wrong_cluster_name":
                self._report(
                    reports.ReportItem.error(
                        reports.messages.NodeReportsUnexpectedClusterName(
                            self._cluster_name or ""
                        ),
                        context=context,
                    )
                )
                return []

            parsed_result = parsed_data["result"]
            results = {}
            for cfg_name in parsed_result:
                cfg_filetypecode = _LEGACY_FILE_NAME_TO_FILETYPECODE_MAP.get(
                    cfg_name, cfg_name
                )
                normalized_cfg_result = SetConfigsResult(
                    parsed_result[cfg_name]
                )
                match normalized_cfg_result:
                    case SetConfigsResult.ACCEPTED:
                        self._report(
                            reports.ReportItem.info(
                                reports.messages.PcsCfgsyncConfigAccepted(
                                    cfg_filetypecode
                                ),
                                context=reports.ReportItemContext(node_label),
                            )
                        )
                    case SetConfigsResult.REJECTED:
                        self._report(
                            reports.ReportItem(
                                self._rejection_severity,
                                reports.messages.PcsCfgsyncConfigRejected(
                                    cfg_filetypecode
                                ),
                                context=reports.ReportItemContext(node_label),
                            )
                        )
                    case SetConfigsResult.ERROR:
                        # The api does not provide description of the error, so we
                        # just provide some generic error message
                        self._report(
                            reports.ReportItem.error(
                                reports.messages.PcsCfgsyncConfigSaveError(
                                    cfg_filetypecode,
                                ),
                                context=reports.ReportItemContext(node_label),
                            )
                        )
                    case SetConfigsResult.NOT_SUPPORTED:
                        self._report(
                            reports.ReportItem.error(
                                reports.messages.PcsCfgsyncConfigUnsupported(
                                    cfg_filetypecode
                                ),
                                context=reports.ReportItemContext(node_label),
                            )
                        )

                results[cfg_filetypecode] = normalized_cfg_result
            self._node_results[node_label] = results
        except (json.JSONDecodeError, KeyError, ValueError, AttributeError):
            self._report(
                reports.ReportItem.error(
                    reports.messages.InvalidResponseFormat(node_label)
                )
            )

        return []

    def on_complete(self) -> dict[str, dict[FileTypeCode, SetConfigsResult]]:
        return self._node_results
