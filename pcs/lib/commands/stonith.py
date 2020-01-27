from typing import (
    Optional,
)

from pcs.lib import reports
from pcs.lib.cib import resource
from pcs.lib.cib.resource.common import are_meta_disabled
from pcs.lib.cib.tools import IdProvider
from pcs.lib.commands.resource import (
    _ensure_disabled_after_wait,
    resource_environment
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.live import (
    FenceHistoryCommandErrorException,
    fence_history_cleanup,
    fence_history_text,
    fence_history_update,
    is_fence_history_supported_management,
)
from pcs.lib.pacemaker.values import validate_id
from pcs.lib.resource_agent import find_valid_stonith_agent_by_name as get_agent

def create(
    env, stonith_id, stonith_agent_name,
    operations, meta_attributes, instance_attributes,
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
        )
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
            resource_type="stonith"
        )
        if ensure_disabled:
            resource.common.disable(stonith_element, id_provider)

def create_in_group(
    env, stonith_id, stonith_agent_name, group_id,
    operations, meta_attributes, instance_attributes,
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
        )
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        stonith_element = resource.primitive.create(
            env.report_processor, resources_section, id_provider,
            stonith_id, stonith_agent,
            operations, meta_attributes, instance_attributes,
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
        raise LibraryError(reports.fence_history_not_supported())

    try:
        return fence_history_text(runner, node)
    except FenceHistoryCommandErrorException as e:
        raise LibraryError(
            reports.fence_history_command_error(str(e), "show")
        )

def history_cleanup(env: LibraryEnvironment, node: Optional[str] = None):
    """
    Clear fencing history

    env
    node -- clear history for the specified node or all nodes if None
    """
    runner = env.cmd_runner()
    if not is_fence_history_supported_management(runner):
        raise LibraryError(reports.fence_history_not_supported())

    try:
        return fence_history_cleanup(runner, node)
    except FenceHistoryCommandErrorException as e:
        raise LibraryError(
            reports.fence_history_command_error(str(e), "cleanup")
        )

def history_update(env: LibraryEnvironment):
    """
    Update fencing history in a cluster (sync with other nodes)

    env
    """
    runner = env.cmd_runner()
    if not is_fence_history_supported_management(runner):
        raise LibraryError(reports.fence_history_not_supported())

    try:
        return fence_history_update(runner)
    except FenceHistoryCommandErrorException as e:
        raise LibraryError(
            reports.fence_history_command_error(str(e), "update")
        )
