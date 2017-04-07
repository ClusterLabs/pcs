from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import os
import json

from pcs import settings
from pcs.common import (
    tools,
    report_codes,
)
from pcs.lib import (
    sbd,
    reports,
    nodes_task,
)
from pcs.lib.tools import environment_file_to_dict
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity as Severities
)
from pcs.lib.external import (
    node_communicator_exception_to_report_item,
    NodeCommunicationException,
    NodeConnectionException,
    NodeCommandUnsuccessfulException,
)
from pcs.lib.node import (
    NodeAddressesList,
    NodeNotFound
)
from pcs.lib.validate import (
    names_in,
    run_collection_of_option_validators,
    value_nonnegative_integer,
)


def _validate_sbd_options(sbd_config, allow_unknown_opts=False):
    """
    Validate user SBD configuration. Options 'SBD_WATCHDOG_DEV' and 'SBD_OPTS'
    are restricted. Returns list of ReportItem

    sbd_config -- dictionary in format: <SBD config option>: <value>
    allow_unknown_opts -- if True, accept also unknown options.
    """

    report_item_list = []
    unsupported_sbd_option_list = [
        "SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_PACEMAKER", "SBD_DEVICE"
    ]
    allowed_sbd_options = [
        "SBD_DELAY_START", "SBD_STARTMODE", "SBD_WATCHDOG_TIMEOUT"
    ]
    for sbd_opt in sbd_config:
        if sbd_opt in unsupported_sbd_option_list:
            report_item_list.append(reports.invalid_option(
                [sbd_opt], allowed_sbd_options, None
            ))

        elif sbd_opt not in allowed_sbd_options:
            report_item_list.append(reports.invalid_option(
                [sbd_opt],
                allowed_sbd_options,
                None,
                Severities.WARNING if allow_unknown_opts else Severities.ERROR,
                None if allow_unknown_opts else report_codes.FORCE_OPTIONS
            ))
    if "SBD_WATCHDOG_TIMEOUT" in sbd_config:
        report_item = reports.invalid_option_value(
            "SBD_WATCHDOG_TIMEOUT",
            sbd_config["SBD_WATCHDOG_TIMEOUT"],
            "a non-negative integer"
        )
        try:
            if int(sbd_config["SBD_WATCHDOG_TIMEOUT"]) < 0:
                report_item_list.append(report_item)
        except (ValueError, TypeError):
            report_item_list.append(report_item)

    return report_item_list


def _validate_watchdog_dict(watchdog_dict):
    """
    Validates if all watchdogs are specified by absolute path.
    Returns list of ReportItem.

    watchdog_dict -- dictionary with NodeAddresses as keys and value as watchdog
    """
    return [
        reports.invalid_watchdog_path(watchdog)
        for watchdog in watchdog_dict.values()
        if not watchdog or not os.path.isabs(watchdog)
    ]


def _validate_device_dict(node_device_dict):
    """
    Validates device list for all nodes. If node is present, it checks if there
    is at least one device and at max settings.sbd_max_device_num. Also devices
    have to be specified with absolute path.
    Returns list of ReportItem

    node_device_dict -- dictionary with NodeAddresses as keys and list of
        devices as values
    """
    report_item_list = []
    for node, device_list in node_device_dict.items():
        if not device_list:
            report_item_list.append(
                reports.sbd_no_device_for_node(node.label)
            )
            continue
        elif len(device_list) > settings.sbd_max_device_num:
            report_item_list.append(reports.sbd_too_many_devices_for_node(
                node.label, device_list, settings.sbd_max_device_num
            ))
            continue
        for device in device_list:
            if not device or not os.path.isabs(device):
                report_item_list.append(
                    reports.sbd_device_path_not_absolute(device, node.label)
                )

    return report_item_list


def _check_node_names_in_cluster(node_list, node_name_list):
    """
    Check whenever all node names from node_name_list exists in node_list.
    Returns list of ReportItem

    node_list -- NodeAddressesList
    node_name_list -- list of stings
    """
    not_existing_node_set = set()
    for node_name in node_name_list:
        try:
            node_list.find_by_label(node_name)
        except NodeNotFound:
            not_existing_node_set.add(node_name)

    return [reports.node_not_found(node) for node in not_existing_node_set]


