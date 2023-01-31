import json
from typing import Dict

from dacite import DaciteError

from pcs.common import reports
from pcs.common.communication import const
from pcs.common.communication.dto import InternalCommunicationResultDto
from pcs.common.interface.dto import from_dict
from pcs.common.node_communicator import (
    Request,
    RequestData,
)
from pcs.common.types import StringIterable
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    MarkSuccessfulMixin,
    RunRemotelyBase,
)
from pcs.lib.node_communication import response_to_report_item


class Unfence(
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    MarkSuccessfulMixin,
    RunRemotelyBase,
):
    def __init__(
        self,
        report_processor: reports.ReportProcessor,
        original_devices: StringIterable,
        updated_devices: StringIterable,
    ) -> None:
        super().__init__(report_processor)
        self._original_devices = list(original_devices)
        self._updated_devices = list(updated_devices)

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


class UnfenceMpath(Unfence):
    def __init__(
        self,
        report_processor: reports.ReportProcessor,
        original_devices: StringIterable,
        updated_devices: StringIterable,
        node_key_map: Dict[str, str],
    ) -> None:
        super().__init__(report_processor, original_devices, updated_devices)
        self._node_key_map = node_key_map

    def _prepare_initial_requests(self):
        return [
            Request(
                target,
                RequestData(
                    "api/v1/scsi-unfence-node-mpath/v1",
                    data=json.dumps(
                        dict(
                            key=self._node_key_map[target.label],
                            original_devices=self._original_devices,
                            updated_devices=self._updated_devices,
                        )
                    ),
                ),
            )
            for target in self._target_list
        ]
