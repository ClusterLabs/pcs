from typing import Any, Iterable, Mapping, Optional

from pcs import settings
from pcs.common import reports
from pcs.common.node_communicator import RequestTarget
from pcs.common.types import StringSequence
from pcs.common.validate import is_integer
from pcs.lib import (
    sbd,
    validate,
)
from pcs.lib.communication.nodes import GetOnlineTargets
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
from pcs.lib.communication.tools import run as run_com
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.tools import environment_file_to_dict

_UNSUPPORTED_SBD_OPTION_LIST = [
    "SBD_WATCHDOG_DEV",
    "SBD_OPTS",
    "SBD_PACEMAKER",
    "SBD_DEVICE",
]
_ALLOWED_SBD_OPTION_LIST = [
    "SBD_DELAY_START",
    "SBD_STARTMODE",
    "SBD_WATCHDOG_TIMEOUT",
    "SBD_TIMEOUT_ACTION",
]
_TIMEOUT_ACTION_ALLOWED_VALUES = (
    {"flush", "noflush"},
    {"reboot", "off", "crashdump"},
)
_STARTMODE_ALLOWED_VALUES = ["always", "clean"]


def __tuple(set1: set[str], set2: set[str]) -> set[str]:
    return {f"{v1},{v2}" for v1 in set1 for v2 in set2}


_TIMEOUT_ACTION_ALLOWED_VALUE_LIST = sorted(
    _TIMEOUT_ACTION_ALLOWED_VALUES[0]
    | _TIMEOUT_ACTION_ALLOWED_VALUES[1]
    | __tuple(
        _TIMEOUT_ACTION_ALLOWED_VALUES[0], _TIMEOUT_ACTION_ALLOWED_VALUES[1]
    )
    | __tuple(
        _TIMEOUT_ACTION_ALLOWED_VALUES[1], _TIMEOUT_ACTION_ALLOWED_VALUES[0]
    )
)


class _ValueSbdDelayStart(validate.ValuePredicateBase):
    def _is_valid(self, value: validate.TypeOptionValue) -> bool:
        # 1 means yes, so we don't allow it to prevent confusion
        return value in ["yes", "no"] or is_integer(value, 2)

    def _get_allowed_values(self) -> Any:
        return "'yes', 'no' or an integer greater than 1"


def _validate_sbd_options(
    sbd_config: Mapping[str, str],
    allow_unknown_opts: bool = False,
    allow_invalid_option_values: bool = False,
) -> reports.ReportItemList:
    """
    Validate user SBD configuration. Options 'SBD_WATCHDOG_DEV' and 'SBD_OPTS'
    are restricted

    sbd_config -- dictionary in format: <SBD config option>: <value>
    allow_unknown_opts -- if True, accept also unknown options.
    """
    validators = [
        validate.NamesIn(
            _ALLOWED_SBD_OPTION_LIST,
            banned_name_list=_UNSUPPORTED_SBD_OPTION_LIST,
            severity=reports.item.get_severity(
                reports.codes.FORCE, allow_unknown_opts
            ),
        ),
        _ValueSbdDelayStart(
            "SBD_DELAY_START",
            severity=reports.item.get_severity(
                reports.codes.FORCE, allow_invalid_option_values
            ),
        ),
        validate.ValueIn(
            "SBD_STARTMODE",
            _STARTMODE_ALLOWED_VALUES,
            severity=reports.item.get_severity(
                reports.codes.FORCE, allow_invalid_option_values
            ),
        ),
        validate.ValueNonnegativeInteger("SBD_WATCHDOG_TIMEOUT"),
        validate.ValueIn(
            "SBD_TIMEOUT_ACTION",
            _TIMEOUT_ACTION_ALLOWED_VALUE_LIST,
            severity=reports.item.get_severity(
                reports.codes.FORCE, allow_invalid_option_values
            ),
        ),
    ]
    return validate.ValidatorAll(validators).validate(sbd_config)


