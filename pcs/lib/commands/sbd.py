from __future__ import (
    absolute_import,
    division,
    print_function,
)

import os

from pcs import settings
from pcs.common import report_codes
from pcs.lib.communication.sbd import (
    CheckSbd,
    DisableSbdService,
    EnableSbdService,
    GetSbdConfig,
    GetSbdStatus,
    RemoveStonithWatchdogTimeout,
    SetSbdConfig,
    SetStonithWatchdogTimeoutToZero,
)
from pcs.lib.communication.nodes import GetOnlineTargets
from pcs.lib.communication.corosync import CheckCorosyncOffline
from pcs.lib.communication.tools import (
    run as run_com,
    run_and_raise,
)
from pcs.lib import (
    sbd,
    reports,
)
from pcs.lib.tools import environment_file_to_dict
from pcs.lib.errors import (
    LibraryError,
    ReportItemSeverity as Severities
)
from pcs.lib.node import NodeNotFound
from pcs.lib.validate import (
    names_in,
    run_collection_of_option_validators,
    value_nonnegative_integer,
)


UNSUPPORTED_SBD_OPTION_LIST = [
    "SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_PACEMAKER", "SBD_DEVICE"
]
ALLOWED_SBD_OPTION_LIST = [
    "SBD_DELAY_START", "SBD_STARTMODE", "SBD_WATCHDOG_TIMEOUT"
]


