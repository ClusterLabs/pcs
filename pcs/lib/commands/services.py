from typing import Optional

from pcs.common.services_dto import (
    ServicesInfoResultDto,
    ServiceStatusDto,
)
from pcs.common.types import StringIterable
from pcs.lib.env import LibraryEnvironment


def start_service(
    env: LibraryEnvironment,
    service: str,
    instance: Optional[str],
) -> None:
    env.service_manager.start(service, instance)


def stop_service(
    env: LibraryEnvironment,
    service: str,
    instance: Optional[str],
) -> None:
    env.service_manager.stop(service, instance)


def enable_service(
    env: LibraryEnvironment,
    service: str,
    instance: Optional[str],
) -> None:
    env.service_manager.enable(service, instance)


def disable_service(
    env: LibraryEnvironment,
    service: str,
    instance: Optional[str],
) -> None:
    env.service_manager.disable(service, instance)


def get_services_info(
    env: LibraryEnvironment,
    services: StringIterable,
    installed: bool = False,
    enabled: bool = False,
    running: bool = False,
) -> ServicesInfoResultDto:
    """
    services -- status of these services will be returned
    installed -- check whether specified services are installed
    enabled -- check whether specified services are enabled
    running -- check whether specified services are running

    Returns status of specified services based on requested information
    (`installed`, `running`, `enabled`). If `installed` is `True`, all
    installed services will be returned, but enabled nor running is not checked
    for services not specified in `services`
    """
    service_set = set(services)
    return ServicesInfoResultDto(
        [
            ServiceStatusDto(
                service,
                (
                    env.service_manager.is_installed(service)
                    if installed
                    else None
                ),
                (
                    env.service_manager.is_enabled(service)
                    if enabled and service in service_set
                    else None
                ),
                (
                    env.service_manager.is_running(service)
                    if running and service in service_set
                    else None
                ),
            )
            for service in service_set
            | set(
                env.service_manager.get_available_services()
                if installed
                else []
            )
        ]
    )
