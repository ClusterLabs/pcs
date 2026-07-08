from pcs.common import file_type_codes, reports
from pcs.common.services.errors import ManageServiceError
from pcs.common.services_dto import (
    ServicesInfoResultDto,
    ServiceStatusDto,
)
from pcs.common.types import StringIterable
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.services import service_exception_to_report


# Following command is meant to be used internally only. It is only used
# from pcsd via pcs_internal script, so that the service_manager functionality
# is not duplicated in ruby. It doesn't do any checks and thus allows anyone to
# query any service, not limited to cluster services. Therefore, it MUST NOT
# be exposed in CLI, APIv0, APIv1, neither APIv2. Once related ruby code is
# moved to python, this command won't be needed anymore and should be removed.
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
                    else False
                ),
                (
                    env.service_manager.is_enabled(service)
                    if enabled and service in service_set
                    else False
                ),
                (
                    env.service_manager.is_running(service)
                    if running and service in service_set
                    else False
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


# This module is a good place for commands managing cluster daemons. Naming
# could be based on the following schema:
#   <component>_<action>_<target>
# where
#   component is: cluster, sbd, qdevice, sbd, etc.
#   action is: start, stop, enable, disable, on, off, kill
#   target is: all (all nodes), list (list of nodes), local (local node)


def _ensure_live_env(env: LibraryEnvironment) -> None:
    not_live = []
    if not env.is_cib_live:
        not_live.append(file_type_codes.CIB)
    if not env.is_corosync_conf_live:
        not_live.append(file_type_codes.COROSYNC_CONF)
    if not_live:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.LiveEnvironmentRequired(not_live)
            )
        )
        raise LibraryError()


def pacemaker_remote_on_local(env: LibraryEnvironment) -> None:
    """
    Enable and start pacemaker_remote service on the local node
    """
    _ensure_live_env(env)
    service_name = "pacemaker_remote"
    try:
        # Enable the service first (persistence)
        env.service_manager.enable(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_ENABLE,
                    service_name,
                )
            )
        )
        # Start the service (immediate action)
        env.service_manager.start(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_START,
                    service_name,
                )
            )
        )
    except ManageServiceError as e:
        env.report_processor.report(service_exception_to_report(e))
        raise LibraryError() from e


def pacemaker_remote_off_local(env: LibraryEnvironment) -> None:
    """
    Stop and disable pacemaker_remote service on the local node
    """
    _ensure_live_env(env)
    service_name = "pacemaker_remote"
    try:
        # Stop the service first (immediate action)
        env.service_manager.stop(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_STOP,
                    service_name,
                )
            )
        )
        # Disable the service (remove persistence)
        env.service_manager.disable(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_DISABLE,
                    service_name,
                )
            )
        )
    except ManageServiceError as e:
        env.report_processor.report(service_exception_to_report(e))
        raise LibraryError() from e


def corosync_qdevice_enable_local(env: LibraryEnvironment) -> None:
    _ensure_live_env(env)
    service_name = "corosync-qdevice"
    if not env.service_manager.is_enabled("corosync"):
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSkipped(
                    reports.const.SERVICE_ACTION_ENABLE,
                    service_name,
                    "corosync is not enabled",
                )
            )
        )
        return
    try:
        env.service_manager.enable(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_ENABLE,
                    service_name,
                )
            )
        )
    except ManageServiceError as e:
        env.report_processor.report(service_exception_to_report(e))
        raise LibraryError() from e


def corosync_qdevice_disable_local(env: LibraryEnvironment) -> None:
    _ensure_live_env(env)
    service_name = "corosync-qdevice"
    try:
        env.service_manager.disable(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_DISABLE,
                    service_name,
                )
            )
        )
    except ManageServiceError as e:
        env.report_processor.report(service_exception_to_report(e))
        raise LibraryError() from e


def corosync_qdevice_start_local(env: LibraryEnvironment) -> None:
    _ensure_live_env(env)
    service_name = "corosync-qdevice"
    if not env.service_manager.is_running("corosync"):
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSkipped(
                    reports.const.SERVICE_ACTION_START,
                    service_name,
                    "corosync is not running",
                )
            )
        )
        return
    try:
        env.service_manager.start(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_START,
                    service_name,
                )
            )
        )
    except ManageServiceError as e:
        env.report_processor.report(service_exception_to_report(e))
        raise LibraryError() from e


def corosync_qdevice_stop_local(env: LibraryEnvironment) -> None:
    _ensure_live_env(env)
    service_name = "corosync-qdevice"
    try:
        env.service_manager.stop(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_STOP,
                    service_name,
                )
            )
        )
    except ManageServiceError as e:
        env.report_processor.report(service_exception_to_report(e))
        raise LibraryError() from e


def sbd_enable_local(env: LibraryEnvironment) -> None:
    _ensure_live_env(env)
    service_name = "sbd"
    try:
        env.service_manager.enable(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_ENABLE,
                    service_name,
                )
            )
        )
    except ManageServiceError as e:
        env.report_processor.report(service_exception_to_report(e))
        raise LibraryError() from e


def sbd_disable_local(env: LibraryEnvironment) -> None:
    _ensure_live_env(env)
    service_name = "sbd"
    try:
        env.service_manager.disable(service_name, instance=None)
        env.report_processor.report(
            reports.ReportItem.info(
                reports.messages.ServiceActionSucceeded(
                    reports.const.SERVICE_ACTION_DISABLE,
                    service_name,
                )
            )
        )
    except ManageServiceError as e:
        env.report_processor.report(service_exception_to_report(e))
        raise LibraryError() from e
