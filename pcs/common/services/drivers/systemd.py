import os.path
import re
from typing import (
    List,
    Optional,
)

from pcs.common.types import StringIterable

from .. import errors
from ..interfaces import (
    ExecutorInterface,
    ServiceManagerInterface,
)


class SystemdDriver(ServiceManagerInterface):
    def __init__(
        self,
        executor: ExecutorInterface,
        systemctl_bin: str,
        systemd_unit_paths: StringIterable,
    ) -> None:
        """
        executor -- external commands used by this class are executed using
            this object
        systemctl_bin -- path to systemctl executable, it is used for managing
            services
        systemd_unit_paths -- paths to directories where unit files should be
            located. If at least one location is present on the system, systemd
            is considered as a current init system.
        """
        self._executor = executor
        self._systemctl_bin = systemctl_bin
        self._systemd_unit_paths = systemd_unit_paths
        self._available_services: List[str] = []

    def start(self, service: str, instance: Optional[str] = None) -> None:
        result = self._executor.run(
            [
                self._systemctl_bin,
                "start",
                _format_service_name(service, instance),
            ]
        )
        if result.retval != 0:
            raise errors.StartServiceError(
                service, result.joined_output, instance
            )

    def stop(self, service: str, instance: Optional[str] = None) -> None:
        result = self._executor.run(
            [
                self._systemctl_bin,
                "stop",
                _format_service_name(service, instance),
            ]
        )
        if result.retval != 0:
            raise errors.StopServiceError(
                service, result.joined_output, instance
            )

    def enable(self, service: str, instance: Optional[str] = None) -> None:
        result = self._executor.run(
            [
                self._systemctl_bin,
                "enable",
                _format_service_name(service, instance),
            ]
        )
        if result.retval != 0:
            raise errors.EnableServiceError(
                service, result.joined_output, instance
            )

    def disable(self, service: str, instance: Optional[str] = None) -> None:
        if not self.is_installed(service):
            return
        result = self._executor.run(
            [
                self._systemctl_bin,
                "disable",
                _format_service_name(service, instance),
            ]
        )
        if result.retval != 0:
            raise errors.DisableServiceError(
                service, result.joined_output, instance
            )

    def is_enabled(self, service: str, instance: Optional[str] = None) -> bool:
        result = self._executor.run(
            [
                self._systemctl_bin,
                "is-enabled",
                _format_service_name(service, instance),
            ]
        )
        return result.retval == 0

    def is_running(self, service: str, instance: Optional[str] = None) -> bool:
        result = self._executor.run(
            [
                self._systemctl_bin,
                "is-active",
                _format_service_name(service, instance),
            ]
        )
        return result.retval == 0

    def is_installed(self, service: str) -> bool:
        return service in self.get_available_services()

    def get_available_services(self) -> List[str]:
        if not self._available_services:
            self._available_services = self._get_available_services()
        return self._available_services

    def _get_available_services(self) -> List[str]:
        result = self._executor.run(
            [self._systemctl_bin, "list-unit-files", "--full"]
        )
        if result.retval != 0:
            return []

        service_list = []
        for service in result.stdout.splitlines():
            match = re.search(r"^([\S]*)\.service", service)
            if match:
                service_list.append(match.group(1))
        return service_list

    def is_current_system_supported(self) -> bool:
        return any(
            os.path.isdir(path) for path in self._systemd_unit_paths
        ) and os.path.isfile(self._systemctl_bin)


def _format_service_name(service: str, instance: Optional[str]) -> str:
    instance_str = f"@{instance}" if instance else ""
    return f"{service}{instance_str}.service"
