from os import path

from pcs import settings
from pcs.lib import (
    external,
    reports,
)
from pcs.lib.tools import dict_to_environment_file, environment_file_to_dict
from pcs.lib.errors import LibraryError


DEVICE_INITIALIZATION_OPTIONS_MAPPING = {
    "watchdog-timeout": "-1",
    "allocate-timeout": "-2",
    "loop-timeout": "-3",
    "msgwait-timeout": "-4",
}


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
        and
        not is_device_set_local()
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


def validate_new_nodes_devices(is_sbd_enabled, nodes_devices):
    """
    Validate if SBD devices are set for new nodes when they should be

    bool is_sbd_enabled -- True if SBD is enableb in a cluster
    dict nodes_devices -- name: node name, key: list of SBD devices
    """
    if is_sbd_enabled and is_device_set_local():
        return validate_nodes_devices(nodes_devices)
    return [
        reports.sbd_with_devices_not_used_cannot_set_device(node)
        for node, devices in nodes_devices.items() if devices
    ]


def validate_nodes_devices(node_device_dict):
    """
    Validates device list for all nodes. If node is present, it checks if there
    is at least one device and at max settings.sbd_max_device_num. Also devices
    have to be specified with absolute path.
    Returns list of ReportItem

    dict node_device_dict -- name: node name, key: list of SBD devices
    """
    report_item_list = []
    for node_label, device_list in node_device_dict.items():
        if not device_list:
            report_item_list.append(
                reports.sbd_no_device_for_node(node_label)
            )
        elif len(device_list) > settings.sbd_max_device_num:
            report_item_list.append(reports.sbd_too_many_devices_for_node(
                node_label, device_list, settings.sbd_max_device_num
            ))
        for device in device_list:
            if not device or not path.isabs(device):
                report_item_list.append(
                    reports.sbd_device_path_not_absolute(device, node_label)
                )
    return report_item_list


def create_sbd_config(base_config, node_label, watchdog, device_list=None):
    # TODO: figure out which name/ring has to be in SBD_OPTS
    config = dict(base_config)
    config["SBD_OPTS"] = '"-n {node_name}"'.format(node_name=node_label)
    if watchdog:
        config["SBD_WATCHDOG_DEV"] = watchdog
    if device_list:
        config["SBD_DEVICE"] = '"{0}"'.format(";".join(device_list))
    return dict_to_environment_file(config)


def get_default_sbd_config():
    """
    Returns default SBD configuration as dictionary.
    """
    return {
        "SBD_DELAY_START": "no",
        "SBD_PACEMAKER": "yes",
        "SBD_STARTMODE": "always",
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


def initialize_block_devices(
    report_processor, cmd_runner, device_list, option_dict
):
    """
    Initialize devices with specified options in option_dict.
    Raise LibraryError on failure.

    report_processor -- report processor
    cmd_runner -- CommandRunner
    device_list -- list of strings
    option_dict -- dictionary of options and their values
    """
    report_processor.process(
        reports.sbd_device_initialization_started(device_list)
    )

    cmd = [settings.sbd_binary]
    for device in device_list:
        cmd += ["-d", device]

    for option, value in sorted(option_dict.items()):
        cmd += [DEVICE_INITIALIZATION_OPTIONS_MAPPING[option], str(value)]

    cmd.append("create")
    _, std_err, ret_val = cmd_runner.run(cmd)
    if ret_val != 0:
        raise LibraryError(
            reports.sbd_device_initialization_error(device_list, std_err)
        )
    report_processor.process(
        reports.sbd_device_initialization_success(device_list)
    )


def get_local_sbd_device_list():
    """
    Returns list of devices specified in local SBD config
    """
    if not path.exists(settings.sbd_config):
        return []

    cfg = environment_file_to_dict(get_local_sbd_config())
    if "SBD_DEVICE" not in cfg:
        return []
    devices = cfg["SBD_DEVICE"]
    if devices.startswith('"') and devices.endswith('"'):
        devices = devices[1:-1]
    return [
        device.strip()
        for device in devices.split(";") if device.strip()
    ]


def is_device_set_local():
    """
    Returns True if there is at least one device specified in local SBD config,
    False otherwise.
    """
    return len(get_local_sbd_device_list()) > 0


def get_device_messages_info(cmd_runner, device):
    """
    Returns info about messages (string) stored on specified SBD device.

    cmd_runner -- CommandRunner
    device -- string
    """
    std_out, dummy_std_err, ret_val = cmd_runner.run(
        [settings.sbd_binary, "-d", device, "list"]
    )
    if ret_val != 0:
        # sbd writes error message into std_out
        raise LibraryError(reports.sbd_device_list_error(device, std_out))
    return std_out


def get_device_sbd_header_dump(cmd_runner, device):
    """
    Returns header dump (string) of specified SBD device.

    cmd_runner -- CommandRunner
    device -- string
    """
    std_out, dummy_std_err, ret_val = cmd_runner.run(
        [settings.sbd_binary, "-d", device, "dump"]
    )
    if ret_val != 0:
        # sbd writes error message into std_out
        raise LibraryError(reports.sbd_device_dump_error(device, std_out))
    return std_out


def set_message(cmd_runner, device, node_name, message):
    """
    Set message of specified type 'message' on SBD device for node.

    cmd_runner -- CommandRunner
    device -- string, device path
    node_name -- string, nae of node for which message should be set
    message -- string, message type
    """
    dummy_std_out, std_err, ret_val = cmd_runner.run(
        [settings.sbd_binary, "-d", device, "message", node_name, message]
    )
    if ret_val != 0:
        raise LibraryError(reports.sbd_device_message_error(
            device, node_name, message, std_err
        ))
