import multiprocessing as mp

from pcs.common import reports as pcs_reports
from .messaging import (
    Message,
    MessageType,
)

class WorkerReportProcessor(pcs_reports.ReportProcessor):
    def __init__(self, worker_com: mp.Queue, task_ident: str) -> None:
        super().__init__()
        self._worker_communicator: mp.Queue = worker_com
        self._task_ident: str = task_ident

    def _do_report(self, report_item: pcs_reports.item.ReportItem) -> None:
        try:
            self._worker_communicator.put(
                Message(
                    self._task_ident,
                    MessageType.REPORT,
                    report_item.to_dto()
                )
            )
        except mp.Queue.queue.Full:
            pass
            #TODO Log and exit
