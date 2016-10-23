from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import json

from pcs import settings
from pcs.common import tools
from pcs.lib import (
    external,
    reports,
)
from pcs.lib.tools import dict_to_environment_file
from pcs.lib.external import (
    NodeCommunicator,
    node_communicator_exception_to_report_item,
    NodeCommunicationException,
)
from pcs.lib.errors import LibraryError


def _run_parallel_and_raise_lib_error_on_failure(func, param_list):
    """
    Run function func in parallel for all specified parameters in arg_list.
    Raise LibraryError on any failure.

    func -- function to be run
    param_list -- list of tuples: (*args, **kwargs)
    """
    report_list = []

    def _parallel(*args, **kwargs):
        try:
            func(*args, **kwargs)
        except NodeCommunicationException as e:
            report_list.append(node_communicator_exception_to_report_item(e))
        except LibraryError as e:
            report_list.extend(e.args)

    tools.run_parallel(_parallel, param_list)

    if report_list:
        raise LibraryError(*report_list)


def _even_number_of_nodes_and_no_qdevice(
    corosync_conf_facade, node_number_modifier=0
):
    """
    Returns True whenever cluster has no quorum device configured and number of
    nodes + node_number_modifier is even number, False otherwise.

    corosync_conf_facade --
    node_number_modifier -- this value will be added to current number of nodes.
        This can be useful to test whenever is ATB needed when adding/removing
        node.
    """
    return (
        not corosync_conf_facade.has_quorum_device()
        and
        (len(corosync_conf_facade.get_nodes()) + node_number_modifier) % 2 == 0
    )


def is_auto_tie_breaker_needed(
    runner, corosync_conf_facade, node_number_modifier=0
):
    """
    Returns True whenever quorum option auto tie breaker is needed to be enabled
    for proper working of SBD fencing. False if it is not needed.

    runner -- command runner
    corosync_conf_facade --
    node_number_modifier -- this value vill be added to current number of nodes.
        This can be useful to test whenever is ATB needed when adding/removeing
        node.
    """
    return (
        _even_number_of_nodes_and_no_qdevice(
            corosync_conf_facade, node_number_modifier
        )
        and
        is_sbd_installed(runner)
        and
        is_sbd_enabled(runner)
    )


def atb_has_to_be_enabled_pre_enable_check(corosync_conf_facade):
    """
    Returns True whenever quorum option auto_tie_breaker is needed to be enabled
    for proper working of SBD fencing. False if it is not needed. This function
    doesn't check if sbd is installed nor enabled.
     """
    return (
        not corosync_conf_facade.is_enabled_auto_tie_breaker()
        and
        _even_number_of_nodes_and_no_qdevice(corosync_conf_facade)
    )


def atb_has_to_be_enabled(runner, corosync_conf_facade, node_number_modifier=0):
    """
    Return True whenever quorum option auto tie breaker has to be enabled for
    proper working of SBD fencing. False if it's not needed or it is already
    enabled.

    runner -- command runner
    corosync_conf_facade --
    node_number_modifier -- this value vill be added to current number of nodes.
        This can be useful to test whenever is ATB needed when adding/removeing
        node.
    """
    return (
        not corosync_conf_facade.is_enabled_auto_tie_breaker()
        and
        is_auto_tie_breaker_needed(
            runner, corosync_conf_facade, node_number_modifier
        )
    )


def check_sbd(communicator, node, watchdog):
    """
    Check SBD on specified 'node' and existence of specified watchdog.

    communicator -- NodeCommunicator
    node -- NodeAddresses
    watchdog -- watchdog path
    """
    return communicator.call_node(
        node,
        "remote/check_sbd",
        NodeCommunicator.format_data_dict([("watchdog", watchdog)])
    )


def check_sbd_on_node(report_processor, node_communicator, node, watchdog):
    """
    Check if SBD can be enabled on specified 'node'.
    Raises LibraryError if check fails.
    Raises NodeCommunicationException if there is communication issue.

    report_processor --
    node_communicator -- NodeCommunicator
    node -- NodeAddresses
    watchdog -- watchdog path
    """
    report_list = []
    try:
        data = json.loads(check_sbd(node_communicator, node, watchdog))
        if not data["sbd"]["installed"]:
            report_list.append(reports.sbd_not_installed(node.label))
        if not data["watchdog"]["exist"]:
            report_list.append(reports.watchdog_not_found(node.label, watchdog))
    except (ValueError, KeyError):
        raise LibraryError(reports.invalid_response_format(node.label))

    if report_list:
        raise LibraryError(*report_list)
    report_processor.process(reports.sbd_check_success(node.label))


