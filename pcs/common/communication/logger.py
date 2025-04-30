import os
from typing import Iterable, Optional

from pcs import settings
from pcs.common.node_communicator import (
    CommunicatorLoggerInterface,
    Destination,
    Request,
    Response,
)
from pcs.common.reports import ReportItem, ReportProcessor, messages
from pcs.lib.external import is_proxy_set


def _get_port(port: Optional[int]) -> int:
    return port if port is not None else settings.pcsd_default_port


class CommunicatorLogger(CommunicatorLoggerInterface):
    def __init__(self, reporters: Iterable[ReportProcessor]):
        self._reporters = reporters

    def _log_report_to_all_reporters(self, msg: ReportItem) -> None:
        for reporter in self._reporters:
            reporter.report(msg)

    def log_request_start(self, request: Request) -> None:
        self._log_report_to_all_reporters(
            ReportItem.debug(
                messages.NodeCommunicationStarted(request.url, request.data)
            )
        )

    def log_response(self, response: Response) -> None:
        if response.was_connected:
            self._log_response_successful(response)
        else:
            self._log_response_failure(response)
        self._log_debug(response)

    def _log_response_successful(self, response: Response) -> None:
        self._log_report_to_all_reporters(
            ReportItem.debug(
                messages.NodeCommunicationFinished(
                    response.request.url,
                    response.response_code,  # type: ignore
                    response.data,
                )
            )
        )

    def _log_response_failure(self, response: Response) -> None:
        self._log_report_to_all_reporters(
            ReportItem.debug(
                messages.NodeCommunicationNotConnected(
                    response.request.host_label, response.error_msg or ""
                )
            )
        )
        if is_proxy_set(os.environ):
            self._log_report_to_all_reporters(
                ReportItem.warning(
                    messages.NodeCommunicationProxyIsSet(
                        response.request.host_label, response.request.dest.addr
                    )
                )
            )

    def _log_debug(self, response: Response) -> None:
        self._log_report_to_all_reporters(
            ReportItem.debug(
                messages.NodeCommunicationDebugInfo(
                    response.request.url, response.debug
                )
            )
        )

    def log_retry(self, response: Response, previous_dest: Destination) -> None:
        self._log_report_to_all_reporters(
            ReportItem.warning(
                messages.NodeCommunicationRetrying(
                    response.request.host_label,
                    previous_dest.addr,
                    str(_get_port(previous_dest.port)),
                    response.request.dest.addr,
                    str(_get_port(response.request.dest.port)),
                    response.request.url,
                )
            )
        )

    def log_no_more_addresses(self, response: Response) -> None:
        self._log_report_to_all_reporters(
            ReportItem.warning(
                messages.NodeCommunicationNoMoreAddresses(
                    response.request.host_label, response.request.url
                )
            )
        )
