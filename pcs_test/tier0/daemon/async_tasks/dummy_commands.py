from pcs.common.reports import ReportItem
from pcs.common.reports.messages import CibUpgradeSuccessful
from pcs.lib.errors import LibraryError

RESULT = "I'm done."

# These functions use _ to discard environment that is hardcoded in
# task_executor because all library functions use it
def dummy_workload_no_result_with_reports(lib_env) -> None:
    lib_env.report_processor.report(ReportItem.info(CibUpgradeSuccessful()))


def dummy_workload_with_result(_) -> str:
    return RESULT


def dummy_workload_unhandled_exception(_) -> None:
    raise Exception("Whoa, something happened to this task!")


def dummy_workload_lib_exception(_) -> None:
    raise LibraryError()


def dummy_workload_lib_exception_contains_reports(_) -> None:
    raise LibraryError(ReportItem.error(CibUpgradeSuccessful()))


test_command_map = {
    "success": dummy_workload_with_result,
    "success_with_reports": dummy_workload_no_result_with_reports,
    "unhandled_exc": dummy_workload_unhandled_exception,
    "lib_exc": dummy_workload_lib_exception,
    "lib_exc_reports": dummy_workload_lib_exception_contains_reports,
}
