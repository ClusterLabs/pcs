from typing import Optional

from pcs.common import reports
from pcs.common.node_communicator import RequestData
from pcs.common.reports.item import ReportItem
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    OneByOneStrategyMixin,
    RunRemotelyBase,
    SimpleResponseProcessingMixin,
    SkipOfflineMixin,
)
from pcs.lib.corosync.live import (
    QuorumStatusException,
    QuorumStatusFacade,
)
from pcs.lib.node_communication import response_to_report_item


class Destroy(
    AllSameDataMixin,
    AllAtOnceStrategyMixin,
    SkipOfflineMixin,
    SimpleResponseProcessingMixin,
    RunRemotelyBase,
):
    def _get_request_data(self):
        return RequestData("remote/cluster_destroy")

    def _get_success_report(self, node_label):
        return ReportItem.info(
            reports.messages.ClusterDestroySuccess(node_label)
        )

    def before(self):
        self._set_skip_offline(False, force_code=None)
        self._report(
            ReportItem.info(
                reports.messages.ClusterDestroyStarted(
                    sorted(self._target_label_list)
                )
            )
        )


class DestroyWarnOnFailure(
    AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    _unreachable_nodes = None

    def _get_request_data(self):
        return RequestData("remote/cluster_destroy")

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, severity=reports.ReportItemSeverity.WARNING
        )
        node_label = response.request.target.label
        if report_item is None:
            self._report(
                ReportItem.info(
                    reports.messages.ClusterDestroySuccess(node_label)
                )
            )
        else:
            self._report(report_item)
            self._unreachable_nodes.append(node_label)

    def before(self):
        self._report(
            ReportItem.info(
                reports.messages.ClusterDestroyStarted(
                    sorted(self._target_label_list)
                )
            )
        )
        self._unreachable_nodes = []

    def on_complete(self):
        if self._unreachable_nodes:
            self._report(
                ReportItem.warning(
                    reports.messages.NodesToRemoveUnreachable(
                        sorted(self._unreachable_nodes)
                    )
                )
            )


class GetQuorumStatus(AllSameDataMixin, OneByOneStrategyMixin, RunRemotelyBase):
    _quorum_status_facade: Optional[QuorumStatusFacade] = None
    _has_failure: Optional[bool] = False

    def _get_request_data(self):
        return RequestData("remote/get_quorum_info")

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, severity=reports.ReportItemSeverity.WARNING
        )
        node = response.request.target.label
        if report_item is not None:
            self._has_failure = True
            self._report(report_item)
            return self._get_next_list()
        if response.data.strip() == "Cannot initialize CMAP service":
            # corosync is not running on the node, this is OK
            return self._get_next_list()
        try:
            quorum_status_facade = QuorumStatusFacade.from_string(response.data)
            if not quorum_status_facade.is_quorate:
                return self._get_next_list()
            self._quorum_status_facade = quorum_status_facade
        except QuorumStatusException as e:
            self._has_failure = True
            self._report(
                ReportItem.warning(
                    reports.messages.CorosyncQuorumGetStatusError(
                        e.reason,
                        node=node,
                    )
                )
            )
            return self._get_next_list()
        return []

    def on_complete(
        self,
    ) -> tuple[Optional[bool], Optional[QuorumStatusFacade]]:
        return self._has_failure, self._quorum_status_facade
