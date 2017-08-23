from __future__ import (
    absolute_import,
    division,
    print_function,
)

import os.path

from pcs import settings
from pcs.common.tools import join_multilines
from pcs.lib import reports
from pcs.lib.errors import LibraryError


def get_status_text(runner, verbose=False):
    """
    Get quorum device client runtime status in plain text
    bool verbose get more detailed output
    """
    cmd = [
        os.path.join(settings.corosync_binaries, "corosync-qdevice-tool"),
        "-s"
    ]
    if verbose:
        cmd.append("-v")
    stdout, stderr, retval = runner.run(cmd)
    if retval != 0:
        raise LibraryError(
            reports.corosync_quorum_get_status_error(
                join_multilines([stderr, stdout])
            )
        )
    return stdout