def check_sbd_on_all_nodes(report_processor, node_communicator, nodes_watchdog):
    """
    Checks SBD (if SBD is installed and watchdog exists) on all NodeAddresses
        defined as keys in data.
    Raises LibraryError with all ReportItems in case of any failure.

    report_processor --
    node_communicator -- NodeCommunicator
    nodes_watchdog -- dictionary with NodeAddresses as keys and watchdog path
        as value
    """
    report_processor.process(reports.sbd_check_started())
    _run_parallel_and_raise_lib_error_on_failure(
        check_sbd_on_node,
        [
            ([report_processor, node_communicator, node, watchdog], {})
            for node, watchdog in sorted(nodes_watchdog.items())
        ]
    )


def set_sbd_config(communicator, node, config):
    """
    Send SBD configuration to 'node'.

    communicator -- NodeCommunicator
    node -- NodeAddresses
    config -- string, SBD configuration file
    """
    communicator.call_node(
        node,
        "remote/set_sbd_config",
        NodeCommunicator.format_data_dict([("config", config)])
    )


def set_sbd_config_on_node(
    report_processor, node_communicator, node, config, watchdog
):
    """
    Send SBD configuration to 'node' with specified watchdog set. Also puts
    correct node name into SBD_OPTS option (SBD_OPTS="-n <node_name>").

    report_processor --
    node_communicator -- NodeCommunicator
    node -- NodeAddresses
    config -- dictionary in format: <SBD config option>: <value>
    watchdog -- path to watchdog device
    """
    config = dict(config)
    config["SBD_OPTS"] = '"-n {node_name}"'.format(node_name=node.label)
    if watchdog:
        config["SBD_WATCHDOG_DEV"] = watchdog
    set_sbd_config(node_communicator, node, dict_to_environment_file(config))
    report_processor.process(
        reports.sbd_config_accepted_by_node(node.label)
    )


def set_sbd_config_on_all_nodes(
    report_processor, node_communicator, node_list, config, watchdog_dict
):
    """
    Send SBD configuration 'config' to all nodes in 'node_list'. Option
        SBD_OPTS="-n <node_name>" is added automatically.
    Raises LibraryError with all ReportItems in case of any failure.

    report_processor --
    node_communicator -- NodeCommunicator
    node_list -- NodeAddressesList
    config -- dictionary in format: <SBD config option>: <value>
    watchdog_dict -- dictionary of watchdogs where key is NodeAdresses object
        and value is path to watchdog
    """
    report_processor.process(reports.sbd_config_distribution_started())
    _run_parallel_and_raise_lib_error_on_failure(
        set_sbd_config_on_node,
        [
            (
                [
                    report_processor, node_communicator, node, config,
                    watchdog_dict.get(node)
                ],
                {}
            )
            for node in node_list
        ]
    )


def enable_sbd_service(communicator, node):
    """
    Enable SBD service on 'node'.

    communicator -- NodeCommunicator
    node -- NodeAddresses
    """
    communicator.call_node(node, "remote/sbd_enable", None)


def enable_sbd_service_on_node(report_processor, node_communicator, node):
    """
    Enable SBD service on 'node'.
    Returns list of ReportItem if there was any failure. Empty list otherwise.

    report_processor --
    node_communicator -- NodeCommunicator
    node -- NodeAddresses
    """
    enable_sbd_service(node_communicator, node)
    report_processor.process(reports.service_enable_success("sbd", node.label))


def enable_sbd_service_on_all_nodes(
        report_processor, node_communicator, node_list
):
    """
    Enable SBD service on all nodes in 'node_list'.
    Raises LibraryError with all ReportItems in case of any failure.

    report_processor --
    node_communicator -- NodeCommunicator
    node_list -- NodeAddressesList
    """
    report_processor.process(reports.sbd_enabling_started())
    _run_parallel_and_raise_lib_error_on_failure(
        enable_sbd_service_on_node,
        [
            ([report_processor, node_communicator, node], {})
            for node in node_list
        ]
    )


def disable_sbd_service(communicator, node):
    """
    Disable SBD service on 'node'.

    communicator -- NodeCommunicator
    node -- NodeAddresses
    """
    communicator.call_node(node, "remote/sbd_disable", None)


