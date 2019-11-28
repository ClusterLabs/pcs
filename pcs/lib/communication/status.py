import json
from typing import Tuple

from pcs.common.node_communicator import RequestData
from pcs.lib import reports
from pcs.lib.communication.tools import (
    AllSameDataMixin,
    OneByOneStrategyMixin,
    RunRemotelyBase,
)
from pcs.lib.errors import ReportItemSeverity
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
                    json.dumps(dict(
                        hide_inactive_resources=self._hide_inactive_resources,
                        verbose=self._verbose,
                    ))
                )
            ],
        )

    def _process_response(self, response):
        report = response_to_report_item(
            response, severity=ReportItemSeverity.WARNING
        )
        if report is not None:
            self._report(report)
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
                    reports.node_communication_command_unsuccessful(
                        node,
                        response.request.action,
                        output["status_msg"]
                    )
                )
            # TODO Node name should be added to each received report item and
            # those modified report itemss should be reported. That, however,
            # requires reports overhaul which would add posibility to add a
            # node name to any report item. Also, infos and warnings should not
            # be ignored.
            if output["report_list"]:
                for report_data in output["report_list"]:
                    if (
                        report_data["severity"] == ReportItemSeverity.ERROR
                        and
                        report_data["report_text"]
                    ):
                        self._report(
                            reports.node_communication_command_unsuccessful(
                                node,
                                response.request.action,
                                report_data["report_text"]
                            )
                        )
        except (ValueError, LookupError, TypeError):
            self._report(reports.invalid_response_format(
                node,
                severity=ReportItemSeverity.WARNING,
            ))

        return self._get_next_list()

    def on_complete(self) -> Tuple[bool, str]:
        # Usually, reports.unable_to_perform_operation_on_any_node is reported
        # when the operation was unsuccessful and failed on at least one node.
        # The only use case this communication command is used does not need
        # that report and on top of that the report causes confusing ouptut for
        # the user. The report may be added in a future if needed.
        return self._was_successful, self._cluster_status
