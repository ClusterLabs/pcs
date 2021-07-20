import os.path
from typing import Iterable

from pcs import settings
from pcs.common import reports
from pcs.common.str_tools import join_multilines
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def unfence_node(env: LibraryEnvironment, node: str, devices: Iterable[str]):
    """
    Unfence scsi devices on a node by calling fence_scsi agent script.

    env -- provides communication with externals
    node -- node name on wich is unfencing performed
    devices -- scsi devices to be unfenced
    """
    stdout, stderr, return_code = env.cmd_runner().run(
        [
            os.path.join(settings.fence_agent_binaries, "fence_scsi"),
            "--action=on",
            "--devices",
            ",".join(sorted(devices)),
            f"--plug={node}",
        ],
    )
    if return_code != 0:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.StonithUnfencingFailed(
                    join_multilines([stderr, stdout])
                )
            )
        )
