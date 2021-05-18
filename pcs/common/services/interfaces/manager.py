from typing import (
    List,
    Optional,
)


class ServiceManagerInterface:
    def start(self, service: str, instance: Optional[str] = None) -> None:
        """
        service -- name of service to be started
        instance -- service instance identifier. Available only for system which
            supports multiple service instances (e.g. systemd)

        Start defined service. Raises StartServiceError on failure.
        """
        raise NotImplementedError()

    def stop(self, service: str, instance: Optional[str] = None) -> None:
        """
        service -- name of service to be stopped
        instance -- service instance identifier. Available only for system which
            supports multiple service instances (e.g. systemd)

        Stop defined service. Raises StopServiceError on failure.
        """
        raise NotImplementedError()

    def enable(self, service: str, instance: Optional[str] = None) -> None:
        """
        service -- name of service to be enabled
        instance -- service instance identifier. Available only for system which
            supports multiple service instances (e.g. systemd)

        Enable defined service. Raises EnableServiceError on failure.
        """
        raise NotImplementedError()

    def disable(self, service: str, instance: Optional[str] = None) -> None:
        """
        service -- name of service to be disabled
        instance -- service instance identifier. Available only for system which
            supports multiple service instances (e.g. systemd)

        Disable defined service. Raises DisableServiceError on failure.
        """
        raise NotImplementedError()

    def is_enabled(self, service: str, instance: Optional[str] = None) -> bool:
        """
        service -- name of service to be checked
        instance -- service instance identifier. Available only for system which
            supports multiple service instances (e.g. systemd)

        Returns True if specified service is enabled, False otherwise.
        """
        raise NotImplementedError()

    def is_running(self, service: str, instance: Optional[str] = None) -> bool:
        """
        service -- name of service to be checked
        instance -- service instance identifier. Available only for system which
            supports multiple service instances (e.g. systemd)

        Returns True if specified service is running (active), False otherwise.
        """
        raise NotImplementedError()

    def is_installed(self, service: str) -> bool:
        """
        service -- name of service to be checked

        Returns True if specified service is installed (managable by init
        system), False otherwise.
        """
        raise NotImplementedError()

    def get_available_services(self) -> List[str]:
        """
        Returns list of service names recognized by init system.
        """
        raise NotImplementedError()

    def is_current_system_supported(self) -> bool:
        """
        Returns True if the instance of this class is able to manage current
        init system.
        """
        raise NotImplementedError()