def _validate_watchdog_dict(
    watchdog_dict: Mapping[str, str],
) -> reports.ReportItemList:
    """
    Validates if all watchdogs are not empty strings.

    watchdog_dict -- dictionary with node names as keys and value as watchdog
    """
    return [
        reports.ReportItem.error(reports.messages.WatchdogInvalid(watchdog))
        for watchdog in watchdog_dict.values()
        if not watchdog
    ]


def _get_full_target_dict[T](
    target_list: Iterable[RequestTarget],
    node_value_dict: Mapping[str, T],
    default_value: T,
) -> dict[str, T]:
    """
    Returns dictionary where keys are labels of all nodes in cluster and value
    is obtained from node_value_dict for node name, or default value if node
    is not specified in node_value_dict.

    node_list -- cluster nodes
    node_value_dict -- dictionary, keys: node names, values: some value
    default_value -- some default value
    """
    return {
        target.label: node_value_dict.get(target.label, default_value)
        for target in target_list
    }


def enable_sbd(  # noqa: PLR0913
    lib_env: LibraryEnvironment,
    default_watchdog: Optional[str],
    watchdog_dict: Mapping[str, str],
    sbd_options: Mapping[str, str],
    default_device_list: Optional[StringSequence] = None,
    node_device_dict: Optional[Mapping[str, StringSequence]] = None,
    *,
    allow_unknown_opts: bool = False,
    ignore_offline_nodes: bool = False,
    no_watchdog_validation: bool = False,
    allow_invalid_option_values: bool = False,
) -> None:
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    """
    Enable SBD on all nodes in cluster.

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
    no_watchdog_validation -- it True, do not validate existence of a watchdog
        on the nodes
    allow_invalid_option_values -- if True, invalid values of some options will
        be treated as warning instead of errors
    """
    using_devices = not (
        default_device_list is None and node_device_dict is None
    )
    if default_device_list is None:
        default_device_list = []
    if node_device_dict is None:
        node_device_dict = {}
    if not default_watchdog:
        default_watchdog = settings.sbd_watchdog_default
    sbd_options = {opt.upper(): val for opt, val in sbd_options.items()}

    corosync_conf = lib_env.get_corosync_conf()

    node_list, get_nodes_report_list = get_existing_nodes_names(corosync_conf)
    if not node_list:
        get_nodes_report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    target_list = lib_env.get_node_target_factory().get_target_list(
        node_list,
        skip_non_existing=ignore_offline_nodes,
    )

    full_watchdog_dict = _get_full_target_dict(
        target_list, watchdog_dict, default_watchdog
    )
    full_device_dict = _get_full_target_dict(
        target_list, node_device_dict, default_device_list
    )

    if lib_env.report_processor.report_list(
        get_nodes_report_list
        + [
            reports.ReportItem.error(reports.messages.NodeNotFound(node))
            for node in (
                set(list(watchdog_dict.keys()) + list(node_device_dict.keys()))
                - set(node_list)
            )
        ]
        + _validate_watchdog_dict(full_watchdog_dict)
        + (
            sbd.validate_nodes_devices(full_device_dict)
            if using_devices
            else []
        )
        + _validate_sbd_options(
            sbd_options, allow_unknown_opts, allow_invalid_option_values
        )
    ).has_errors:
        raise LibraryError()

    com_cmd_1 = GetOnlineTargets(
        lib_env.report_processor,
        ignore_offline_targets=ignore_offline_nodes,
    )
    com_cmd_1.set_targets(target_list)
    online_targets = run_and_raise(lib_env.get_node_communicator(), com_cmd_1)

    # check if SBD can be enabled
    if no_watchdog_validation:
        lib_env.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.SbdWatchdogValidationInactive()
            )
        )
    com_cmd_2 = CheckSbd(lib_env.report_processor)
    for target in online_targets:
        com_cmd_2.add_request(
            target,
            (
                # Do not send watchdog if validation is turned off. Listing of
                # available watchdogs in pcsd may restart the machine in some
                # corner cases.
                ""
                if no_watchdog_validation
                else full_watchdog_dict[target.label]
            ),
            full_device_dict[target.label] if using_devices else [],
        )
    run_and_raise(lib_env.get_node_communicator(), com_cmd_2)

    # enable ATB if needed
    if not using_devices:
        if sbd.atb_has_to_be_enabled_pre_enable_check(corosync_conf):
            lib_env.report_processor.report(
                reports.ReportItem.warning(
                    reports.messages.CorosyncQuorumAtbWillBeEnabledDueToSbd()
                )
            )
            corosync_conf.set_quorum_options({"auto_tie_breaker": "1"})
            lib_env.push_corosync_conf(corosync_conf, ignore_offline_nodes)

    # distribute SBD configuration
    config = sbd.get_default_sbd_config()
    config.update(sbd_options)
    com_cmd_3 = SetSbdConfig(lib_env.report_processor)
    for target in online_targets:
        com_cmd_3.add_request(
            target,
            sbd.create_sbd_config(
                config,
                target.label,
                full_watchdog_dict[target.label],
                full_device_dict[target.label],
            ),
        )
    run_and_raise(lib_env.get_node_communicator(), com_cmd_3)

    # remove cluster prop 'stonith_watchdog_timeout'
    com_cmd_4 = RemoveStonithWatchdogTimeout(lib_env.report_processor)
    com_cmd_4.set_targets(online_targets)
    run_and_raise(lib_env.get_node_communicator(), com_cmd_4)

    # enable SBD service an all nodes
    com_cmd_5 = EnableSbdService(lib_env.report_processor)
    com_cmd_5.set_targets(online_targets)
    run_and_raise(lib_env.get_node_communicator(), com_cmd_5)

    lib_env.report_processor.report(
        reports.ReportItem.warning(
            reports.messages.ClusterRestartRequiredToApplyChanges()
        )
    )


