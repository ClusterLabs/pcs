import json
from typing import Optional

from pcs.common import reports
from pcs.common.node_communicator import (
    Request,
    RequestData,
    RequestTarget,
    Response,
)
from pcs.common.reports import ReportItemSeverity
from pcs.common.reports.item import ReportItem
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
        self,
        report_processor: reports.ReportProcessor,
        skip_offline_targets: bool = False,
        allow_skip_offline: bool = True,
    ):
        super().__init__(report_processor)
        if allow_skip_offline:
            self._set_skip_offline(skip_offline_targets)
        self._corosync_running_target_list: list[RequestTarget] = []

    def _get_request_data(self) -> RequestData:
        return RequestData("remote/status", [("version", "2")])

    def _process_response(self, response: Response) -> list[Request]:
        report_item = self._get_response_report(response)
        node_label = response.request.target.label
        if report_item is not None:
            self._report_list(
                [
                    report_item,
                    ReportItem(
                        severity=ReportItemSeverity(
                            self._failure_severity,
                            self._failure_forceable,
                        ),
                        message=(
                            reports.messages.CorosyncNotRunningCheckNodeError(
                                node_label,
                            )
                        ),
                    ),
                ]
            )
            return []
        try:
            status = response.data
            if not json.loads(status)["node"]["corosync"]:
                report_item = ReportItem.info(
                    reports.messages.CorosyncNotRunningCheckNodeStopped(
                        node_label
                    ),
                )
            else:
                report_item = ReportItem.error(
                    reports.messages.CorosyncNotRunningCheckNodeRunning(
                        node_label
                    ),
                )
                self._corosync_running_target_list.append(
                    response.request.target
                )
        except (KeyError, json.JSONDecodeError):
            report_item = ReportItem(
                severity=ReportItemSeverity(
                    self._failure_severity,
                    self._failure_forceable,
                ),
                message=reports.messages.CorosyncNotRunningCheckNodeError(
                    node_label,
                ),
            )
        self._report(report_item)
        return []

    def before(self) -> None:
        self._report(
            ReportItem.info(reports.messages.CorosyncNotRunningCheckStarted())
        )

    def on_complete(self) -> list[RequestTarget]:
        return self._corosync_running_target_list


class GetCorosyncOnlineTargets(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(
        self,
        report_processor: reports.ReportProcessor,
        skip_offline_targets: bool = False,
        allow_skip_offline: bool = True,
    ):
        super().__init__(report_processor)
        if allow_skip_offline:
            self._set_skip_offline(skip_offline_targets)
        self._corosync_online_target_list: list[RequestTarget] = []

    def _get_request_data(self) -> RequestData:
        return RequestData("remote/status", [("version", "2")])

    def _process_response(self, response: Response) -> list[Request]:
        report_item = self._get_response_report(response)
        if report_item:
            self._report(report_item)
            return []
        try:
            status = response.data
            if json.loads(status)["node"]["corosync"]:
                self._corosync_online_target_list.append(
                    response.request.target
                )
        except (KeyError, json.JSONDecodeError):
            self._report(
                reports.ReportItem.error(
                    reports.messages.InvalidResponseFormat(
                        response.request.target.label
                    )
                )
            )
        return []

    def on_complete(self) -> list[RequestTarget]:
        return self._corosync_online_target_list


class DistributeCorosyncConf(
    SkipOfflineMixin, AllSameDataMixin, AllAtOnceStrategyMixin, RunRemotelyBase
):
    def __init__(
        self,
        report_processor: reports.ReportProcessor,
        config_text: str,
        skip_offline_targets: bool = False,
        allow_skip_offline: bool = True,
    ):
        super().__init__(report_processor)
        self._config_text = config_text
        if allow_skip_offline:
            self._set_skip_offline(skip_offline_targets)

    def _get_request_data(self) -> RequestData:
        return RequestData(
            "remote/set_corosync_conf", [("corosync_conf", self._config_text)]
        )

    def _process_response(self, response: Response) -> list[Request]:
        report_item = self._get_response_report(response)
        node_label = response.request.target.label
        if report_item is None:
            self._report(
                ReportItem.info(
                    reports.messages.CorosyncConfigAcceptedByNode(node_label)
                )
            )
        else:
            self._report_list(
                [
                    report_item,
                    ReportItem(
                        severity=ReportItemSeverity(
                            self._failure_severity,
                            self._failure_forceable,
                        ),
                        message=reports.messages.CorosyncConfigDistributionNodeError(
                            node_label,
                        ),
                    ),
                ]
            )
        return []

    def before(self) -> None:
        self._report(
            ReportItem.info(
                reports.messages.CorosyncConfigDistributionStarted()
            )
        )


class ReloadCorosyncConf(
    AllSameDataMixin, OneByOneStrategyMixin, RunRemotelyBase
):
    __was_successful = False
    __has_failures = False

    def _get_request_data(self) -> RequestData:
        return RequestData("remote/reload_corosync_conf")

    def _process_response(self, response: Response) -> list[Request]:
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
                        reports.messages.CorosyncConfigReloaded(node)
                    )
                )
                return []

            if output["code"] == "not_running":
                self._report(
                    ReportItem.warning(
                        reports.messages.CorosyncConfigReloadNotPossible(node)
                    )
                )
            else:
                self.__has_failures = True
                message = "\n".join(
                    line.strip()
                    for line in output["message"].split("\n")
                    if line.strip()
                )
                self._report(
                    ReportItem.warning(
                        reports.messages.CorosyncConfigReloadError(
                            message, node=node
                        )
                    )
                )
        except (ValueError, LookupError):
            self.__has_failures = True
            self._report(
                ReportItem.warning(reports.messages.InvalidResponseFormat(node))
            )

        return self._get_next_list()

    def on_complete(self) -> None:
        # corosync-cfgtool -R actually does not report issues with reload
        # from nodes other than the local node
        # We should eventually change this so that we run the reload on each
        # node one-by-one, to see issues from all cluster nodes.
        # For now, we want to print this warning even in case the reload was
        # successful on the last node.
        if self.__has_failures:
            self._report(
                ReportItem.warning(
                    reports.messages.CorosyncConfigInvalidPreventsClusterJoin()
                )
            )
        if not self.__was_successful and self.__has_failures:
            self._report(
                ReportItem.error(
                    reports.messages.UnableToPerformOperationOnAnyNode()
                )
            )


class GetCorosyncConf(AllSameDataMixin, OneByOneStrategyMixin, RunRemotelyBase):
    __was_successful = False
    __has_failures = False
    __corosync_conf = None

    def _get_request_data(self) -> RequestData:
        return RequestData("remote/get_corosync_conf")

    def _process_response(self, response: Response) -> list[Request]:
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

    def on_complete(self) -> Optional[str]:
        if not self.__was_successful and self.__has_failures:
            self._report(
                ReportItem.error(
                    reports.messages.UnableToPerformOperationOnAnyNode()
                )
            )
        return self.__corosync_conf
