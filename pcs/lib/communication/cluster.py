from pcs.common.node_communicator import RequestData
from pcs.lib import reports
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SkipOfflineMixin,
    SimpleResponseProcessingMixin,
)
from pcs.lib.errors import ReportItemSeverity
from pcs.lib.node_communication import response_to_report_item


class Destroy(
    AllSameDataMixin, AllAtOnceStrategyMixin, SkipOfflineMixin,
    SimpleResponseProcessingMixin, RunRemotelyBase
):
    def _get_request_data(self):
        return RequestData("remote/cluster_destroy")

    def _get_success_report(self, node_label):
        return reports.cluster_destroy_success(node_label)

    def before(self):
        self._set_skip_offline(False, force_code=None)
        self._report(reports.cluster_destroy_started(self._target_label_list))


class DestroyWarnOnFailure(
    AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    _unreachable_nodes = None

    def _get_request_data(self):
        return RequestData("remote/cluster_destroy")

    def _process_response(self, response):
        report = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        node_label = response.request.target.label
        if report is None:
            self._report(reports.cluster_destroy_success(node_label))
        else:
            self._report(report)
            self._unreachable_nodes.append(node_label)

    def before(self):
        self._report(reports.cluster_destroy_started(self._target_label_list))
        self._unreachable_nodes = []

    def on_complete(self):
        if self._unreachable_nodes:
            self._report(
                reports.nodes_to_remove_unreachable(self._unreachable_nodes)
            )