def disable_sbd(
    lib_env: LibraryEnvironment, ignore_offline_nodes: bool = False
) -> None:
    """
    Disable SBD on all nodes in cluster.

    ignore_offline_nodes -- if True, omit offline nodes
    """
    node_list, get_nodes_report_list = get_existing_nodes_names(
        lib_env.get_corosync_conf()
    )
    if not node_list:
        get_nodes_report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    if lib_env.report_processor.report_list(get_nodes_report_list).has_errors:
        raise LibraryError()

    com_cmd_1 = GetOnlineTargets(
        lib_env.report_processor,
        ignore_offline_targets=ignore_offline_nodes,
    )
    com_cmd_1.set_targets(
        lib_env.get_node_target_factory().get_target_list(
            node_list,
            skip_non_existing=ignore_offline_nodes,
        )
    )
    online_nodes = run_and_raise(lib_env.get_node_communicator(), com_cmd_1)

    com_cmd_2 = SetStonithWatchdogTimeoutToZero(lib_env.report_processor)
    com_cmd_2.set_targets(online_nodes)
    run_and_raise(lib_env.get_node_communicator(), com_cmd_2)

    com_cmd_3 = DisableSbdService(lib_env.report_processor)
    com_cmd_3.set_targets(online_nodes)
    run_and_raise(lib_env.get_node_communicator(), com_cmd_3)

    lib_env.report_processor.report(
        reports.ReportItem.warning(
            reports.messages.ClusterRestartRequiredToApplyChanges()
        )
    )


def get_cluster_sbd_status(
    lib_env: LibraryEnvironment,
) -> dict[str, dict[str, bool]]:
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
    """
    node_list, get_nodes_report_list = get_existing_nodes_names(
        lib_env.get_corosync_conf()
    )
    if not node_list:
        get_nodes_report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    if lib_env.report_processor.report_list(get_nodes_report_list).has_errors:
        raise LibraryError()

    com_cmd = GetSbdStatus(lib_env.report_processor)
    com_cmd.set_targets(
        lib_env.get_node_target_factory().get_target_list(
            node_list, skip_non_existing=True
        )
    )
    return run_com(lib_env.get_node_communicator(), com_cmd)


def get_cluster_sbd_config(
    lib_env: LibraryEnvironment,
) -> list[dict[str, Optional[str]]]:
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
    """
    node_list, get_nodes_report_list = get_existing_nodes_names(
        lib_env.get_corosync_conf()
    )
    if not node_list:
        get_nodes_report_list.append(
            reports.ReportItem.error(
                reports.messages.CorosyncConfigNoNodesDefined()
            )
        )
    if lib_env.report_processor.report_list(get_nodes_report_list).has_errors:
        raise LibraryError()

    com_cmd = GetSbdConfig(lib_env.report_processor)
    com_cmd.set_targets(
        lib_env.get_node_target_factory().get_target_list(
            node_list, skip_non_existing=True
        )
    )
    return run_com(lib_env.get_node_communicator(), com_cmd)


