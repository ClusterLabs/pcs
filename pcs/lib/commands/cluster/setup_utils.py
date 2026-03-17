import math
import os.path
import time

from pcs import settings
from pcs.common import file_type_codes, reports
from pcs.common.file import RawFileError
from pcs.common.tools import format_os_error
from pcs.lib.communication.nodes import CheckPacemakerStarted, StartCluster
from pcs.lib.communication.tools import run as run_com
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import get_valid_timeout_seconds
from pcs.lib.tools import environment_file_to_dict


def start_cluster(
    communicator_factory,
    report_processor: reports.ReportProcessor,
    target_list,
    wait_timeout=False,
) -> None:
    # Large clusters take longer time to start up. So we make the timeout
    # longer for each 8 nodes:
    #  1 -  8 nodes: 1 * timeout
    #  9 - 16 nodes: 2 * timeout
    # 17 - 24 nodes: 3 * timeout
    # and so on ...
    # Users can override this and set their own timeout by specifying
    # the --request-timeout option.
    timeout = int(
        settings.default_request_timeout * math.ceil(len(target_list) / 8.0)
    )
    com_cmd = StartCluster(report_processor)
    com_cmd.set_targets(target_list)
    run_and_raise(
        communicator_factory.get_communicator(request_timeout=timeout), com_cmd
    )
    if wait_timeout is not False:
        report_processor.report_list(
            _wait_for_pacemaker_to_start(
                communicator_factory.get_communicator(),
                report_processor,
                target_list,
                # wait_timeout is either None or a timeout
                timeout=wait_timeout,
            )
        )
        if report_processor.has_errors:
            raise LibraryError()


def _wait_for_pacemaker_to_start(
    node_communicator,
    report_processor: reports.ReportProcessor,
    target_list,
    timeout=None,
):
    timeout = 60 * 15 if timeout is None else timeout
    interval = 2
    stop_at = time.time() + timeout
    report_processor.report(
        reports.ReportItem.info(
            reports.messages.WaitForNodeStartupStarted(
                sorted([target.label for target in target_list])
            )
        )
    )
    error_report_list = []
    has_errors = False
    while target_list:
        if time.time() > stop_at:
            error_report_list.append(
                reports.ReportItem.error(
                    reports.messages.WaitForNodeStartupTimedOut()
                )
            )
            break
        time.sleep(interval)
        com_cmd = CheckPacemakerStarted(report_processor)
        com_cmd.set_targets(target_list)
        target_list = run_com(node_communicator, com_cmd)
        has_errors = has_errors or com_cmd.has_errors

    if error_report_list or has_errors:
        error_report_list.append(
            reports.ReportItem.error(reports.messages.WaitForNodeStartupError())
        )
    return error_report_list


def host_check_cluster_setup(
    host_info_dict, force, check_services_versions=True
):
    # pylint: disable=too-many-locals
    report_list = []
    # We only care about services which matter for creating a cluster. It does
    # not make sense to check e.g. booth when a) it will never be used b) it
    # will be used in a year - which means we should do the check in a year.
    service_version_dict = {
        "pacemaker": {},
        "corosync": {},
        "pcsd": {},
    }
    required_service_list = ["pacemaker", "corosync"]
    required_as_stopped_service_list = required_service_list + [
        "pacemaker_remote"
    ]
    severity = reports.item.get_severity(reports.codes.FORCE, force)
    cluster_exists_on_nodes = False
    for host_name, host_info in host_info_dict.items():
        try:
            services = host_info["services"]
            if check_services_versions:
                for service, version_dict in service_version_dict.items():
                    version_dict[host_name] = services[service]["version"]
            missing_service_list = [
                service
                for service in required_service_list
                if not services[service]["installed"]
            ]
            if missing_service_list:
                report_list.append(
                    reports.ReportItem.error(
                        reports.messages.ServiceNotInstalled(
                            host_name, sorted(missing_service_list)
                        )
                    )
                )
            cannot_be_running_service_list = [
                service
                for service in required_as_stopped_service_list
                if service in services and services[service]["running"]
            ]
            if cannot_be_running_service_list:
                cluster_exists_on_nodes = True
                report_list.append(
                    reports.ReportItem(
                        severity=severity,
                        message=reports.messages.HostAlreadyInClusterServices(
                            host_name,
                            sorted(cannot_be_running_service_list),
                        ),
                    )
                )
            if host_info["cluster_configuration_exists"]:
                cluster_exists_on_nodes = True
                report_list.append(
                    reports.ReportItem(
                        severity=severity,
                        message=reports.messages.HostAlreadyInClusterConfig(
                            host_name,
                        ),
                    )
                )
        except KeyError:
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.InvalidResponseFormat(host_name)
                )
            )

    if check_services_versions:
        for service, version_dict in service_version_dict.items():
            report_list.extend(
                _check_for_not_matching_service_versions(service, version_dict)
            )

    if cluster_exists_on_nodes and not force:
        # This is always a forceable error
        report_list.append(
            reports.ReportItem(
                severity=reports.item.ReportItemSeverity.error(
                    reports.codes.FORCE
                ),
                message=reports.messages.ClusterWillBeDestroyed(),
            )
        )
    return report_list


def _check_for_not_matching_service_versions(service, service_version_dict):
    if len(set(service_version_dict.values())) <= 1:
        return []
    return [
        reports.ReportItem.error(
            reports.messages.ServiceVersionMismatch(
                service, service_version_dict
            )
        )
    ]


def normalize_dict(input_dict, required_keys):
    normalized = dict(input_dict)
    for key in required_keys:
        if key not in normalized:
            normalized[key] = None
    return normalized


def set_defaults_in_dict(input_dict, defaults):
    completed = dict(input_dict)
    for key, factory in defaults.items():
        if completed[key] is None:
            completed[key] = factory(input_dict)
    return completed


def get_addrs_defaulter(
    report_processor: reports.ReportProcessor,
    targets_dict,
    default_to_name_if_no_target: bool = False,
):
    def defaulter(node):
        if "name" not in node:
            return []
        address_for_use = None
        address_source = None
        target = targets_dict.get(node["name"])
        if target:
            address_for_use = target.first_addr
            address_source = reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
        elif default_to_name_if_no_target:
            address_for_use = node["name"]
            address_source = reports.const.DEFAULT_ADDRESS_SOURCE_HOST_NAME
        if address_for_use:
            report_processor.report(
                reports.ReportItem.info(
                    reports.messages.UsingDefaultAddressForHost(
                        node["name"], address_for_use, address_source
                    )
                )
            )
            return [address_for_use]
        return []

    return defaulter


def get_validated_wait_timeout(report_processor, wait, start):
    try:
        if wait is False:
            return False
        if not start:
            report_processor.report(
                reports.ReportItem.error(
                    reports.messages.WaitForNodeStartupWithoutStart()
                )
            )
        return get_valid_timeout_seconds(wait)
    except LibraryError as e:
        report_processor.report_list(e.args)
    return None


def is_ssl_cert_sync_enabled(report_processor: reports.ReportProcessor) -> bool:
    try:
        if os.path.isfile(settings.pcsd_config):
            with open(settings.pcsd_config, "r") as cfg_file:
                cfg = environment_file_to_dict(cfg_file.read())
                return (
                    cfg.get("PCSD_SSL_CERT_SYNC_ENABLED", "false").lower()
                    == "true"
                )
    except OSError as e:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.FileIoError(
                    file_type_codes.PCSD_ENVIRONMENT_CONFIG,
                    RawFileError.ACTION_READ,
                    format_os_error(e),
                    file_path=settings.pcsd_config,
                )
            )
        )
    return False
