import json
from typing import Tuple

from pcs.common import reports
from pcs.common.node_communicator import RequestData
from pcs.common.reports import ReportItemSeverity
from pcs.common.reports.item import ReportItem
from pcs.lib.communication.tools import (
    AllSameDataMixin,
    OneByOneStrategyMixin,
    RunRemotelyBase,
)
from pcs.lib.node_communication import response_to_report_item


class GetFullClusterStatusPlaintext(
    AllSameDataMixin, OneByOneStrategyMixin, RunRemotelyBase
):
    def __init__(
        self, report_processor, hide_inactive_resources=False, verbose=False
    ):
        super().__init__(report_processor)
        self._hide_inactive_resources = hide_inactive_resources
        self._verbose = verbose
        self._cluster_status = ""
        self._was_successful = False

    def _get_request_data(self):
        return RequestData(
            "remote/cluster_status_plaintext",
            [
                (
                    "data_json",
                    json.dumps(
                        dict(
                            hide_inactive_resources=(
                                self._hide_inactive_resources
                            ),
                            verbose=self._verbose,
                        )
                    ),
                )
            ],
        )

    def _process_response(self, response):
        report_item = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        if report_item is not None:
            self._report(report_item)
            return self._get_next_list()

        node = response.request.target.label
        try:
            output = json.loads(response.data)
            if output["status"] == "success":
                self._was_successful = True
                self._cluster_status = output["data"]
                return []
            if output["status_msg"]:
                self._report(
                    ReportItem.error(
                        reports.messages.NodeCommunicationCommandUnsuccessful(
                            node,
                            response.request.action,
                            output["status_msg"],
                        )
                    )
                )
            # TODO Node name should be added to each received report item and
            # those modified report itemss should be reported. That, however,
            # requires reports overhaul which would add possibility to add a
            # node name to any report item. Also, infos and warnings should not
            # be ignored.
            if output["report_list"]:
                for report_data in output["report_list"]:
                    if (
                        report_data["severity"] == ReportItemSeverity.ERROR
                        and report_data["report_text"]
                    ):
                        self._report(
                            ReportItem.error(
                                reports.messages.NodeCommunicationCommandUnsuccessful(
                                    node,
                                    response.request.action,
                                    report_data["report_text"],
                                )
                            )
                        )
        except (ValueError, LookupError, TypeError):
            self._report(
                ReportItem.warning(reports.messages.InvalidResponseFormat(node))
            )

        return self._get_next_list()

    def on_complete(self) -> Tuple[bool, str]:
        # Usually, pcs.common.messages.UnableToPerformOperationOnAnyNode is
        # reported when the operation was unsuccessful and failed on at least
        # one node.  The only use case this communication command is used does
        # not need that report and on top of that the report causes confusing
        # output for the user. The report may be added in a future if needed.
        return self._was_successful, self._cluster_status
