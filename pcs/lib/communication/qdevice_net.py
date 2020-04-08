import base64
import binascii

from pcs.common import reports
from pcs.common.node_communicator import (
    Request,
    RequestData,
)
from pcs.common.reports.item import ReportItem
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SkipOfflineMixin,
    SimpleResponseProcessingMixin,
    SimpleResponseProcessingNoResponseOnSuccessMixin,
)
from pcs.lib.communication.qdevice import QdeviceBase


class GetCaCert(AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super(GetCaCert, self).__init__(report_processor)
        self._data = []

    def _get_request_data(self):
        return RequestData("remote/qdevice_net_get_ca_certificate")

    def _process_response(self, response):
        report = self._get_response_report(response)
        if report is not None:
            self._report(report)
            return
        target = response.request.target
        try:
            self._data.append((target, base64.b64decode(response.data)))
        except (TypeError, binascii.Error):
            self._report(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(target.label)
                )
            )

    def on_complete(self):
        return self._data


class ClientSetup(
    SimpleResponseProcessingNoResponseOnSuccessMixin,
    SkipOfflineMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def __init__(
        self,
        report_processor,
        ca_cert,
        skip_offline_targets=False,
        allow_skip_offline=True,
    ):
        super(ClientSetup, self).__init__(report_processor)
        if allow_skip_offline:
            self._set_skip_offline(skip_offline_targets)
        self._ca_cert = ca_cert

    def _get_request_data(self):
        return RequestData(
            "remote/qdevice_net_client_init_certificate_storage",
            [("ca_certificate", base64.b64encode(self._ca_cert))],
        )


class SignCertificate(AllAtOnceStrategyMixin, RunRemotelyBase):
    def __init__(self, report_processor):
        super(SignCertificate, self).__init__(report_processor)
        self._output_data = []
        self._input_data = []

    def add_request(self, target, cert, cluster_name):
        self._input_data.append((target, cert, cluster_name))

    def _prepare_initial_requests(self):
        return [
            Request(
                target,
                RequestData(
                    "remote/qdevice_net_sign_node_certificate",
                    [
                        ("certificate_request", base64.b64encode(cert)),
                        ("cluster_name", cluster_name),
                    ],
                ),
            )
            for target, cert, cluster_name in self._input_data
        ]

    def _process_response(self, response):
        report = self._get_response_report(response)
        if report is not None:
            self._report(report)
            return
        target = response.request.target
        try:
            self._output_data.append((target, base64.b64decode(response.data)))
        except (TypeError, binascii.Error):
            self._report(
                ReportItem.error(
                    reports.messages.InvalidResponseFormat(target.label)
                )
            )

    def on_complete(self):
        return self._output_data


class ClientImportCertificateAndKey(
    SimpleResponseProcessingMixin,
    SkipOfflineMixin,
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    RunRemotelyBase,
):
    def __init__(
        self,
        report_processor,
        pk12,
        skip_offline_targets=False,
        allow_skip_offline=True,
    ):
        super(ClientImportCertificateAndKey, self).__init__(report_processor)
        if allow_skip_offline:
            self._set_skip_offline(skip_offline_targets)
        self._pk12 = pk12

    def _get_request_data(self):
        return RequestData(
            "remote/qdevice_net_client_import_certificate",
            [("certificate", base64.b64encode(self._pk12))],
        )

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.QdeviceCertificateAcceptedByNode(node_label)
        )


class ClientDestroy(SimpleResponseProcessingMixin, QdeviceBase):
    def _get_request_data(self):
        return RequestData("remote/qdevice_net_client_destroy")

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.QdeviceCertificateRemovedFromNode(node_label)
        )
