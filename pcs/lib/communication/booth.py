import base64
import json

from pcs.common import reports
from pcs.common.node_communicator import RequestData
from pcs.common.reports.item import ReportItem
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SimpleResponseProcessingMixin,
    SkipOfflineMixin,
)


class BoothSendConfig(
    SimpleResponseProcessingMixin,
    SkipOfflineMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    # TODO adapt to new file transfer framework once it is written
    def __init__(
        self,
        report_processor,
        booth_name,
        config_data,
        authfile=None,
        authfile_data=None,
        skip_offline_targets=False,
    ):
        super().__init__(report_processor)
        self._set_skip_offline(skip_offline_targets)
        self._booth_name = booth_name
        self._config_data = config_data.decode("utf-8")
        self._authfile = authfile
        self._authfile_data = authfile_data

    def _get_request_data(self):
        data = {
            "config": {
                "name": f"{self._booth_name}.conf",
                "data": self._config_data,
            }
        }
        if self._authfile is not None and self._authfile_data is not None:
            data["authfile"] = {
                "name": self._authfile,
                "data": base64.b64encode(self._authfile_data).decode("utf-8"),
            }
        return RequestData(
            "remote/booth_set_config", [("data_json", json.dumps(data))]
        )

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.BoothConfigAcceptedByNode(
                node=node_label,
                name_list=[self._booth_name],
            )
        )

    def before(self):
        self._report(
            ReportItem.info(reports.messages.BoothConfigDistributionStarted())
        )


class ProcessJsonDataMixin:
    __data = None

    @property
    def _data(self):
        if self.__data is None:
            self.__data = []
        return self.__data

    def _process_response(self, response):
        report = self._get_response_report(response)
        if report is not None:
            self._report(report)
            return
        target = response.request.target
        try:
            self._data.append((target, json.loads(response.data)))
        except ValueError:
            self._report(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(target.label)
                )
            )

    def on_complete(self):
        return self._data


class BoothGetConfig(
    ProcessJsonDataMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def __init__(self, report_processor, booth_name):
        super().__init__(report_processor)
        self._booth_name = booth_name

    def _get_request_data(self):
        return RequestData(
            "remote/booth_get_config", [("name", self._booth_name)]
        )


class BoothSaveFiles(
    ProcessJsonDataMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def __init__(self, report_processor, file_list, rewrite_existing=True):
        super().__init__(report_processor)
        self._file_list = file_list
        self._rewrite_existing = rewrite_existing
        self._output_data = []

    def _get_request_data(self):
        data = [("data_json", json.dumps(self._file_list))]
        if self._rewrite_existing:
            data.append(("rewrite_existing", "1"))
        return RequestData("remote/booth_save_files", data)

    def _process_response(self, response):
        report = self._get_response_report(response)
        if report is not None:
            self._report(report)
            return
        target = response.request.target
        try:
            parsed_data = json.loads(response.data)
            self._report(
                ReportItem.info(
                    reports.messages.BoothConfigAcceptedByNode(
                        node=target.label,
                        name_list=sorted(parsed_data["saved"]),
                    )
                )
            )
            for filename in list(parsed_data["existing"]):
                self._report(
                    ReportItem(
                        severity=reports.item.get_severity(
                            reports.codes.FORCE,
                            self._rewrite_existing,
                        ),
                        message=reports.messages.FileAlreadyExists(
                            # TODO specify file type; this will be overhauled
                            # to a generic file transport framework anyway
                            "",
                            filename,
                            node=target.label,
                        ),
                    )
                )
            for file, reason in dict(parsed_data["failed"]).items():
                self._report(
                    ReportItem.error(
                        reports.messages.BoothConfigDistributionNodeError(
                            target.label,
                            reason,
                            file,
                        )
                    )
                )
        except (KeyError, TypeError, ValueError):
            self._report(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(target.label)
                )
            )
