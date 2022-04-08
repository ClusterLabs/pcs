import os.path
from typing import (
    List,
    Optional,
)

from .. import errors
from ..interfaces import (
    ExecutorInterface,
    ServiceManagerInterface,
)


class OpenRcDriver(ServiceManagerInterface):
    def __init__(
        self,
        executor: ExecutorInterface,
        rc_service_bin: str,
        rc_config_bin: str,
    ):
        """
        executor -- external commands used by this class are executed using
            this object
        rc_service_bin -- path to an executable used for starting and stopping
            services and to check if a service is running
        rc_config_bin -- path to an executable used for enabling, disabling and
            listing available service and to check if service is enabled
        """
        self._executor = executor
        self._rc_service_bin = rc_service_bin
        self._rc_config_bin = rc_config_bin
        self._available_services: List[str] = []

    def start(self, service: str, instance: Optional[str] = None) -> None:
        result = self._executor.run([self._rc_service_bin, service, "start"])
        if result.retval != 0:
            raise errors.StartServiceError(service, result.joined_output)

    def stop(self, service: str, instance: Optional[str] = None) -> None:
        result = self._executor.run([self._rc_service_bin, service, "stop"])
        if result.retval != 0:
            raise errors.StopServiceError(service, result.joined_output)

    def enable(self, service: str, instance: Optional[str] = None) -> None:
        result = self._executor.run(
            [self._rc_config_bin, "add", service, "default"]
        )
        if result.retval != 0:
            raise errors.EnableServiceError(service, result.joined_output)

    def disable(self, service: str, instance: Optional[str] = None) -> None:
        if not self.is_installed(service):
            return
        result = self._executor.run(
            [self._rc_config_bin, "delete", service, "default"]
        )
        if result.retval != 0:
            raise errors.DisableServiceError(service, result.joined_output)

    def is_enabled(self, service: str, instance: Optional[str] = None) -> bool:
        result = self._executor.run([self._rc_config_bin, "list", "default"])
        for line in result.stdout.splitlines()[1:]:
            if service == line.strip():
                return True
        return False

    def is_running(self, service: str, instance: Optional[str] = None) -> bool:
        return (
            self._executor.run([self._rc_service_bin, service, "status"]).retval
            == 0
        )

    def is_installed(self, service: str) -> bool:
        return service in self.get_available_services()

    def get_available_services(self) -> List[str]:
        if not self._available_services:
            self._available_services = self._get_available_services()
        return self._available_services

    def _get_available_services(self) -> List[str]:
        result = self._executor.run([self._rc_config_bin, "list"])
        if result.retval != 0:
            return []

        service_list = []
        for service in result.stdout.splitlines()[1:]:
            service = service.strip().split(" ")[0]
            if service:
                service_list.append(service)
        return service_list

    def is_current_system_supported(self) -> bool:
        return all(
            os.path.isfile(binary)
            for binary in (self._rc_service_bin, self._rc_config_bin)
        )
