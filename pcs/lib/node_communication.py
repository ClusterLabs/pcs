from typing import Mapping

from pcs.common import pcs_pycurl as pycurl
from pcs.common import reports
from pcs.common.host import PcsKnownHost
from pcs.common.node_communicator import (
    HostNotFound,
    NodeTargetFactory,
    RequestTarget,
)
from pcs.common.reports import (
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.common.reports.item import ReportItem, ReportItemList
from pcs.common.types import StringIterable
from pcs.lib.errors import LibraryError


class NodeTargetLibFactory(NodeTargetFactory):
    def __init__(
        self,
        known_hosts: Mapping[str, PcsKnownHost],
        report_processor: ReportProcessor,
    ):
        super().__init__(known_hosts)
        self._report_processor = report_processor

    def get_target_list_with_reports(
        self,
        host_name_list: StringIterable,
        skip_non_existing: bool = False,
        allow_skip: bool = True,
        report_none_host_found: bool = True,
    ) -> tuple[ReportItemList, list[RequestTarget]]:
        target_list = []
        unknown_host_list = []
        for host_name in host_name_list:
            try:
                target_list.append(self.get_target(host_name))
            except HostNotFound:
                unknown_host_list.append(host_name)

        report_list = []
        if unknown_host_list:
            report_list.append(
                ReportItem(
                    severity=reports.item.get_severity(
                        (
                            reports.codes.SKIP_OFFLINE_NODES
                            if allow_skip
                            else None
                        ),
                        skip_non_existing,
                    ),
                    message=reports.messages.HostNotFound(
                        sorted(unknown_host_list),
                    ),
                )
            )

        if not target_list and host_name_list and report_none_host_found:
            # we want to create this report only if there was at least one
            # required address specified
            report_list.append(
                ReportItem.error(reports.messages.NoneHostFound())
            )
        return report_list, target_list

    def get_target_list(
        self, host_name_list, skip_non_existing=False, allow_skip=True
    ):
        report_list, target_list = self.get_target_list_with_reports(
            host_name_list, skip_non_existing, allow_skip
        )
        if report_list:
            if self._report_processor.report_list(report_list).has_errors:
                raise LibraryError()
        return target_list


def response_to_report_item(
    response,
    severity=ReportItemSeverity.ERROR,
    forceable=None,
    report_pcsd_too_old_on_404=False,
):
    """
    Returns report item which corresponds to response if was not successful.
    Otherwise returns None.

    Response response -- response from which report item shoculd be created
    ReportItemseverity severity -- severity of report item
    string forceable -- force code
    bool report_pcsd_too_old_on_404 -- if False, report unsupported command
    """
    response_code = response.response_code
    report_item = None
    reason = None
    if (
        report_pcsd_too_old_on_404
        and response.was_connected
        and response_code == 404
    ):
        return ReportItem.error(
            reports.messages.PcsdVersionTooOld(response.request.host_label)
        )
    if response.was_connected:
        if response_code == 400:
            # old pcsd protocol: error messages are commonly passed in plain
            # text in response body with HTTP code 400
            # we need to be backward compatible with that
            report_item = reports.messages.NodeCommunicationCommandUnsuccessful
            reason = response.data.rstrip()
        elif response_code == 401:
            report_item = reports.messages.NodeCommunicationErrorNotAuthorized
            reason = f"HTTP error: {response_code}"
        elif response_code == 403:
            report_item = (
                reports.messages.NodeCommunicationErrorPermissionDenied
            )
            reason = f"HTTP error: {response_code}"
        elif response_code == 404:
            report_item = (
                reports.messages.NodeCommunicationErrorUnsupportedCommand
            )
            reason = f"HTTP error: {response_code}"
        elif response_code >= 400:
            report_item = reports.messages.NodeCommunicationError
            reason = f"HTTP error: {response_code}"
    elif response.errno in [
        pycurl.E_OPERATION_TIMEDOUT,
        pycurl.E_OPERATION_TIMEOUTED,
    ]:
        report_item = reports.messages.NodeCommunicationErrorTimedOut
        reason = response.error_msg
    else:
        report_item = reports.messages.NodeCommunicationErrorUnableToConnect
        reason = response.error_msg
    if not report_item:
        return None
    return ReportItem(
        severity=ReportItemSeverity(severity, forceable),
        message=report_item(
            response.request.host_label,
            response.request.action,
            reason,
        ),
    )