def get_local_sbd_config(lib_env: LibraryEnvironment) -> dict[str, str]:
    """
    Returns local SBD config as dictionary.
    """
    del lib_env
    return environment_file_to_dict(sbd.get_local_sbd_config())


def initialize_block_devices(
    lib_env: LibraryEnvironment,
    device_list: StringSequence,
    option_dict: Mapping[str, str],
) -> None:
    """
    Initialize SBD devices in device_list with options_dict.
    """
    report_item_list = []
    if not device_list:
        report_item_list.append(
            reports.ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(["device"])
            )
        )

    supported_options = sbd.DEVICE_INITIALIZATION_OPTIONS_MAPPING.keys()

    report_item_list += validate.NamesIn(supported_options).validate(
        option_dict
    )

    report_item_list += validate.ValidatorAll(
        [validate.ValueNonnegativeInteger(key) for key in supported_options]
    ).validate(option_dict)

    if lib_env.report_processor.report_list(report_item_list).has_errors:
        raise LibraryError()
    sbd.initialize_block_devices(
        lib_env.report_processor, lib_env.cmd_runner(), device_list, option_dict
    )


def get_local_devices_info(
    lib_env: LibraryEnvironment, dump: bool = False
) -> list[dict[str, Optional[str]]]:
    """
    Returns list of local devices info in format:
    {
        "device": <device_path>,
        "list": <output of 'sbd list' command>,
        "dump": <output of 'sbd dump' command> if dump is True, None otherwise
    }
    If sbd is not enabled, empty list will be returned.

    dump -- if True returns also output of command 'sbd dump'
    """
    if not sbd.is_sbd_enabled(lib_env.service_manager):
        return []
    device_list = sbd.get_local_sbd_device_list()
    report_item_list: reports.ReportItemList = []
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
        report_item.severity = reports.item.ReportItemSeverity.warning()
    if lib_env.report_processor.report_list(report_item_list).has_errors:
        raise LibraryError()
    return output


def set_message(
    lib_env: LibraryEnvironment, device: str, node_name: str, message: str
) -> None:
    """
    Set message on device for node_name.

    device -- absolute path to device
    node_name --
    message -- message type, should be one of settings.sbd_message_types
    """
    report_item_list = []
    missing_options = []
    if not device:
        missing_options.append("device")
    if not node_name:
        missing_options.append("node")
    if missing_options:
        report_item_list.append(
            reports.ReportItem.error(
                reports.messages.RequiredOptionsAreMissing(missing_options)
            )
        )
    supported_messages = settings.sbd_message_types
    if message not in supported_messages:
        report_item_list.append(
            reports.ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "message", message, supported_messages
                )
            )
        )
    if lib_env.report_processor.report_list(report_item_list).has_errors:
        raise LibraryError()
    sbd.set_message(lib_env.cmd_runner(), device, node_name, message)


def get_local_available_watchdogs(
    lib_env: LibraryEnvironment,
) -> dict[str, dict[str, str]]:
    """
    Returns available local watchdog devices.
    """
    return sbd.get_available_watchdogs(lib_env.cmd_runner())


def test_local_watchdog(
    lib_env: LibraryEnvironment, watchdog: Optional[str] = None
) -> None:
    """
    Test local watchdog device by triggering it. System reset is expected. If
    watchdog is not specified, available watchdog will be used if there is only
    one.

    watchdog -- watchdog to trigger
    """
    lib_env.report_processor.report(
        reports.ReportItem.info(reports.messages.SystemWillReset())
    )
    sbd.test_watchdog(lib_env.cmd_runner(), watchdog)
