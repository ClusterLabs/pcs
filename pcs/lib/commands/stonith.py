from typing import (
    Collection,
    Container,
    List,
    Mapping,
    Optional,
    Tuple,
)

from lxml.etree import _Element

from pcs.common import reports
from pcs.common.reports import ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.types import StringCollection
from pcs.lib.cib import resource
from pcs.lib.cib.nvpair import (
    INSTANCE_ATTRIBUTES_TAG,
    get_value,
)
from pcs.lib.cib.tools import (
    ElementNotFound,
    IdProvider,
    get_element_by_id,
)
from pcs.lib.commands.resource import (
    _ensure_disabled_after_wait,
    resource_environment,
)
from pcs.lib.communication.corosync import GetCorosyncOnlineTargets
from pcs.lib.communication.scsi import (
    Unfence,
    UnfenceMpath,
)
from pcs.lib.communication.tools import (
    AllSameDataMixin,
    run_and_raise,
)
from pcs.lib.env import (
    LibraryEnvironment,
    WaitType,
)
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
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
from pcs.lib.resource_agent import (
    InvalidResourceAgentName,
    ResourceAgentError,
    ResourceAgentFacade,
    ResourceAgentFacadeFactory,
    ResourceAgentName,
    UnableToGetAgentMetadata,
    UnsupportedOcfVersion,
    resource_agent_error_to_report_item,
)
from pcs.lib.validate import validate_add_remove_items
from pcs.lib.xml_tools import get_root


def _get_agent_facade(
    report_processor: reports.ReportProcessor,
    factory: ResourceAgentFacadeFactory,
    name: str,
    allow_absent_agent: bool,
) -> ResourceAgentFacade:
    try:
        if ":" in name:
            raise InvalidResourceAgentName(name)
        full_name = ResourceAgentName("stonith", None, name)
        return factory.facade_from_parsed_name(full_name)
    except (UnableToGetAgentMetadata, UnsupportedOcfVersion) as e:
        if allow_absent_agent:
            report_processor.report(
                resource_agent_error_to_report_item(
                    e, reports.ReportItemSeverity.warning(), is_stonith=True
                )
            )
            return factory.void_facade_from_parsed_name(full_name)
        report_processor.report(
            resource_agent_error_to_report_item(
                e,
                reports.ReportItemSeverity.error(reports.codes.FORCE),
                is_stonith=True,
            )
        )
        raise LibraryError() from e
    except ResourceAgentError as e:
        report_processor.report(
            resource_agent_error_to_report_item(
                e, reports.ReportItemSeverity.error(), is_stonith=True
            )
        )
        raise LibraryError() from e


