import json

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
    def __init__(self, report_processor, devices):
        super().__init__(report_processor)
        self._devices = devices

    def _get_request_data(self):
        return None

    def _prepare_initial_requests(self):
        return [
            Request(
                target,
                RequestData(
                    "api/v1/scsi-unfence-node/v1",
                    data=json.dumps(
                        {"devices": self._devices, "node": target.label}
                    ),
                ),
            )
            for target in self._target_list
        ]

    def _process_response(self, response):
        report_item = response_to_report_item(response)
        if report_item:
            self._report(report_item)
            return
        node_label = response.request.target.label
        try:
            result = from_dict(
                InternalCommunicationResultDto, json.loads(response.data)
            )
            if result.status != const.COM_STATUS_SUCCESS:
                context = reports.ReportItemContext(node_label)
                self._report_list(
                    [
                        reports.report_dto_to_item(report, context)
                        for report in result.report_list
                    ]
                )
            else:
                self._on_success()

        except (json.JSONDecodeError, DaciteError):
            self._report(
                reports.ReportItem.error(
                    reports.messages.InvalidResponseFormat(node_label)
                )
            )