def _get_full_node_dict(node_list, node_value_dict, default_value):
    """
    Returns dictionary where keys NodeAdressesof all nodes in cluster and value
    is obtained from node_value_dict for node name, or default+value if node
    nade is not specified in node_value_dict.

    node_list -- NodeAddressesList
    node_value_dict -- dictionary, keys: node names, values: some velue
    default_value -- some default value
     """
    return dict([
        (node, node_value_dict.get(node.label, default_value))
        for node in node_list
    ])


def enable_sbd(
    lib_env, default_watchdog, watchdog_dict, sbd_options,
    default_device_list=None, node_device_dict=None, allow_unknown_opts=False,
    ignore_offline_nodes=False,
):
    """
    Enable SBD on all nodes in cluster.

    lib_env -- LibraryEnvironment
    default_watchdog -- watchdog for nodes which are not specified in
        watchdog_dict. Uses default value from settings if None.
    watchdog_dict -- dictionary with node names as keys and watchdog path
        as value
    sbd_options -- dictionary in format: <SBD config option>: <value>
    default_device_list -- list of devices for all nodes
    node_device_dict -- dictionary with node names as keys and list of devices
        as value
    allow_unknown_opts -- if True, accept also unknown options.
    ignore_offline_nodes -- if True, omit offline nodes
    """
    node_list = _get_cluster_nodes(lib_env)
    using_devices = not (
        default_device_list is None and node_device_dict is None
    )
    if default_device_list is None:
        default_device_list = []
    if node_device_dict is None:
        node_device_dict = {}
    if not default_watchdog:
        default_watchdog = settings.sbd_watchdog_default
    sbd_options = dict([(opt.upper(), val) for opt, val in sbd_options.items()])

    full_watchdog_dict = _get_full_node_dict(
        node_list, watchdog_dict, default_watchdog
    )
    full_device_dict = _get_full_node_dict(
        node_list, node_device_dict, default_device_list
    )

    lib_env.report_processor.process_list(
        _check_node_names_in_cluster(
            node_list, watchdog_dict.keys() + node_device_dict.keys()
        )
        +
        _validate_watchdog_dict(full_watchdog_dict)
        +
        _validate_device_dict(full_device_dict) if using_devices else []
        +
        _validate_sbd_options(sbd_options, allow_unknown_opts)
    )

    online_nodes = _get_online_nodes(lib_env, node_list, ignore_offline_nodes)

    node_data_dict = {}
    for node in online_nodes:
        node_data_dict[node] = {
            "watchdog": full_watchdog_dict[node],
            "device_list": full_device_dict[node] if using_devices else [],
        }

    # check if SBD can be enabled
    sbd.check_sbd_on_all_nodes(
        lib_env.report_processor,
        lib_env.node_communicator(),
        node_data_dict,
    )

    # enable ATB if needed
    if not lib_env.is_cman_cluster and not using_devices:
        corosync_conf = lib_env.get_corosync_conf()
        if sbd.atb_has_to_be_enabled_pre_enable_check(corosync_conf):
            lib_env.report_processor.process(reports.sbd_requires_atb())
            corosync_conf.set_quorum_options(
                lib_env.report_processor, {"auto_tie_breaker": "1"}
            )
            lib_env.push_corosync_conf(corosync_conf, ignore_offline_nodes)

    # distribute SBD configuration
    config = sbd.get_default_sbd_config()
    config.update(sbd_options)
    sbd.set_sbd_config_on_all_nodes(
        lib_env.report_processor,
        lib_env.node_communicator(),
        online_nodes,
        config,
        full_watchdog_dict,
        full_device_dict,
    )

    # remove cluster prop 'stonith_watchdog_timeout'
    sbd.remove_stonith_watchdog_timeout_on_all_nodes(
        lib_env.node_communicator(), online_nodes
    )

    # enable SBD service an all nodes
    sbd.enable_sbd_service_on_all_nodes(
        lib_env.report_processor, lib_env.node_communicator(), online_nodes
    )

    lib_env.report_processor.process(
        reports.cluster_restart_required_to_apply_changes()
    )


