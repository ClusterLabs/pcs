from pcs import settings
from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.common.str_tools import join_multilines
from pcs.lib.errors import LibraryError


def get_daemon_status(runner, name=None):
    cmd = [settings.booth_binary, "status"]
    if name:
        cmd += ["-c", name]
    stdout, stderr, return_value = runner.run(cmd)
    # 7 means that there is no booth instance running
    if return_value not in [0, 7]:
        raise LibraryError(
            ReportItem.error(
                reports.messages.BoothDaemonStatusError(
                    join_multilines([stderr, stdout])
                )
            )
        )
    return stdout


def get_tickets_status(runner, name=None):
    cmd = [settings.booth_binary, "list"]
    if name:
        cmd += ["-c", name]
    stdout, stderr, return_value = runner.run(cmd)
    if return_value != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.BoothTicketStatusError(
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return stdout


def get_peers_status(runner, name=None):
    cmd = [settings.booth_binary, "peers"]
    if name:
        cmd += ["-c", name]
    stdout, stderr, return_value = runner.run(cmd)
    if return_value != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.BoothPeersStatusError(
                    join_multilines([stderr, stdout]),
                )
            )
        )
    return stdout
