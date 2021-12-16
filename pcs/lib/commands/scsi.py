import os.path
from typing import Iterable

from pcs import settings
from pcs.common import reports
from pcs.common.str_tools import join_multilines
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def unfence_node(
    env: LibraryEnvironment,
    node: str,
    original_devices: Iterable[str],
    updated_devices: Iterable[str],
) -> None:
    """
    Unfence scsi devices on a node by calling fence_scsi agent script. Only
    newly added devices will be unfenced (set(updated_devices) -
    set(original_devices)). Before unfencing, original devices are be checked
    if any of them are not fenced. If there is a fenced device, unfencing will
    be skipped.

    env -- provides communication with externals
    node -- node name on wich is unfencing performed
    original_devices -- list of devices defined before update
    updated_devices -- list of devices defined after update
    """
    devices_to_unfence = set(updated_devices) - set(original_devices)
    if not devices_to_unfence:
        return
    fence_scsi_bin = os.path.join(settings.fence_agent_binaries, "fence_scsi")
    fenced_devices = []
    # do not check devices being removed
    for device in sorted(set(original_devices) & set(updated_devices)):
        stdout, stderr, return_code = env.cmd_runner().run(
            [
                fence_scsi_bin,
                "--action=status",
                f"--devices={device}",
                f"--plug={node}",
            ]
        )
        if return_code == 2:
            fenced_devices.append(device)
        elif return_code != 0:
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.StonithUnfencingDeviceStatusFailed(
                        device, join_multilines([stderr, stdout])
                    )
                )
            )
    if fenced_devices:
        # At least one of existing devices is off, which means the node has
        # been fenced and new devices should not be unfenced.
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.StonithUnfencingSkippedDevicesFenced(
                    fenced_devices
                )
            )
        )
        return
    stdout, stderr, return_code = env.cmd_runner().run(
        [
            fence_scsi_bin,
            "--action=on",
            "--devices",
            ",".join(sorted(devices_to_unfence)),
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
