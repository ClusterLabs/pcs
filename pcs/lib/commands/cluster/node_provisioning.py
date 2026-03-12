from pcs.common import reports


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
