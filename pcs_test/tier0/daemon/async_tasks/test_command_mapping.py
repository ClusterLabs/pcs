from pcs.common.reports.item import ReportItem

from pcs.lib.errors import LibraryError
from .helpers import StubReportItem


# These functions use _ to discard environment that is hardcoded in
# task_executor because all library functions use it
def dummy_workload(_) -> str:
    return "I'm done."


def dummy_workload_unhandled_exception(_) -> None:
    raise Exception("Whoa, something happened to this task!")


def dummy_workload_lib_exception(_) -> None:
    raise LibraryError()


def dummy_workload_lib_exception_reports(_) -> None:
    raise LibraryError(ReportItem.error(StubReportItem()))


test_command_map = {
    "success": dummy_workload,
    "unhandled_exc": dummy_workload_unhandled_exception,
    "lib_exc": dummy_workload_lib_exception,
    "lib_exc_reports": dummy_workload_lib_exception_reports,
}
