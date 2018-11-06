from pcs.common.node_communicator import RequestData
from pcs.lib import reports
from pcs.lib.corosync import live as corosync_live
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    OneByOneStrategyMixin,
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


class GetQuorumStatus(AllSameDataMixin, OneByOneStrategyMixin, RunRemotelyBase):
    _quorum_status = None
    _has_failure = False

    def _get_request_data(self):
        return RequestData("remote/get_quorum_info")

    def _process_response(self, response):
        report = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        node = response.request.target.label
        if report is not None:
            self._has_failure = True
            self._report(report)
            return self._get_next_list()
        if response.data.strip() == "Cannot initialize CMAP service":
            # corosync is not running on the node, this is OK
            return self._get_next_list()
        try:
            quorum_status = corosync_live.QuorumStatus.from_string(
                response.data
            )
            if not quorum_status.is_quorate:
                return self._get_next_list()
            self._quorum_status = quorum_status
        except corosync_live.QuorumStatusParsingException as e:
            self._has_failure = True
            self._report(
                reports.corosync_quorum_get_status_error(
                    e.reason,
                    node=node,
                    severity=ReportItemSeverity.WARNING,
                )
            )
            return self._get_next_list()
        return []

    def on_complete(self):
        return self._has_failure, self._quorum_status