def _validate_sbd_options(sbd_config, allow_unknown_opts=False):
    """
    Validate user SBD configuration. Options 'SBD_WATCHDOG_DEV' and 'SBD_OPTS'
    are restricted. Returns list of ReportItem

    sbd_config -- dictionary in format: <SBD config option>: <value>
    allow_unknown_opts -- if True, accept also unknown options.
    """

    report_item_list = []
    for sbd_opt in sbd_config:
        if sbd_opt in UNSUPPORTED_SBD_OPTION_LIST:
            report_item_list.append(reports.invalid_options(
                [sbd_opt], ALLOWED_SBD_OPTION_LIST, None
            ))

        elif sbd_opt not in ALLOWED_SBD_OPTION_LIST:
            report_item_list.append(reports.invalid_options(
                [sbd_opt],
                ALLOWED_SBD_OPTION_LIST,
                None,
                severity=(
                    Severities.WARNING if allow_unknown_opts
                    else Severities.ERROR
                ),
                forceable=(
                    None if allow_unknown_opts
                    else report_codes.FORCE_OPTIONS
                )
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
    for node_label, device_list in node_device_dict.items():
        if not device_list:
            report_item_list.append(
                reports.sbd_no_device_for_node(node_label)
            )
            continue
        elif len(device_list) > settings.sbd_max_device_num:
            report_item_list.append(reports.sbd_too_many_devices_for_node(
                node_label, device_list, settings.sbd_max_device_num
            ))
            continue
        for device in device_list:
            if not device or not os.path.isabs(device):
                report_item_list.append(
                    reports.sbd_device_path_not_absolute(device, node_label)
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


def _get_full_target_dict(target_list, node_value_dict, default_value):
    """
    Returns dictionary where keys are labels of all nodes in cluster and value
    is obtained from node_value_dict for node name, or default value if node
    is not specified in node_value_dict.

    list node_list -- list of cluster nodes (RequestTarget object)
    node_value_dict -- dictionary, keys: node names, values: some velue
    default_value -- some default value
     """
    return dict([
        (target.label, node_value_dict.get(target.label, default_value))
        for target in target_list
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
    target_list = lib_env.get_node_target_factory().get_target_list(node_list)
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

    full_watchdog_dict = _get_full_target_dict(
        target_list, watchdog_dict, default_watchdog
    )
    full_device_dict = _get_full_target_dict(
        target_list, node_device_dict, default_device_list
    )

    lib_env.report_processor.process_list(
        _check_node_names_in_cluster(
            node_list,
            list(watchdog_dict.keys()) + list(node_device_dict.keys())
        )
        +
        _validate_watchdog_dict(full_watchdog_dict)
        +
        (_validate_device_dict(full_device_dict) if using_devices else [])
        +
        _validate_sbd_options(sbd_options, allow_unknown_opts)
    )

    com_cmd = GetOnlineTargets(
        lib_env.report_processor, ignore_offline_targets=ignore_offline_nodes,
    )
    com_cmd.set_targets(target_list)
    online_targets = run_and_raise(lib_env.get_node_communicator(), com_cmd)

    # check if SBD can be enabled
    com_cmd = CheckSbd(lib_env.report_processor)
    for target in online_targets:
        com_cmd.add_request(
            target,
            full_watchdog_dict[target.label],
            full_device_dict[target.label] if using_devices else [],
        )
    run_and_raise(lib_env.get_node_communicator(), com_cmd)

    # enable ATB if neede
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
    com_cmd = SetSbdConfig(lib_env.report_processor)
    for target in online_targets:
        com_cmd.add_request(
            target,
            sbd.create_sbd_config(
                config,
                target.label,
                full_watchdog_dict[target.label],
                full_device_dict[target.label]
            )
        )
    run_and_raise(lib_env.get_node_communicator(), com_cmd)

    # remove cluster prop 'stonith_watchdog_timeout'
    com_cmd = RemoveStonithWatchdogTimeout(lib_env.report_processor)
    com_cmd.set_targets(online_targets)
    run_and_raise(lib_env.get_node_communicator(), com_cmd)

    # enable SBD service an all nodes
    com_cmd = EnableSbdService(lib_env.report_processor)
    com_cmd.set_targets(online_targets)
    run_and_raise(lib_env.get_node_communicator(), com_cmd)

    lib_env.report_processor.process(
        reports.cluster_restart_required_to_apply_changes()
    )


def disable_sbd(lib_env, ignore_offline_nodes=False):
    """
    Disable SBD on all nodes in cluster.

    lib_env -- LibraryEnvironment
    ignore_offline_nodes -- if True, omit offline nodes
    """
    com_cmd = GetOnlineTargets(
        lib_env.report_processor, ignore_offline_targets=ignore_offline_nodes,
    )
    com_cmd.set_targets(
        lib_env.get_node_target_factory().get_target_list(
            _get_cluster_nodes(lib_env)
        )
    )
    online_nodes = run_and_raise(lib_env.get_node_communicator(), com_cmd)

    if lib_env.is_cman_cluster:
        com_cmd = CheckCorosyncOffline(
            lib_env.report_processor, skip_offline_targets=ignore_offline_nodes,
        )
        com_cmd.set_targets(online_nodes)
        run_and_raise(lib_env.get_node_communicator(), com_cmd)

    com_cmd = SetStonithWatchdogTimeoutToZero(lib_env.report_processor)
    com_cmd.set_targets(online_nodes)
    run_and_raise(lib_env.get_node_communicator(), com_cmd)

    com_cmd = DisableSbdService(lib_env.report_processor)
    com_cmd.set_targets(online_nodes)
    run_and_raise(lib_env.get_node_communicator(), com_cmd)

    if not lib_env.is_cman_cluster:
        lib_env.report_processor.process(
            reports.cluster_restart_required_to_apply_changes()
        )


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
    com_cmd = GetSbdStatus(lib_env.report_processor)
    com_cmd.set_targets(
        lib_env.get_node_target_factory().get_target_list(
            _get_cluster_nodes(lib_env)
        )
    )
    return run_com(lib_env.get_node_communicator(), com_cmd)


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
    com_cmd = GetSbdConfig(lib_env.report_processor)
    com_cmd.set_targets(
        lib_env.get_node_target_factory().get_target_list(
            _get_cluster_nodes(lib_env)
        )
    )
    return run_com(lib_env.get_node_communicator(), com_cmd)

def get_local_sbd_config(lib_env):
    """
    Returns local SBD config as dictionary.

    lib_env -- LibraryEnvironment
    """
    return environment_file_to_dict(sbd.get_local_sbd_config())


def _get_cluster_nodes(lib_env):
    if lib_env.is_cman_cluster:
        return lib_env.get_cluster_conf().get_nodes()
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