def create(
    env: LibraryEnvironment,
    stonith_id: str,
    stonith_agent_name: str,
    operations: Collection[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    *,
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    wait: WaitType = False,
    enable_agent_self_validation: bool = False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    """
    Create stonith as resource in a cib.

    env -- provides all for communication with externals
    stonith_id -- an identifier of stonith resource
    stonith_agent_name -- contains name for the identification of agent
    operations -- contains attributes for each entered operation
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for primitive/instance_attributes
    allow_absent_agent -- a flag for allowing agent not installed in a system
    allow_invalid_operation -- a flag for allowing to use operations that
        are not listed in a stonith agent metadata
    allow_invalid_instance_attributes -- a flag for allowing to use instance
        attributes that are not listed in a stonith agent metadata or for
        allowing to not use the instance_attributes that are required in
        stonith agent metadata
    use_default_operations -- a flag for stopping of adding default cib
        operations (specified in a stonith agent)
    ensure_disabled -- flag that keeps resource in target-role "Stopped"
    wait -- flag for controlling waiting for pacemaker idle mechanism
    enable_agent_self_validation -- if True, use agent self-validation feature
        to validate instance attributes
    """
    runner = env.cmd_runner()
    agent_factory = ResourceAgentFacadeFactory(runner, env.report_processor)
    stonith_agent = _get_agent_facade(
        env.report_processor,
        agent_factory,
        stonith_agent_name,
        allow_absent_agent,
    )
    if stonith_agent.metadata.provides_unfencing:
        meta_attributes = dict(meta_attributes, provides="unfencing")

    with resource_environment(
        env,
        wait,
        [stonith_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or resource.common.are_meta_disabled(meta_attributes),
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        stonith_element = resource.primitive.create(
            env.report_processor,
            runner,
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
            enable_agent_self_validation=enable_agent_self_validation,
        )
        if ensure_disabled:
            resource.common.disable(stonith_element, id_provider)


# DEPRECATED: this command is deprecated and will be removed in a future release
def create_in_group(
    env: LibraryEnvironment,
    stonith_id: str,
    stonith_agent_name: str,
    group_id: str,
    operations: Collection[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    *,
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    adjacent_resource_id: Optional[str] = None,
    put_after_adjacent: bool = False,
    wait: WaitType = False,
    enable_agent_self_validation: bool = False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    """
    DEPRECATED
    Create stonith as resource in a cib and put it into defined group.

    env -- provides all for communication with externals
    stonith_id --an identifier of stonith resource
    stonith_agent_name -- contains name for the identification of agent
    group_id -- identificator for group to put stonith inside
    operations -- contains attributes for each entered operation
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for primitive/instance_attributes
    allow_absent_agent -- a flag for allowing agent not installed in a system
    allow_invalid_operation -- a flag for allowing to use operations that
        are not listed in a stonith agent metadata
    allow_invalid_instance_attributes -- a flag for allowing to use instance
        attributes that are not listed in a stonith agent metadata or for
        allowing to not use the instance_attributes that are required in
        stonith agent metadata
    use_default_operations -- a flag for stopping of adding default cib
        operations (specified in a stonith agent)
    ensure_disabled -- flag that keeps resource in target-role "Stopped"
    adjacent_resource_id -- identify neighbor of a newly created stonith
    put_after_adjacent -- is flag to put a newly create resource befor/after
        adjacent stonith
    wait -- flag for controlling waiting for pacemaker idle mechanism
    enable_agent_self_validation -- if True, use agent self-validation feature
        to validate instance attributes
    """
    runner = env.cmd_runner()
    agent_factory = ResourceAgentFacadeFactory(runner, env.report_processor)
    stonith_agent = _get_agent_facade(
        env.report_processor,
        agent_factory,
        stonith_agent_name,
        allow_absent_agent,
    )
    if stonith_agent.metadata.provides_unfencing:
        meta_attributes = dict(meta_attributes, provides="unfencing")

    with resource_environment(
        env,
        wait,
        [stonith_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or resource.common.are_meta_disabled(meta_attributes),
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)

        adjacent_resource_element = None
        if adjacent_resource_id:
            try:
                adjacent_resource_element = get_element_by_id(
                    get_root(resources_section), adjacent_resource_id
                )
            except ElementNotFound:
                # We cannot continue without adjacent element because
                # the validator might produce misleading reports
                if env.report_processor.report(
                    ReportItem.error(
                        reports.messages.IdNotFound(adjacent_resource_id, [])
                    )
                ).has_errors:
                    raise LibraryError() from None

        try:
            group_element = get_element_by_id(
                get_root(resources_section), group_id
            )
        except ElementNotFound:
            group_id_reports: List[ReportItem] = []
            validate_id(
                group_id, description="group name", reporter=group_id_reports
            )
            env.report_processor.report_list(group_id_reports)
            group_element = resource.group.append_new(
                resources_section, group_id
            )

        stonith_element = resource.primitive.create(
            env.report_processor,
            runner,
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
            enable_agent_self_validation=enable_agent_self_validation,
        )
        if ensure_disabled:
            resource.common.disable(stonith_element, id_provider)

        if env.report_processor.report_list(
            resource.validations.validate_move_resources_to_group(
                group_element,
                [stonith_element],
                adjacent_resource_element,
            )
        ).has_errors:
            raise LibraryError()

        resource.hierarchy.move_resources_to_group(
            group_element,
            [stonith_element],
            adjacent_resource_element,
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
    runner: CommandRunner,
    report_processor: ReportProcessor,
    cib: _Element,
    stonith_id: str,
) -> Tuple[_Element, List[str]]:
    """
    Do checks and return stonith element and list of current scsi devices.
    Raise LibraryError if checks fail.

    runner -- command runner instance
    report_processor -- tool for warning/info/error reporting
    cib -- cib element
    stonith_id -- id of stonith resource
    """
    if not is_getting_resource_digest_supported(runner):
        raise LibraryError(
            ReportItem.error(
                reports.messages.StonithRestartlessUpdateOfScsiDevicesNotSupported()
            )
        )
    (
        stonith_el,
        report_list,
    ) = resource.stonith.validate_stonith_restartless_update(cib, stonith_id)
    if report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    # for mypy, this should not happen because exception would be raised
    if stonith_el is None:
        raise AssertionError("stonith element is None")
    current_device_list = get_value(
        INSTANCE_ATTRIBUTES_TAG, stonith_el, "devices"
    )
    if current_device_list is None:
        raise AssertionError("current_device_list is None")
    return stonith_el, current_device_list.split(",")


def _unfencing_scsi_devices(
    env: LibraryEnvironment,
    stonith_el: _Element,
    original_devices: StringCollection,
    updated_devices: StringCollection,
    force_flags: Container[reports.types.ForceCode] = (),
) -> None:
    """
    Unfence scsi devices provided in device_list if it is possible to connect
    to pcsd and corosync is running.

    env -- provides all for communication with externals
    original_devices -- devices before update
    updated_devices -- devices after update
    force_flags -- list of flags codes
    """
    devices_to_unfence = set(updated_devices) - set(original_devices)
    if not devices_to_unfence:
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
    if stonith_el.get("type") == "fence_mpath":
        com_cmd = UnfenceMpath(
            env.report_processor,
            original_devices=sorted(original_devices),
            updated_devices=sorted(updated_devices),
            node_key_map=resource.stonith.get_node_key_map_for_mpath(
                stonith_el,
                [target.label for target in online_corosync_target_list],
            ),
        )
    else:  # fence_scsi
        com_cmd = Unfence(
            env.report_processor,
            original_devices=sorted(original_devices),
            updated_devices=sorted(updated_devices),
        )
    com_cmd.set_targets(online_corosync_target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)


def update_scsi_devices(
    env: LibraryEnvironment,
    stonith_id: str,
    set_device_list: StringCollection,
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
    if not set_device_list:
        env.report_processor.report(
            ReportItem.error(
                reports.messages.InvalidOptionValue(
                    "devices", "", None, cannot_be_empty=True
                )
            )
        )
    runner = env.cmd_runner()
    (
        stonith_el,
        current_device_list,
    ) = _update_scsi_devices_get_element_and_devices(
        runner, env.report_processor, env.get_cib(), stonith_id
    )
    if env.report_processor.has_errors:
        raise LibraryError()
    resource.stonith.update_scsi_devices_without_restart(
        runner,
        env.get_cluster_state(),
        stonith_el,
        IdProvider(stonith_el),
        set_device_list,
    )
    _unfencing_scsi_devices(
        env, stonith_el, current_device_list, set_device_list, force_flags
    )
    env.push_cib()


def update_scsi_devices_add_remove(
    env: LibraryEnvironment,
    stonith_id: str,
    add_device_list: StringCollection,
    remove_device_list: StringCollection,
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
    runner = env.cmd_runner()
    (
        stonith_el,
        current_device_list,
    ) = _update_scsi_devices_get_element_and_devices(
        runner, env.report_processor, env.get_cib(), stonith_id
    )
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
    resource.stonith.update_scsi_devices_without_restart(
        env.cmd_runner(),
        env.get_cluster_state(),
        stonith_el,
        IdProvider(stonith_el),
        updated_device_set,
    )
    _unfencing_scsi_devices(
        env, stonith_el, current_device_list, updated_device_set, force_flags
    )
    env.push_cib()
