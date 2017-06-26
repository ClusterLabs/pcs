from __future__ import (
    absolute_import,
    division,
    print_function,
)

import json

from pcs.common.node_communicator import RequestData
from pcs.lib import reports
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    RunRemotelyBase,
    SkipOfflineMixin,
)


class CheckCorosyncOffline(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(self, report_processor, skip_offline_targets=False):
        super(CheckCorosyncOffline, self).__init__(report_processor)
        self._set_skip_offline(skip_offline_targets)

    def _get_request_data(self):
        return RequestData("remote/status")

    def _process_response(self, response):
        report = self._get_response_report(response)
        node_label = response.request.target.label
        if report is not None:
            self._report_list([
                report,
                reports.corosync_not_running_check_node_error(
                    node_label,
                    self._failure_severity,
                    self._failure_forceable,
                )
            ])
            return
        try:
            status = response.data
            if not json.loads(status)["corosync"]:
                report = reports.corosync_not_running_on_node_ok(node_label)
            else:
                report = reports.corosync_running_on_node_fail(node_label)
        except (ValueError, LookupError):
            report = reports.corosync_not_running_check_node_error(
                node_label, self._failure_severity, self._failure_forceable
            )
        self._report(report)

    def before(self):
        self._report(reports.corosync_not_running_check_started())


class DistributeCorosyncConf(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(
        self, report_processor, config_text, skip_offline_targets=False
    ):
        super(DistributeCorosyncConf, self).__init__(report_processor)
        self._config_text = config_text
        self._set_skip_offline(skip_offline_targets)

    def _get_request_data(self):
        return RequestData(
            "remote/set_corosync_conf", [("corosync_conf", self._config_text)]
        )

    def _process_response(self, response):
        report = self._get_response_report(response)
        node_label = response.request.target.label
        if report is None:
            self._report(reports.corosync_config_accepted_by_node(node_label))
        else:
            self._report_list([
                report,
                reports.corosync_not_running_check_node_error(
                    node_label,
                    self._failure_severity,
                    self._failure_forceable,
                )
            ])

    def before(self):
        self._report(reports.corosync_config_distribution_started())

