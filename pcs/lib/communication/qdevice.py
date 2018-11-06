from pcs.common.node_communicator import RequestData
from pcs.lib import reports
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SkipOfflineMixin,
    SimpleResponseProcessingMixin,
)


class QdeviceBase(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    #pylint: disable=abstract-method
    def __init__(self, report_processor, skip_offline_targets=False):
        super(QdeviceBase, self).__init__(report_processor)
        self._set_skip_offline(skip_offline_targets)


class Stop(SimpleResponseProcessingMixin, QdeviceBase):
    # pylint: disable=too-many-ancestors
    def _get_request_data(self):
        return RequestData("remote/qdevice_client_stop")

    def _get_success_report(self, node_label):
        return reports.service_stop_success("corosync-qdevice", node_label)


class Start(QdeviceBase):
    def _get_request_data(self):
        return RequestData("remote/qdevice_client_start")

    def _process_response(self, response):
        report = self._get_response_report(response)
        node_label = response.request.target.label
        if report is None:
            if response.data == "corosync is not running, skipping":
                report = reports.service_start_skipped(
                    "corosync-qdevice",
                    "corosync is not running",
                    node_label
                )
            else:
                report = reports.service_start_success(
                    "corosync-qdevice", node_label
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
                report = reports.service_enable_skipped(
                    "corosync-qdevice",
                    "corosync is not enabled",
                    node_label
                )
            else:
                report = reports.service_enable_success(
                    "corosync-qdevice", node_label
                )
        self._report(report)


class Disable(SimpleResponseProcessingMixin, QdeviceBase):
    def _get_request_data(self):
        return RequestData("remote/qdevice_client_disable")

    def _get_success_report(self, node_label):
        return reports.service_disable_success("corosync-qdevice", node_label)
