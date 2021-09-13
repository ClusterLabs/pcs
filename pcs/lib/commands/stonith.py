from typing import Container, Iterable, List, Optional, Tuple

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.cib import resource
from pcs.lib.cib import stonith
from pcs.lib.cib.nvpair import INSTANCE_ATTRIBUTES_TAG, get_value
from pcs.lib.cib.resource.common import are_meta_disabled
from pcs.lib.cib.tools import IdProvider
from pcs.lib.commands.resource import (
    _ensure_disabled_after_wait,
    resource_environment,
)
from pcs.lib.communication.corosync import GetCorosyncOnlineTargets

# from pcs.lib.communication.nodes import GetOnlineTargets
from pcs.lib.communication.scsi import Unfence
from pcs.lib.communication.tools import (
    AllSameDataMixin,
    run_and_raise,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.live import (
    FenceHistoryCommandErrorException,
    fence_history_cleanup,
    fence_history_text,
    fence_history_update,
    is_fence_history_supported_management,
    is_getting_resource_digest_supported,
)
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.validate import validate_add_remove_items
from pcs.lib.resource_agent import find_valid_stonith_agent_by_name as get_agent


def create(
    env,
    stonith_id,
    stonith_agent_name,
    operations,
    meta_attributes,
    instance_attributes,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    wait=False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create stonith as resource in a cib.

    LibraryEnvironment env provides all for communication with externals
    string stonith_id is an identifier of stonith resource
    string stonith_agent_name contains name for the identification of agent
    list of dict operations contains attributes for each entered operation
    dict meta_attributes contains attributes for primitive/meta_attributes
    dict instance_attributes contains attributes for
        primitive/instance_attributes
    bool allow_absent_agent is a flag for allowing agent that is not installed
        in a system
    bool allow_invalid_operation is a flag for allowing to use operations that
        are not listed in a stonith agent metadata
    bool allow_invalid_instance_attributes is a flag for allowing to use
        instance attributes that are not listed in a stonith agent metadata
        or for allowing to not use the instance_attributes that are required in
        stonith agent metadata
    bool use_default_operations is a flag for stopping stopping of adding
        default cib operations (specified in a stonith agent)
    bool ensure_disabled is flag that keeps resource in target-role "Stopped"
    mixed wait is flag for controlling waiting for pacemaker idle mechanism
    """
    stonith_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        stonith_agent_name,
        allow_absent_agent,
    )
    if stonith_agent.get_provides_unfencing():
        meta_attributes["provides"] = "unfencing"

    with resource_environment(
        env,
        wait,
        [stonith_id],
        _ensure_disabled_after_wait(
            ensure_disabled or are_meta_disabled(meta_attributes),
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        stonith_element = resource.primitive.create(
            env.report_processor,
            resources_section,
            id_provider,
            stonith_id,
            stonith_agent,
            raw_operation_list=operations,
            meta_attributes=meta_attributes,
            instance_attributes=instance_attributes,
            allow_invalid_operation=allow_invalid_operation,
            allow_invalid_instance_attributes=allow_invalid_instance_attributes,
            use_default_operations=use_default_operations,
            resource_type="stonith",
        )
        if ensure_disabled:
            resource.common.disable(stonith_element, id_provider)


def create_in_group(
    env,
    stonith_id,
    stonith_agent_name,
    group_id,
    operations,
    meta_attributes,
    instance_attributes,
    allow_absent_agent=False,
    allow_invalid_operation=False,
    allow_invalid_instance_attributes=False,
    use_default_operations=True,
    ensure_disabled=False,
    adjacent_resource_id=None,
    put_after_adjacent=False,
    wait=False,
):
    # pylint: disable=too-many-arguments, too-many-locals
    """
    Create stonith as resource in a cib and put it into defined group.

    LibraryEnvironment env provides all for communication with externals
    string stonith_id is an identifier of stonith resource
    string stonith_agent_name contains name for the identification of agent
    string group_id is identificator for group to put stonith inside
    list of dict operations contains attributes for each entered operation
    dict meta_attributes contains attributes for primitive/meta_attributes
    dict instance_attributes contains attributes for
        primitive/instance_attributes
    bool allow_absent_agent is a flag for allowing agent that is not installed
        in a system
    bool allow_invalid_operation is a flag for allowing to use operations that
        are not listed in a stonith agent metadata
    bool allow_invalid_instance_attributes is a flag for allowing to use
        instance attributes that are not listed in a stonith agent metadata
        or for allowing to not use the instance_attributes that are required in
        stonith agent metadata
    bool use_default_operations is a flag for stopping stopping of adding
        default cib operations (specified in a stonith agent)
    bool ensure_disabled is flag that keeps resource in target-role "Stopped"
    string adjacent_resource_id identify neighbor of a newly created stonith
    bool put_after_adjacent is flag to put a newly create resource befor/after
        adjacent stonith
    mixed wait is flag for controlling waiting for pacemaker idle mechanism
    """
    stonith_agent = get_agent(
        env.report_processor,
        env.cmd_runner(),
        stonith_agent_name,
        allow_absent_agent,
    )
    if stonith_agent.get_provides_unfencing():
        meta_attributes["provides"] = "unfencing"

    with resource_environment(
        env,
        wait,
        [stonith_id],
        _ensure_disabled_after_wait(
            ensure_disabled or are_meta_disabled(meta_attributes),
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        stonith_element = resource.primitive.create(
            env.report_processor,
            resources_section,
            id_provider,
            stonith_id,
            stonith_agent,
            operations,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
        if ensure_disabled:
            resource.common.disable(stonith_element, id_provider)
        validate_id(group_id, "group name")
        resource.group.place_resource(
            resource.group.provide_group(resources_section, group_id),
            stonith_element,
            adjacent_resource_id,
            put_after_adjacent,
        )


def history_get_text(env: LibraryEnvironment, node: Optional[str] = None):
    """
    Get full fencing history in plain text

    env
    node -- get history for the specified node or all nodes if None
    """
    runner = env.cmd_runner()
    if not is_fence_history_supported_management(runner):
        raise LibraryError(
            ReportItem.error(reports.messages.FenceHistoryNotSupported())
        )

    try:
        return fence_history_text(runner, node)
    except FenceHistoryCommandErrorException as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.FenceHistoryCommandError(
                    str(e), reports.const.FENCE_HISTORY_COMMAND_SHOW
                )
            )
        ) from e


def history_cleanup(env: LibraryEnvironment, node: Optional[str] = None):
    """
    Clear fencing history

    env
    node -- clear history for the specified node or all nodes if None
    """
    runner = env.cmd_runner()
    if not is_fence_history_supported_management(runner):
        raise LibraryError(
            ReportItem.error(reports.messages.FenceHistoryNotSupported())
        )

    try:
        return fence_history_cleanup(runner, node)
    except FenceHistoryCommandErrorException as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.FenceHistoryCommandError(
                    str(e), reports.const.FENCE_HISTORY_COMMAND_CLEANUP
                )
            )
        ) from e


def history_update(env: LibraryEnvironment):
    """
    Update fencing history in a cluster (sync with other nodes)

    env
    """
    runner = env.cmd_runner()
    if not is_fence_history_supported_management(runner):
        raise LibraryError(
            ReportItem.error(reports.messages.FenceHistoryNotSupported())
        )

    try:
        return fence_history_update(runner)
    except FenceHistoryCommandErrorException as e:
        raise LibraryError(
            ReportItem.error(
                reports.messages.FenceHistoryCommandError(
                    str(e), reports.const.FENCE_HISTORY_COMMAND_UPDATE
                )
            )
        ) from e


def _update_scsi_devices_get_element_and_devices(
    env: LibraryEnvironment, stonith_id: str
) -> Tuple[_Element, List[str]]:
    """
    Do checks and return stonith element and list of current scsi devices.
    Raise LibraryError if checks fail.

    env -- provides all for communication with externals
    stonith_id -- id of stonith resource
    """
    if not is_getting_resource_digest_supported(env.cmd_runner()):
        raise LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateOfScsiDevicesNotSupported()
            )
        )
    (
        stonith_el,
        report_list,
    ) = stonith.validate_stonith_restartless_update(env.get_cib(), stonith_id)
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    current_device_list = get_value(
        INSTANCE_ATTRIBUTES_TAG, stonith_el, "devices"
    )
    # for mypy, this should not happen because exception would be raised
    if stonith_el is None:
        raise AssertionError("stonith element is None")
    if current_device_list is None:
        raise AssertionError("current_device_list is None")
    return stonith_el, current_device_list.split(",")


def _unfencing_scsi_devices(
    env: LibraryEnvironment,
    device_list: Iterable[str],
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    """
    Unfence scsi devices provided in device_list if it is possible to connect
    to pcsd and corosync is running.

    env -- provides all for communication with externals
    device_list -- devices to be unfenced
    force_flags -- list of flags codes
    """
    if not list(device_list):
        return
    cluster_nodes_names, nodes_report_list = get_existing_nodes_names(
        env.get_corosync_conf(),
        error_on_missing_name=True,
    )
    env.report_processor.report_list(nodes_report_list)
    (
        target_report_list,
        cluster_nodes_target_list,
    ) = env.get_node_target_factory().get_target_list_with_reports(
        cluster_nodes_names,
        allow_skip=False,
    )
    env.report_processor.report_list(target_report_list)
    if env.report_processor.has_errors:
        raise LibraryError()
    com_cmd: AllSameDataMixin = GetCorosyncOnlineTargets(
        env.report_processor,
        skip_offline_targets=reports.codes.SKIP_OFFLINE_NODES in force_flags,
    )
    com_cmd.set_targets(cluster_nodes_target_list)
    online_corosync_target_list = run_and_raise(
        env.get_node_communicator(), com_cmd
    )
    com_cmd = Unfence(env.report_processor, sorted(device_list))
    com_cmd.set_targets(online_corosync_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)


def update_scsi_devices(
    env: LibraryEnvironment,
    stonith_id: str,
    set_device_list: Iterable[str],
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    """
    Update scsi fencing devices without restart and affecting other resources.

    env -- provides all for communication with externals
    stonith_id -- id of stonith resource
    set_device_list -- paths to the scsi devices that would be set for stonith
        resource
    force_flags -- list of flags codes
    """
    (
        stonith_el,
        current_device_list,
    ) = _update_scsi_devices_get_element_and_devices(env, stonith_id)
    if not set_device_list:
        env.report_processor.report(
            ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "devices", "", None, cannot_be_empty=True
                )
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()
    stonith.update_scsi_devices_without_restart(
        env.cmd_runner(),
        env.get_cluster_state(),
        stonith_el,
        IdProvider(stonith_el),
        set_device_list,
    )
    devices_for_unfencing = set(set_device_list)
    devices_for_unfencing.difference_update(current_device_list)
    _unfencing_scsi_devices(env, devices_for_unfencing, force_flags)
    env.push_cib()


def update_scsi_devices_add_remove(
    env: LibraryEnvironment,
    stonith_id: str,
    add_device_list: Iterable[str],
    remove_device_list: Iterable[str],
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    """
    Update scsi fencing devices without restart and affecting other resources.

    env -- provides all for communication with externals
    stonith_id -- id of stonith resource
    add_device_list -- paths to the scsi devices that would be added to the
        stonith resource
    remove_device_list -- paths to the scsi devices that would be removed from
        the stonith resource
    force_flags -- list of flags codes
    """
    (
        stonith_el,
        current_device_list,
    ) = _update_scsi_devices_get_element_and_devices(env, stonith_id)
    if env.report_processor.report_list(
        validate_add_remove_items(
            add_device_list,
            remove_device_list,
            current_device_list,
            reports.const.ADD_REMOVE_CONTAINER_TYPE_STONITH_RESOURCE,
            reports.const.ADD_REMOVE_ITEM_TYPE_DEVICE,
            stonith_el.get("id", ""),
        )
    ).has_errors:
        raise LibraryError()
    updated_device_set = (
        set(current_device_list)
        .union(add_device_list)
        .difference(remove_device_list)
    )
    stonith.update_scsi_devices_without_restart(
        env.cmd_runner(),
        env.get_cluster_state(),
        stonith_el,
        IdProvider(stonith_el),
        updated_device_set,
    )
    _unfencing_scsi_devices(env, add_device_list, force_flags)
    env.push_cib()
