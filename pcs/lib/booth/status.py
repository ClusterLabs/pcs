from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs import settings
from pcs.common.tools import join_multilines
from pcs.lib.booth import reports
from pcs.lib.errors import LibraryError


def get_daemon_status(runner, name=None):
    cmd = [settings.booth_binary, "status"]
    if name:
        cmd += ["-c", name]
    stdout, stderr, return_value = runner.run(cmd)
    # 7 means that there is no booth instance running
    if return_value not in [0, 7]:
        raise LibraryError(
            reports.booth_daemon_status_error(join_multilines([stderr, stdout]))
        )
    return stdout


def get_tickets_status(runner, name=None):
    cmd = [settings.booth_binary, "list"]
    if name:
        cmd += ["-c", name]
    stdout, stderr, return_value = runner.run(cmd)
    if return_value != 0:
        raise LibraryError(
            reports.booth_tickets_status_error(
                join_multilines([stderr, stdout])
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
            reports.booth_peers_status_error(join_multilines([stderr, stdout]))
        )
    return stdout
