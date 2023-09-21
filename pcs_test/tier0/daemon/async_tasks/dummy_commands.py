from pcs.common.reports import ReportItem
from pcs.common.reports.messages import CibUpgradeSuccessful
from pcs.daemon.async_tasks.worker.command_mapping import _Cmd
from pcs.lib.errors import LibraryError
from pcs.lib.permissions.config.types import PermissionAccessType as p

RESULT = "I'm done."


# These functions use _ to discard environment that is hardcoded in
# task_executor because all library functions use it
def dummy_workload_no_result_with_reports(lib_env) -> None:
    lib_env.report_processor.report(ReportItem.info(CibUpgradeSuccessful()))


def dummy_workload_with_result(_) -> str:
    return RESULT


def dummy_workload_unhandled_exception(_) -> None:
    # pylint: disable=broad-exception-raised
    raise Exception("Whoa, something happened to this task!")


def dummy_workload_lib_exception(_) -> None:
    raise LibraryError()


def dummy_workload_lib_exception_contains_reports(_) -> None:
    raise LibraryError(ReportItem.error(CibUpgradeSuccessful()))


def _get_cmd(callback):
    return _Cmd(cmd=callback, required_permission=p.READ)


test_command_map = {
    "success": _get_cmd(dummy_workload_with_result),
    "success_with_reports": _get_cmd(dummy_workload_no_result_with_reports),
    "unhandled_exc": _get_cmd(dummy_workload_unhandled_exception),
    "lib_exc": _get_cmd(dummy_workload_lib_exception),
    "lib_exc_reports": _get_cmd(dummy_workload_lib_exception_contains_reports),
    "success_api_v1": _get_cmd(dummy_workload_with_result),
}

test_legacy_api_commands = ("success_api_v1",)
