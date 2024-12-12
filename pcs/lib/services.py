from typing import (
    List,
    Optional,
)

from pcs import settings
from pcs.common import (
    reports,
    services,
)
from pcs.common.types import StringSequence
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner


class _CmdExecutor(services.interfaces.ExecutorInterface):
    def __init__(self, cmd_runner: CommandRunner) -> None:
        self._cmd_runner = cmd_runner

    def run(self, args: StringSequence) -> services.types.ExecutorResult:
        stdout, stderr, retval = self._cmd_runner.run(args)
        return services.types.ExecutorResult(retval, stdout, stderr)


class _NoOpDriver(services.interfaces.ServiceManagerInterface):
    def __init__(self, report_processor: reports.ReportProcessor) -> None:
        self._report_processor = report_processor

    def _warn(
        self,
        service: str,
        instance: Optional[str],
        action: reports.types.ServiceAction,
    ) -> None:
        self._report_processor.report(
            reports.ReportItem.warning(
                reports.messages.ServiceActionSkipped(
                    action,
                    service,
                    "Unknown init system",
                    instance=instance or "",
                )
            )
        )

    def start(self, service: str, instance: Optional[str] = None) -> None:
        self._warn(service, instance, reports.const.SERVICE_ACTION_START)

    def stop(self, service: str, instance: Optional[str] = None) -> None:
        self._warn(service, instance, reports.const.SERVICE_ACTION_STOP)

    def enable(self, service: str, instance: Optional[str] = None) -> None:
        self._warn(service, instance, reports.const.SERVICE_ACTION_ENABLE)

    def disable(self, service: str, instance: Optional[str] = None) -> None:
        self._warn(service, instance, reports.const.SERVICE_ACTION_DISABLE)

    def kill(self, service: str, instance: Optional[str] = None) -> None:
        self._warn(service, instance, reports.const.SERVICE_ACTION_KILL)

    def is_enabled(self, service: str, instance: Optional[str] = None) -> bool:
        del service, instance
        return False

    def is_running(self, service: str, instance: Optional[str] = None) -> bool:
        del service, instance
        return False

    def is_installed(self, service: str) -> bool:
        del service
        return True

    def get_available_services(self) -> List[str]:
        return []

    def is_current_system_supported(self) -> bool:
        return True


def get_service_manager(
    cmd_runner: CommandRunner,
    report_processor: reports.ReportProcessor,
) -> services.interfaces.ServiceManagerInterface:
    executor = _CmdExecutor(cmd_runner)
    drivers: List[services.interfaces.ServiceManagerInterface] = [
        services.drivers.SystemdDriver(
            executor, settings.systemctl_exec, settings.systemd_unit_path
        ),
        services.drivers.SysVInitRhelDriver(
            executor, settings.service_exec, settings.chkconfig_exec
        ),
    ]

    for driver in drivers:
        if driver.is_current_system_supported():
            return driver
    report_processor.report(
        reports.ReportItem.warning(
            reports.messages.ServiceUnableToDetectInitSystem()
        )
    )
    return _NoOpDriver(report_processor)


def service_exception_to_report(
    exception: services.errors.ManageServiceError,
) -> reports.ReportItem:
    action = None
    if isinstance(exception, services.errors.DisableServiceError):
        action = reports.const.SERVICE_ACTION_DISABLE
    elif isinstance(exception, services.errors.EnableServiceError):
        action = reports.const.SERVICE_ACTION_ENABLE
    elif isinstance(exception, services.errors.StartServiceError):
        action = reports.const.SERVICE_ACTION_START
    elif isinstance(exception, services.errors.StopServiceError):
        action = reports.const.SERVICE_ACTION_STOP

    if action is None:
        raise AssertionError()

    return reports.ReportItem.error(
        reports.messages.ServiceActionFailed(
            action,
            exception.service,
            exception.message,
            instance=exception.instance or "",
        )
    )


def is_systemd(
    service_manager: services.interfaces.ServiceManagerInterface,
) -> bool:
    return isinstance(service_manager, services.drivers.SystemdDriver)


def ensure_is_systemd(
    service_manager: services.interfaces.ServiceManagerInterface,
) -> None:
    """
    Raise a LibraryError if the current system is not a systemd system
    """
    if not is_systemd(service_manager):
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.UnsupportedOperationOnNonSystemdSystems()
            )
        )
