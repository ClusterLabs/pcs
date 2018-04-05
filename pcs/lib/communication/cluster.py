from pcs.common.node_communicator import RequestData
from pcs.lib import reports
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SkipOfflineMixin,
    SimpleResponseProcessingMixin,
)


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
