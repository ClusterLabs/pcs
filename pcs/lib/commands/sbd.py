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


def _validate_sbd_options(sbd_config, allow_unknown_opts=False):
    """
    Validate user SBD configuration. Options 'SBD_WATCHDOG_DEV' and 'SBD_OPTS'
    are restricted. Returns list of ReportItem

    sbd_config -- dictionary in format: <SBD config option>: <value>
    allow_unknown_opts -- if True, accept also unknown options.
    """

    report_item_list = []
    unsupported_sbd_option_list = [
        "SBD_WATCHDOG_DEV", "SBD_OPTS", "SBD_PACEMAKER"
    ]
    allowed_sbd_options = [
        "SBD_DELAY_START", "SBD_STARTMODE", "SBD_WATCHDOG_TIMEOUT"
    ]
    for sbd_opt in sbd_config:
        if sbd_opt in unsupported_sbd_option_list:
            report_item_list.append(reports.invalid_option(
                sbd_opt, allowed_sbd_options, None
            ))

        elif sbd_opt not in allowed_sbd_options:
            report_item_list.append(reports.invalid_option(
                sbd_opt,
                allowed_sbd_options,
                None,
                Severities.WARNING if allow_unknown_opts else Severities.ERROR,
                None if allow_unknown_opts else report_codes.FORCE_OPTIONS
            ))
    if "SBD_WATCHDOG_TIMEOUT" in sbd_config:
        report_item = reports.invalid_option_value(
            "SBD_WATCHDOG_TIMEOUT",
            sbd_config["SBD_WATCHDOG_TIMEOUT"],
            "nonnegative integer"
        )
        try:
            if int(sbd_config["SBD_WATCHDOG_TIMEOUT"]) < 0:
                report_item_list.append(report_item)
        except (ValueError, TypeError):
            report_item_list.append(report_item)

    return report_item_list


def _get_full_watchdog_list(node_list, default_watchdog, watchdog_dict):
    """
    Validate if all nodes in watchdog_dict does exist and returns dictionary
    where keys are nodes and value is corresponding watchdog.
    Raises LibraryError if any of nodes doesn't belong to cluster.

    node_list -- NodeAddressesList
    default_watchdog -- watchdog for nodes which are not specified
        in watchdog_dict
    watchdog_dict -- dictionary with node names as keys and value as watchdog
    """
    full_dict = dict([(node, default_watchdog) for node in node_list])
    report_item_list = []

    for node_name, watchdog in watchdog_dict.items():
        if not watchdog or not os.path.isabs(watchdog):
            report_item_list.append(reports.invalid_watchdog_path(watchdog))
            continue
        try:
            full_dict[node_list.find_by_label(node_name)] = watchdog
        except NodeNotFound:
            report_item_list.append(reports.node_not_found(node_name))

    if report_item_list:
        raise LibraryError(*report_item_list)

    return full_dict


def enable_sbd(
        lib_env, default_watchdog, watchdog_dict, sbd_options,
        allow_unknown_opts=False, ignore_offline_nodes=False
):
    """
    Enable SBD on all nodes in cluster.

    lib_env -- LibraryEnvironment
    default_watchdog -- watchdog for nodes which are not specified in
        watchdog_dict. Uses default value from settings if None.
    watchdog_dict -- dictionary with NodeAddresses as keys and watchdog path
        as value
    sbd_options -- dictionary in format: <SBD config option>: <value>
    allow_unknown_opts -- if True, accept also unknown options.
    ignore_offline_nodes -- if True, omit offline nodes
    """
    node_list = _get_cluster_nodes(lib_env)

    if not default_watchdog:
        default_watchdog = settings.sbd_watchdog_default

    # input validation begin
    full_watchdog_dict = _get_full_watchdog_list(
        node_list, default_watchdog, watchdog_dict
    )

    # config validation
    sbd_options = dict([(opt.upper(), val) for opt, val in sbd_options.items()])
    lib_env.report_processor.process_list(
        _validate_sbd_options(sbd_options, allow_unknown_opts)
    )

    # check nodes status
    online_nodes = _get_online_nodes(lib_env, node_list, ignore_offline_nodes)
    for node in list(full_watchdog_dict):
        if node not in online_nodes:
            full_watchdog_dict.pop(node, None)
    # input validation end

    # check if SBD can be enabled
    sbd.check_sbd_on_all_nodes(
        lib_env.report_processor,
        lib_env.node_communicator(),
        full_watchdog_dict
    )

    # enable ATB if needed
    if not lib_env.is_cman_cluster:
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
        full_watchdog_dict
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
                "node": node,
                "status": json.loads(
                    sbd.check_sbd(lib_env.node_communicator(), node, "")
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
                "node": node,
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
                "node": node,
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
                "node": node,
                "config": None
            })
    return config_list


def get_local_sbd_config(lib_env):
    return environment_file_to_dict(sbd.get_local_sbd_config())


def _get_cluster_nodes(lib_env):
    if lib_env.is_cman_cluster:
        return lib_env.get_cluster_conf().get_nodes()
    else:
        return lib_env.get_corosync_conf().get_nodes()