def disable_sbd_service_on_node(report_processor, node_communicator, node):
    """
    Disable SBD service on 'node'.

    report_processor --
    node_communicator -- NodeCommunicator
    node -- NodeAddresses
    """
    disable_sbd_service(node_communicator, node)
    report_processor.process(reports.service_disable_success("sbd", node.label))


def disable_sbd_service_on_all_nodes(
    report_processor, node_communicator, node_list
):
    """
    Disable SBD service on all nodes in 'node_list'.
    Raises LibraryError with all ReportItems in case of any failure.

    report_processor --
    node_communicator -- NodeCommunicator
    node_list -- NodeAddressesList
    """
    report_processor.process(reports.sbd_disabling_started())
    _run_parallel_and_raise_lib_error_on_failure(
        disable_sbd_service_on_node,
        [
            ([report_processor, node_communicator, node], {})
            for node in node_list
        ]
    )


def set_stonith_watchdog_timeout_to_zero(communicator, node):
    """
    Set cluster property 'stonith-watchdog-timeout' to value '0' on 'node'.

    communicator -- NodeCommunicator
    node -- NodeAddresses
    """
    communicator.call_node(
        node, "remote/set_stonith_watchdog_timeout_to_zero", None
    )


def set_stonith_watchdog_timeout_to_zero_on_all_nodes(
    node_communicator, node_list
):
    """
    Sets cluster property 'stonith-watchdog-timeout' to value '0' an all nodes
        in 'node_list', even if cluster is not currently running on them (direct
        editing CIB file).
    Raises LibraryError with all ReportItems in case of any failure.

    node_communicator -- NodeCommunicator
    node_list -- NodeAddressesList
    """
    report_list = []
    for node in node_list:
        try:
            set_stonith_watchdog_timeout_to_zero(node_communicator, node)
        except NodeCommunicationException as e:
            report_list.append(node_communicator_exception_to_report_item(e))
    if report_list:
        raise LibraryError(*report_list)


def remove_stonith_watchdog_timeout(communicator, node):
    """
    Remove cluster property 'stonith-watchdog-timeout' on 'node'.

    communicator -- NodeCommunicator
    node -- NodeAddresses
    """
    communicator.call_node(node, "remote/remove_stonith_watchdog_timeout", None)


def remove_stonith_watchdog_timeout_on_all_nodes(node_communicator, node_list):
    """
    Removes cluster property 'stonith-watchdog-timeout' from all nodes
        in 'node_list', even if cluster is not currently running on them (direct
        editing CIB file).
    Raises LibraryError with all ReportItems in case of any failure.

    node_communicator -- NodeCommunicator
    node_list -- NodeAddressesList
    """
    report_list = []
    for node in node_list:
        try:
            remove_stonith_watchdog_timeout(node_communicator, node)
        except NodeCommunicationException as e:
            report_list.append(node_communicator_exception_to_report_item(e))
    if report_list:
        raise LibraryError(*report_list)


def get_default_sbd_config():
    """
    Returns default SBD configuration as dictionary.
    """
    return {
        "SBD_DELAY_START": "no",
        "SBD_PACEMAKER": "yes",
        "SBD_STARTMODE": "clean",
        "SBD_WATCHDOG_DEV": settings.sbd_watchdog_default,
        "SBD_WATCHDOG_TIMEOUT": "5"
    }


def get_local_sbd_config():
    """
    Get local SBD configuration.
    Returns SBD configuration file as string.
    Raises LibraryError on any failure.
    """
    try:
        with open(settings.sbd_config, "r") as sbd_cfg:
            return sbd_cfg.read()
    except EnvironmentError as e:
        raise LibraryError(reports.unable_to_get_sbd_config(
            "local node", str(e)
        ))


def get_sbd_config(communicator, node):
    """
    Get SBD configuration from 'node'.
    Returns SBD configuration string.

    communicator -- NodeCommunicator
    node -- NodeAddresses
    """
    return communicator.call_node(node, "remote/get_sbd_config", None)


def get_sbd_service_name():
    return "sbd" if external.is_systemctl() else "sbd_helper"


def is_sbd_enabled(runner):
    """
    Check if SBD service is enabled in local system.
    Return True if SBD service is enabled, False otherwise.

    runner -- CommandRunner
    """
    return external.is_service_enabled(runner, get_sbd_service_name())



def is_sbd_installed(runner):
    """
    Check if SBD service is installed in local system.
    Reurns True id SBD service is installed. False otherwise.

    runner -- CommandRunner
    """
    return external.is_service_installed(runner, get_sbd_service_name())

