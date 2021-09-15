import json
from typing import Iterable

from dacite import DaciteError

from pcs.common import reports
from pcs.common.node_communicator import (
    Request,
    RequestData,
)
from pcs.common.interface.dto import from_dict
from pcs.common.communication import const
from pcs.common.communication.dto import InternalCommunicationResultDto

from pcs.lib.node_communication import response_to_report_item
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    MarkSuccessfulMixin,
    RunRemotelyBase,
)


class Unfence(
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    MarkSuccessfulMixin,
    RunRemotelyBase,
):
    def __init__(
        self,
        report_processor: reports.ReportProcessor,
        original_devices: Iterable[str],
        updated_devices: Iterable[str],
    ) -> None:
        super().__init__(report_processor)
        self._original_devices = original_devices
        self._updated_devices = updated_devices

    def _get_request_data(self):
        return None

    def _prepare_initial_requests(self):
        return [
            Request(
                target,
                RequestData(
                    "api/v1/scsi-unfence-node/v2",
                    data=json.dumps(
                        dict(
                            node=target.label,
                            original_devices=self._original_devices,
                            updated_devices=self._updated_devices,
                        )
                    ),
                ),
            )
            for target in self._target_list
        ]

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, report_pcsd_too_old_on_404=True
        )
        if report_item:
            self._report(report_item)
            return
        node_label = response.request.target.label
        try:
            result = from_dict(
                InternalCommunicationResultDto, json.loads(response.data)
            )
            context = reports.ReportItemContext(node_label)
            self._report_list(
                [
                    reports.report_dto_to_item(report, context)
                    for report in result.report_list
                ]
            )
            if result.status == const.COM_STATUS_SUCCESS:
                self._on_success()

        except (json.JSONDecodeError, DaciteError):
            self._report(
                reports.ReportItem.error(
                    reports.messages.InvalidResponseFormat(node_label)
                )
            )
