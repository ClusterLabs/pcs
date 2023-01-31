import os.path

from pcs import settings
from pcs.common import reports
from pcs.common.str_tools import join_multilines
from pcs.common.types import StringCollection
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def _unfence_node_devices(
    env: LibraryEnvironment,
    plug: str,
    original_devices: StringCollection,
    updated_devices: StringCollection,
    fence_agent: str,
):
    """
    Unfence shared devices by calling fence agent script. Only newly added
    devices will be unfenced (set(updated_devices) - set(original_devices)).
    Before unfencing, original devices are checked if any of them are not
    fenced. If there is a fenced device, unfencing will be skipped.

    env -- provides communication with externals
    plug -- an information used for unfencing (a node name for fence_scsi,
        registration key for fence_mpath)
    original_devices -- list of devices defined before update
    updated_devices -- list of devices defined after update
    fence_agent -- fance agent name
    """
    devices_to_unfence = set(updated_devices) - set(original_devices)
    if not devices_to_unfence:
        return
    fence_agent_bin = os.path.join(settings.fence_agent_binaries, fence_agent)
    fenced_devices = []
    # do not check devices being removed
    for device in sorted(set(original_devices) & set(updated_devices)):
        stdout, stderr, return_code = env.cmd_runner().run(
            [
                fence_agent_bin,
                "--action=status",
                f"--devices={device}",
                f"--plug={plug}",
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
            fence_agent_bin,
            "--action=on",
            "--devices",
            ",".join(sorted(devices_to_unfence)),
            f"--plug={plug}",
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


def unfence_node(
    env: LibraryEnvironment,
    node: str,
    original_devices: StringCollection,
    updated_devices: StringCollection,
) -> None:
    """
    Unfence scsi devices on a node by calling fence_scsi agent script. Only
    newly added devices will be unfenced (set(updated_devices) -
    set(original_devices)). Before unfencing, original devices are checked
    if any of them are not fenced. If there is a fenced device, unfencing will
    be skipped.

    env -- provides communication with externals
    node -- node name on which unfencing is performed
    original_devices -- list of devices defined before update
    updated_devices -- list of devices defined after update
    """
    _unfence_node_devices(
        env, node, original_devices, updated_devices, "fence_scsi"
    )


def unfence_node_mpath(
    env: LibraryEnvironment,
    key: str,
    original_devices: StringCollection,
    updated_devices: StringCollection,
) -> None:
    """
    Unfence mpath devices on a node by calling fence_mpath agent script. Only
    newly added devices will be unfenced (set(updated_devices) -
    set(original_devices)). Before unfencing, original devices are checked
    if any of them are not fenced. If there is a fenced device, unfencing will
    be skipped.

    env -- provides communication with externals
    key -- registration key of the node for unfencing
    original_devices -- list of devices defined before update
    updated_devices -- list of devices defined after update
    """
    _unfence_node_devices(
        env, key, original_devices, updated_devices, "fence_mpath"
    )
