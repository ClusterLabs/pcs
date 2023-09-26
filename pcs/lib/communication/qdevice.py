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


class QdeviceBase(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    # pylint: disable=abstract-method
    def __init__(self, report_processor, skip_offline_targets=False):
        super().__init__(report_processor)
        self._set_skip_offline(skip_offline_targets)


class Stop(SimpleResponseProcessingMixin, QdeviceBase):
    def _get_request_data(self):
        return RequestData("remote/qdevice_client_stop")

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_STOP,
                "corosync-qdevice",
                node_label,
            )
        )


class Start(QdeviceBase):
    def _get_request_data(self):
        return RequestData("remote/qdevice_client_start")

    def _process_response(self, response):
        report = self._get_response_report(response)
        node_label = response.request.target.label
        if report is None:
            if response.data == "corosync is not running, skipping":
                report = ReportItem.info(
                    reports.messages.ServiceActionSkipped(
                        reports.const.SERVICE_ACTION_START,
                        "corosync-qdevice",
                        "corosync is not running",
                        node_label,
                    )
                )
            else:
                report = ReportItem.info(
                    reports.messages.ServiceActionSucceeded(
                        reports.const.SERVICE_ACTION_START,
                        "corosync-qdevice",
                        node_label,
                    )
                )
        self._report(report)


class Enable(QdeviceBase):
    def _get_request_data(self):
        return RequestData("remote/qdevice_client_enable")

    def _process_response(self, response):
        report = self._get_response_report(response)
        node_label = response.request.target.label
        if report is None:
            if response.data == "corosync is not enabled, skipping":
                report = ReportItem.info(
                    reports.messages.ServiceActionSkipped(
                        reports.const.SERVICE_ACTION_ENABLE,
                        "corosync-qdevice",
                        "corosync is not enabled",
                        node_label,
                    )
                )
            else:
                report = ReportItem.info(
                    reports.messages.ServiceActionSucceeded(
                        reports.const.SERVICE_ACTION_ENABLE,
                        "corosync-qdevice",
                        node_label,
                    )
                )
        self._report(report)


class Disable(SimpleResponseProcessingMixin, QdeviceBase):
    def _get_request_data(self):
        return RequestData("remote/qdevice_client_disable")

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.ServiceActionSucceeded(
                reports.const.SERVICE_ACTION_DISABLE,
                "corosync-qdevice",
                node_label,
            )
        )
