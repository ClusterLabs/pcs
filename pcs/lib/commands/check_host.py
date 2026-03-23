import os.path
from typing import Optional

from pcs import settings
from pcs.common.check_host_dto import CheckHostResultDto
from pcs.common.services_dto import ServiceStatusDto
from pcs.common.tools import Version, get_version_from_string
from pcs.common.version_dto import ClusterComponentVersionDto, VersionDto
from pcs.lib.corosync.live import get_corosync_version
from pcs.lib.env import LibraryEnvironment
from pcs.lib.pacemaker.live import (
    get_pacemaker_version,
    has_cib_xml,
)

_ALL_CLUSTER_SERVICES = [
    "booth",
    "corosync",
    "pacemaker",
    "pacemaker_remote",
    "pcsd",
    "corosync-qdevice",
    "sbd",
]


def _version_to_dto(version: Optional[Version]) -> VersionDto:
    return (
        VersionDto(*version.as_full_tuple) if version else VersionDto(0, 0, 0)
    )


def check_host(env: LibraryEnvironment) -> CheckHostResultDto:
    return CheckHostResultDto(
        cluster_configuration_exists=(
            os.path.exists(settings.corosync_conf_file) or has_cib_xml()
        ),
        services=[
            ServiceStatusDto(
                service=service,
                installed=env.service_manager.is_installed(service),
                enabled=env.service_manager.is_enabled(service),
                running=env.service_manager.is_running(service),
            )
            for service in _ALL_CLUSTER_SERVICES
        ],
        versions=ClusterComponentVersionDto(
            corosync=_version_to_dto(get_corosync_version(env.cmd_runner())),
            pacemaker=_version_to_dto(get_pacemaker_version(env.cmd_runner())),
            pcsd=_version_to_dto(get_version_from_string(settings.pcs_version)),
        ),
    )
