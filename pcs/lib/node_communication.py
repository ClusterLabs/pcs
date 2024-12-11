import os

from pcs import settings
from pcs.common import pcs_pycurl as pycurl
from pcs.common import reports
from pcs.common.node_communicator import (
    CommunicatorLoggerInterface,
    HostNotFound,
    NodeTargetFactory,
)
from pcs.common.reports import (
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.common.reports.item import ReportItem
from pcs.lib.errors import LibraryError


def _get_port(port):
    return port if port is not None else settings.pcsd_default_port


class LibCommunicatorLogger(CommunicatorLoggerInterface):
    def __init__(self, logger, reporter: ReportProcessor):
        self._logger = logger
        self._reporter = reporter

    def log_request_start(self, request):
        msg = "Sending HTTP Request to: {url}"
        if request.data:
            msg += "\n--Debug Input Start--\n{data}\n--Debug Input End--"
        self._logger.debug(msg.format(url=request.url, data=request.data))
        self._reporter.report(
            ReportItem.debug(
                reports.messages.NodeCommunicationStarted(
                    request.url,
                    request.data,
                )
            )
        )

    def log_response(self, response):
        if response.was_connected:
            self._log_response_successful(response)
        else:
            self._log_response_failure(response)
        self._log_debug(response)

    def _log_response_successful(self, response):
        url = response.request.url
        msg = (
            "Finished calling: {url}\nResponse Code: {code}"
            + "\n--Debug Response Start--\n{response}\n--Debug Response End--"
        )
        self._logger.debug(
            msg.format(
                url=url, code=response.response_code, response=response.data
            )
        )
        self._reporter.report(
            ReportItem.debug(
                reports.messages.NodeCommunicationFinished(
                    url,
                    response.response_code,
                    response.data,
                )
            )
        )

    def _log_response_failure(self, response):
        msg = "Unable to connect to {node} ({reason})"
        self._logger.debug(
            msg.format(
                node=response.request.host_label, reason=response.error_msg
            )
        )
        self._reporter.report(
            ReportItem.debug(
                reports.messages.NodeCommunicationNotConnected(
                    response.request.host_label,
                    response.error_msg,
                )
            )
        )
        if is_proxy_set(os.environ):
            self._logger.warning("Proxy is set")
            self._reporter.report(
                ReportItem.warning(
                    reports.messages.NodeCommunicationProxyIsSet(
                        response.request.host_label,
                        response.request.dest.addr,
                    )
                )
            )

    def _log_debug(self, response):
        url = response.request.url
        debug_data = response.debug
        self._logger.debug(
            "Communication debug info for calling: %s\n"
            "--Debug Communication Info Start--\n"
            "%s\n"
            "--Debug Communication Info End--",
            url,
            debug_data,
        )
        self._reporter.report(
            ReportItem.debug(
                reports.messages.NodeCommunicationDebugInfo(url, debug_data)
            )
        )

    def log_retry(self, response, previous_dest):
        old_port = _get_port(previous_dest.port)
        new_port = _get_port(response.request.dest.port)
        msg = (
            "Unable to connect to '{label}' via address '{old_addr}' and port "
            "'{old_port}'. Retrying request '{req}' via address '{new_addr}' "
            "and port '{new_port}'"
        ).format(
            label=response.request.host_label,
            old_addr=previous_dest.addr,
            old_port=old_port,
            new_addr=response.request.dest.addr,
            new_port=new_port,
            req=response.request.url,
        )
        self._logger.warning(msg)
        self._reporter.report(
            ReportItem.warning(
                reports.messages.NodeCommunicationRetrying(
                    response.request.host_label,
                    previous_dest.addr,
                    old_port,
                    response.request.dest.addr,
                    new_port,
                    response.request.url,
                )
            )
        )

    def log_no_more_addresses(self, response):
        msg = "No more addresses for node {label} to run '{req}'".format(
            label=response.request.host_label,
            req=response.request.url,
        )
        self._logger.warning(msg)
        self._reporter.report(
            ReportItem.warning(
                reports.messages.NodeCommunicationNoMoreAddresses(
                    response.request.host_label,
                    response.request.url,
                )
            )
        )


class NodeTargetLibFactory(NodeTargetFactory):
    def __init__(self, known_hosts, report_processor: ReportProcessor):
        super().__init__(known_hosts)
        self._report_processor = report_processor

    def get_target_list_with_reports(
        self,
        host_name_list,
        skip_non_existing=False,
        allow_skip=True,
        report_none_host_found=True,
    ):
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
    else:
        if response.errno in [
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


def is_proxy_set(env_dict):
    """
    Returns True whenever any of proxy environment variables (https_proxy,
    HTTPS_PROXY, all_proxy, ALL_PROXY) are set in env_dict. False otherwise.

    dict env_dict -- environment variables in dict
    """
    proxy_list = ["https_proxy", "all_proxy"]
    for var in proxy_list + [v.upper() for v in proxy_list]:
        if env_dict.get(var, "") != "":
            return True
    return False
