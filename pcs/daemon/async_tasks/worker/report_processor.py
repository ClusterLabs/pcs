from pcs.common import reports as pcs_reports

from .communicator import WorkerCommunicator
from .types import Message


class WorkerReportProcessor(pcs_reports.ReportProcessor):
    """
    Report processor for tasks running inside of the worker pool
    """

    def __init__(self, worker_com: WorkerCommunicator, task_ident: str) -> None:
        super().__init__()
        self._worker_communicator = worker_com
        self._task_ident: str = task_ident

    def _do_report(self, report_item: pcs_reports.item.ReportItem) -> None:
        self._worker_communicator.put(
            Message(self._task_ident, report_item.to_dto())
        )