def disable_sbd(lib_env, ignore_offline_nodes=False):
    """
    Disable SBD on all nodes in cluster.

    lib_env -- LibraryEnvironment
    ignore_offline_nodes -- if True, omit offline nodes
    """
    node_list = _get_online_nodes(
        lib_env, _get_cluster_nodes(lib_env), ignore_offline_nodes
    )

    if lib_env.is_cman_cluster:
        nodes_task.check_corosync_offline_on_nodes(
            lib_env.node_communicator(),
            lib_env.report_processor,
            node_list,
            ignore_offline_nodes
        )

    sbd.set_stonith_watchdog_timeout_to_zero_on_all_nodes(
        lib_env.node_communicator(), node_list
    )
    sbd.disable_sbd_service_on_all_nodes(
        lib_env.report_processor,
        lib_env.node_communicator(),
        node_list
    )

    if not lib_env.is_cman_cluster:
        lib_env.report_processor.process(
            reports.cluster_restart_required_to_apply_changes()
        )


def _get_online_nodes(lib_env, node_list, ignore_offline_nodes=False):
    """
    Returns NodeAddressesList of online nodes.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    node_list -- NodeAddressesList
    ignore_offline_nodes -- if True offline nodes are just omitted from
        returned list.
    """
    to_raise = []
    online_node_list = NodeAddressesList()

    def is_node_online(node):
        try:
            nodes_task.node_check_auth(lib_env.node_communicator(), node)
            online_node_list.append(node)
        except NodeConnectionException as e:
            if ignore_offline_nodes:
                to_raise.append(reports.omitting_node(node.label))
            else:
                to_raise.append(node_communicator_exception_to_report_item(
                    e, Severities.ERROR, report_codes.SKIP_OFFLINE_NODES
                ))
        except NodeCommunicationException as e:
            to_raise.append(node_communicator_exception_to_report_item(e))

    tools.run_parallel(is_node_online, [([node], {}) for node in node_list])

    lib_env.report_processor.process_list(to_raise)
    return online_node_list


def get_cluster_sbd_status(lib_env):
    """
    Returns status of SBD service in cluster in dictionary with format:
    {
        <NodeAddress>: {
            "installed": <boolean>,
            "enabled": <boolean>,
            "running": <boolean>
        },
        ...
    }

    lib_env -- LibraryEnvironment
    """
    node_list = _get_cluster_nodes(lib_env)
    report_item_list = []
    successful_node_list = []
    status_list = []

    def get_sbd_status(node):
        try:
            status_list.append({
                "node": node.label,
                "status": json.loads(
                    # here we just need info about sbd service,
                    # therefore watchdog and device list is empty
                    sbd.check_sbd(lib_env.node_communicator(), node, "", [])
                )["sbd"]
            })
            successful_node_list.append(node)
        except NodeCommunicationException as e:
            report_item_list.append(node_communicator_exception_to_report_item(
                e,
                severity=Severities.WARNING
            ))
            report_item_list.append(reports.unable_to_get_sbd_status(
                node.label,
                "", #reason is in previous report item
                #warning is there implicit
            ))
        except (ValueError, KeyError) as e:
            report_item_list.append(reports.unable_to_get_sbd_status(
                node.label, str(e)
            ))

    tools.run_parallel(get_sbd_status, [([node], {}) for node in node_list])
    lib_env.report_processor.process_list(report_item_list)

    for node in node_list:
        if node not in successful_node_list:
            status_list.append({
                "node": node.label,
                "status": {
                    "installed": None,
                    "enabled": None,
                    "running": None
                }
            })
    return status_list


