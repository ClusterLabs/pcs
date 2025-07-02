from pcs.cli.reports.processor import print_report
from pcs.common import reports


class NodeRemoveRemoteReportProcessor(reports.ReportProcessor):
    """
    Catch reports in memory without printing them. When we receive the first
    report about node communication, we print all of the saved reports into
    console and then start printing all of the subsequent reports

    Used when we need to catch validation error reports from
    `remote_node.node_remove_remote` library command, but we need to provide
    output to the user after the validations passed but the command has not
    finished yet. When we receive the first report about node communication, we
    can start printing the reports to console since we know that the validations
    have passed and the command started the removal.
    """

    def __init__(self, include_debug: bool = False):
        super().__init__()
        self._include_debug = include_debug
        self._save_in_memory = True
        self._reports: reports.ReportItemList = []

    def _do_report(self, report_item: reports.ReportItem) -> None:
        if (
            report_item.severity.level == reports.ReportItemSeverity.DEBUG
            and not self._include_debug
        ):
            return

        if not self._save_in_memory:
            print_report(report_item.to_dto())
            return

        self._reports.append(report_item)
        if (
            report_item.message.code
            == reports.codes.SERVICE_COMMANDS_ON_NODES_STARTED
        ):
            for saved_report in self._reports:
                print_report(saved_report.to_dto())
            self._save_in_memory = False
            self._reports = []

    @property
    def reports(self) -> reports.ReportItemList:
        return self._reports

    @property
    def already_reported_to_console(self) -> bool:
        return not self._save_in_memory
