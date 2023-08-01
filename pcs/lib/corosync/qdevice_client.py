from pcs import settings
from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.common.str_tools import join_multilines
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner


def get_status_text(runner: CommandRunner, verbose: bool = False) -> str:
    """
    Get quorum device client runtime status in plain text

    verbose -- get more detailed output
    """
    cmd = [settings.corosync_qdevice_tool_exec, "-s"]
    if verbose:
        cmd.append("-v")
    stdout, stderr, retval = runner.run(cmd)
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.CorosyncQuorumGetStatusError(
                    join_multilines([stderr, stdout])
                )
            )
        )
    return stdout