def get_cluster_sbd_config(lib_env):
    """
    Returns list of SBD config from all cluster nodes in cluster. Structure
    of data:
    [
        {
            "node": <NodeAddress>
            "config": <sbd_config_dict> or None if there was failure,
        },
        ...
    ]
    If error occurs while obtaining config from some node, it's config will be
    None. If obtaining config fail on all node returns empty dictionary.

    lib_env -- LibraryEnvironment
    """
    node_list = _get_cluster_nodes(lib_env)
    config_list = []
    successful_node_list = []
    report_item_list = []

    def get_sbd_config(node):
        try:
            config_list.append({
                "node": node.label,
                "config": environment_file_to_dict(
                    sbd.get_sbd_config(lib_env.node_communicator(), node)
                )
            })
            successful_node_list.append(node)
        except NodeCommandUnsuccessfulException as e:
            report_item_list.append(reports.unable_to_get_sbd_config(
                node.label,
                e.reason,
                Severities.WARNING
            ))
        except NodeCommunicationException as e:
            report_item_list.append(node_communicator_exception_to_report_item(
                e,
                severity=Severities.WARNING
            ))
            report_item_list.append(reports.unable_to_get_sbd_config(
                node.label,
                "", #reason is in previous report item
                Severities.WARNING
            ))

    tools.run_parallel(get_sbd_config, [([node], {}) for node in node_list])
    lib_env.report_processor.process_list(report_item_list)

    if not len(config_list):
        return []

    for node in node_list:
        if node not in successful_node_list:
            config_list.append({
                "node": node.label,
                "config": None
            })
    return config_list


def get_local_sbd_config(lib_env):
    """
    Returns local SBD config as dictionary.

    lib_env -- LibraryEnvironment
    """
    return environment_file_to_dict(sbd.get_local_sbd_config())


def _get_cluster_nodes(lib_env):
    if lib_env.is_cman_cluster:
        return lib_env.get_cluster_conf().get_nodes()
    else:
        return lib_env.get_corosync_conf().get_nodes()


def initialize_block_devices(lib_env, device_list, option_dict):
    """
    Initialize SBD devices in device_list with options_dict.

    lib_env -- LibraryEnvironment
    device_list -- list of strings
    option_dict -- dictionary
    """
    report_item_list = []
    if not device_list:
        report_item_list.append(reports.required_option_is_missing(["device"]))

    supported_options = sbd.DEVICE_INITIALIZATION_OPTIONS_MAPPING.keys()

    report_item_list += names_in(supported_options, option_dict.keys())
    validator_list = [
        value_nonnegative_integer(key)
        for key in supported_options
    ]

    report_item_list += run_collection_of_option_validators(
        option_dict, validator_list
    )

    lib_env.report_processor.process_list(report_item_list)
    sbd.initialize_block_devices(
        lib_env.report_processor, lib_env.cmd_runner(), device_list, option_dict
    )


def get_local_devices_info(lib_env, dump=False):
    """
    Returns list of local devices info in format:
    {
        "device": <device_path>,
        "list": <output of 'sbd list' command>,
        "dump": <output of 'sbd dump' command> if dump is True, None otherwise
    }
    If sbd is not enabled, empty list will be returned.

    lib_env -- LibraryEnvironment
    dump -- if True returns also output of command 'sbd dump'
    """
    if not sbd.is_sbd_enabled(lib_env.cmd_runner()):
        return []
    device_list = sbd.get_local_sbd_device_list()
    report_item_list = []
    output = []
    for device in device_list:
        obj = {
            "device": device,
            "list": None,
            "dump": None,
        }
        try:
            obj["list"] = sbd.get_device_messages_info(
                lib_env.cmd_runner(), device
            )
            if dump:
                obj["dump"] = sbd.get_device_sbd_header_dump(
                    lib_env.cmd_runner(), device
                )
        except LibraryError as e:
            report_item_list += e.args

        output.append(obj)

    for report_item in report_item_list:
        report_item.severity = Severities.WARNING
    lib_env.report_processor.process_list(report_item_list)
    return output


def set_message(lib_env, device, node_name, message):
    """
    Set message on device for node_name.

    lib_env -- LibrayEnvironment
    device -- string, absolute path to device
    node_name -- string
    message -- string, mesage type, should be one of settings.sbd_message_types
    """
    report_item_list = []
    missing_options = []
    if not device:
        missing_options.append("device")
    if not node_name:
        missing_options.append("node")
    if missing_options:
        report_item_list.append(
            reports.required_option_is_missing(missing_options)
        )
    supported_messages = settings.sbd_message_types
    if message not in supported_messages:
        report_item_list.append(
            reports.invalid_option_value("message", message, supported_messages)
        )
    lib_env.report_processor.process_list(report_item_list)
    sbd.set_message(lib_env.cmd_runner(), device, node_name, message)

