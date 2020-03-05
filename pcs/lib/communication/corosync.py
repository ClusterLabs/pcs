import json

from pcs.common.node_communicator import RequestData
from pcs.common import reports as report
from pcs.common.reports import ReportItemSeverity
from pcs.common.reports.item import ReportItem
from pcs.lib import reports
from pcs.lib.communication.tools import (
    AllAtOnceStrategyMixin,
    AllSameDataMixin,
    OneByOneStrategyMixin,
    RunRemotelyBase,
    SkipOfflineMixin,
)
from pcs.lib.node_communication import response_to_report_item


class CheckCorosyncOffline(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(
        self, report_processor,
        skip_offline_targets=False, allow_skip_offline=True,
    ):
        super(CheckCorosyncOffline, self).__init__(report_processor)
        if allow_skip_offline:
            self._set_skip_offline(skip_offline_targets)

    def _get_request_data(self):
        return RequestData("remote/status")

    def _process_response(self, response):
        report_item = self._get_response_report(response)
        node_label = response.request.target.label
        if report_item is not None:
            self._report_list([
                report_item,
                ReportItem(
                    severity=ReportItemSeverity(
                        self._failure_severity,
                        self._failure_forceable,
                    ),
                    message=report.messages.CorosyncNotRunningCheckNodeError(
                        node_label,
                    )
                )
            ])
            return
        try:
            status = response.data
            if not json.loads(status)["corosync"]:
                report_item = ReportItem.info(
                    report.messages.CorosyncNotRunningOnNode(node_label),
                )
            else:
                report_item = ReportItem.error(
                    report.messages.CorosyncRunningOnNode(node_label),
                )
        except (KeyError, json.JSONDecodeError):
            report_item = ReportItem(
                severity=ReportItemSeverity(
                    self._failure_severity,
                    self._failure_forceable,
                ),
                message=report.messages.CorosyncNotRunningCheckNodeError(
                    node_label,
                )
            )
        self._report(report_item)

    def before(self):
        self._report(
            ReportItem.info(
                report.messages.CorosyncNotRunningCheckStarted()
            )
        )


class DistributeCorosyncConf(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(
        self, report_processor, config_text, skip_offline_targets=False,
        allow_skip_offline=True,
    ):
        super(DistributeCorosyncConf, self).__init__(report_processor)
        self._config_text = config_text
        if allow_skip_offline:
            self._set_skip_offline(skip_offline_targets)

    def _get_request_data(self):
        return RequestData(
            "remote/set_corosync_conf", [("corosync_conf", self._config_text)]
        )

    def _process_response(self, response):
        report_item = self._get_response_report(response)
        node_label = response.request.target.label
        if report_item is None:
            self._report(reports.corosync_config_accepted_by_node(node_label))
        else:
            self._report_list([
                report_item,
                ReportItem(
                    severity=ReportItemSeverity(
                        self._failure_severity,
                        self._failure_forceable,
                    ),
                    message=report.messages.CorosyncConfigDistributionNodeError(
                        node_label,
                    ),
                )
            ])

    def before(self):
        self._report(
            ReportItem.info(
                report.messages.CorosyncConfigDistributionStarted()
            )
        )


class ReloadCorosyncConf(
    AllSameDataMixin, OneByOneStrategyMixin, RunRemotelyBase
):
    __was_successful = False
    __has_failures = False

    def _get_request_data(self):
        return RequestData("remote/reload_corosync_conf")

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        node = response.request.target.label
        if report_item is not None:
            self.__has_failures = True
            self._report(report_item)
            return self._get_next_list()
        try:
            output = json.loads(response.data)
            if output["code"] == "reloaded":
                self.__was_successful = True
                self._report(
                    ReportItem.info(
                        report.messages.CorosyncConfigReloaded(node)
                    )
                )
                return []

            if output["code"] == "not_running":
                self._report(
                    ReportItem.warning(
                        report.messages.CorosyncConfigReloadNotPossible(node)
                    )
                )
            else:
                self.__has_failures = True
                self._report(
                    ReportItem.warning(
                        report.messages.CorosyncConfigReloadError(
                            output["message"],
                            node=node,
                        )
                    )
                )
        except (ValueError, LookupError):
            self.__has_failures = True
            self._report(reports.invalid_response_format(
                node,
                severity=ReportItemSeverity.WARNING,
            ))

        return self._get_next_list()

    def on_complete(self):
        if not self.__was_successful and self.__has_failures:
            self._report(reports.unable_to_perform_operation_on_any_node())


class GetCorosyncConf(
    AllSameDataMixin, OneByOneStrategyMixin, RunRemotelyBase
):
    __was_successful = False
    __has_failures = False
    __corosync_conf = None

    def _get_request_data(self):
        return RequestData("remote/get_corosync_conf")

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        if report_item is not None:
            self.__has_failures = True
            self._report(report_item)
            return self._get_next_list()
        self.__corosync_conf = response.data
        self.__was_successful = True
        return []

    def on_complete(self):
        if not self.__was_successful and self.__has_failures:
            self._report(reports.unable_to_perform_operation_on_any_node())
        return self.__corosync_conf
