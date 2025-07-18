# pylint: disable=too-many-lines
import re
from contextlib import contextmanager
from functools import partial
from typing import (
    Any,
    Callable,
    Dict,
    FrozenSet,
    Iterable,
    List,
    Mapping,
    Optional,
    Set,
    Tuple,
    Union,
    cast,
)

from lxml.etree import _Element

from pcs.common import (
    const,
    file_type_codes,
    reports,
)
from pcs.common.interface import dto
from pcs.common.pacemaker.resource.list import CibResourcesDto
from pcs.common.reports import ReportItemList, ReportProcessor
from pcs.common.reports.item import ReportItem
from pcs.common.resource_status import ResourcesStatusFacade, ResourceState
from pcs.common.tools import (
    Version,
    timeout_to_seconds,
)
from pcs.common.types import StringCollection, StringSequence
from pcs.lib.cib import const as cib_const
from pcs.lib.cib import resource
from pcs.lib.cib import status as cib_status
from pcs.lib.cib.nvpair_multi import (
    NVSET_META,
    find_nvsets,
    nvset_append_new,
    nvset_to_dict_except_without_values,
    nvset_update,
)
from pcs.lib.cib.tag import expand_tag
from pcs.lib.cib.tools import (
    ElementNotFound,
    IdProvider,
    find_element_by_tag_and_id,
    get_element_by_id,
    get_elements_by_ids,
    get_pacemaker_version_by_which_cib_was_validated,
    get_resources,
    get_status,
)
from pcs.lib.env import (
    LibraryEnvironment,
    WaitType,
)
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.node import (
    get_existing_nodes_names_addrs,
    get_pacemaker_node_names,
)
from pcs.lib.pacemaker import simulate as simulate_tools
from pcs.lib.pacemaker.live import (
    diff_cibs_xml,
    get_cib,
    get_cib_xml,
    get_cluster_status_dom,
    has_resource_unmove_unban_expired_support,
    push_cib_diff_xml,
    remove_node,
    resource_ban,
    resource_move,
    resource_restart,
    resource_unmove_unban,
    simulate_cib,
)
from pcs.lib.pacemaker.state import (
    ResourceNotFound,
    ensure_resource_state,
    get_resource_state,
    info_resource_state,
    is_resource_managed,
)
from pcs.lib.pacemaker.status import (
    ClusterStatusParser,
    ClusterStatusParsingError,
    cluster_status_parsing_error_to_report,
)
from pcs.lib.pacemaker.values import (
    is_true,
    validate_id,
)
from pcs.lib.resource_agent import (
    ResourceAgentError,
    ResourceAgentFacade,
    ResourceAgentFacadeFactory,
    ResourceAgentName,
    UnableToGetAgentMetadata,
    UnsupportedOcfVersion,
    find_one_resource_agent_by_type,
    resource_agent_error_to_report_item,
    split_resource_agent_name,
)
from pcs.lib.resource_agent.const import OCF_1_1
from pcs.lib.sbd_stonith import ensure_some_stonith_remains
from pcs.lib.tools import get_tmp_cib
from pcs.lib.validate import ValueTimeInterval
from pcs.lib.xml_tools import (
    etree_to_str,
    get_root,
)


@contextmanager
def resource_environment(
    env: LibraryEnvironment,
    wait: WaitType = False,
    wait_for_resource_ids=None,
    resource_state_reporter=info_resource_state,
    required_cib_version=None,
):
    wait_timeout = env.ensure_wait_satisfiable(wait)
    yield get_resources(env.get_cib(required_cib_version))
    _push_cib_wait(
        env, wait_timeout, wait_for_resource_ids, resource_state_reporter
    )


def _get_resource_state_wait(
    env: LibraryEnvironment,
    wait_timeout: int = -1,
    wait_for_resource_ids: Optional[StringCollection] = None,
    resource_state_reporter: Callable[
        [_Element, str], ReportItem
    ] = info_resource_state,
):
    if wait_timeout >= 0 and wait_for_resource_ids:
        state = env.get_cluster_state()
        if env.report_processor.report_list(
            [
                resource_state_reporter(state, res_id)
                for res_id in wait_for_resource_ids
            ]
        ).has_errors:
            raise LibraryError()


def _push_cib_wait(
    env: LibraryEnvironment,
    wait_timeout: int = -1,
    wait_for_resource_ids: Optional[StringCollection] = None,
    resource_state_reporter: Callable[
        [_Element, str], ReportItem
    ] = info_resource_state,
) -> None:
    env.push_cib(wait_timeout=wait_timeout)
    _get_resource_state_wait(
        env, wait_timeout, wait_for_resource_ids, resource_state_reporter
    )


def _ensure_disabled_after_wait(disabled_after_wait):
    def inner(state, resource_id):
        return ensure_resource_state(
            not disabled_after_wait, state, resource_id
        )

    return inner


def _get_resource_agent_name(
    runner: CommandRunner, report_processor: reports.ReportProcessor, name: str
) -> ResourceAgentName:
    try:
        agent_name = (
            split_resource_agent_name(name)
            if ":" in name
            else find_one_resource_agent_by_type(runner, report_processor, name)
        )
    except ResourceAgentError as e:
        report_processor.report(
            resource_agent_error_to_report_item(
                e, reports.ReportItemSeverity.error()
            )
        )
        raise LibraryError() from e

    if agent_name.is_stonith:
        report_processor.report(
            reports.ReportItem.error(
                reports.messages.CommandArgumentTypeMismatch(
                    "stonith resource", reports.const.PCS_COMMAND_STONITH_CREATE
                )
            )
        )
        raise LibraryError()

    return agent_name


def _get_resource_agent_facade(
    report_processor: reports.ReportProcessor,
    factory: ResourceAgentFacadeFactory,
    agent_name: ResourceAgentName,
    force_flags: reports.types.ForceFlags,
) -> ResourceAgentFacade:
    try:
        return factory.facade_from_parsed_name(agent_name)
    except (UnableToGetAgentMetadata, UnsupportedOcfVersion) as e:
        report_processor.report(
            resource_agent_error_to_report_item(
                e,
                reports.get_severity_from_flags(
                    reports.codes.FORCE, force_flags
                ),
            )
        )
        if report_processor.has_errors:
            raise LibraryError() from e
        return factory.void_facade_from_parsed_name(agent_name)


def _validate_remote_connection(
    resource_agent_name: ResourceAgentName,
    existing_nodes_addrs: StringCollection,
    resource_id: str,
    instance_attributes: Mapping[str, str],
    allow_not_suitable_command: bool,
) -> reports.ReportItemList:
    if resource_agent_name != resource.remote_node.AGENT_NAME:
        return []

    report_list = []
    report_list.append(
        ReportItem(
            severity=reports.item.get_severity(
                reports.codes.FORCE,
                allow_not_suitable_command,
            ),
            message=reports.messages.UseCommandNodeAddRemote(),
        )
    )

    report_list.extend(
        resource.remote_node.validate_host_not_conflicts(
            existing_nodes_addrs, resource_id, instance_attributes
        )
    )
    return report_list


def _validate_guest_change(
    tree: _Element,
    existing_nodes_names: StringCollection,
    existing_nodes_addrs: StringCollection,
    meta_attributes: Mapping[str, str],
    allow_not_suitable_command: bool,
    detect_remove: bool = False,
) -> reports.ReportItemList:
    if not resource.guest_node.is_node_name_in_options(meta_attributes):
        return []

    node_name = resource.guest_node.get_node_name_from_options(meta_attributes)

    report_list = []

    report_msg = (
        reports.messages.UseCommandNodeRemoveGuest()
        if (
            detect_remove
            and not resource.guest_node.get_guest_option_value(meta_attributes)
        )
        else reports.messages.UseCommandNodeAddGuest()
    )

    report_list.append(
        ReportItem(
            severity=reports.item.get_severity(
                reports.codes.FORCE,
                allow_not_suitable_command,
            ),
            message=report_msg,
        )
    )

    report_list.extend(
        resource.guest_node.validate_conflicts(
            tree,
            existing_nodes_names,
            existing_nodes_addrs,
            node_name,
            meta_attributes,
        )
    )

    return report_list


def _get_nodes_to_validate_against(
    env: LibraryEnvironment, tree: _Element
) -> Tuple[List[str], List[str], reports.ReportItemList]:
    if not env.is_corosync_conf_live and env.is_cib_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequired(
                    [file_type_codes.COROSYNC_CONF]
                )
            )
        )

    if not env.is_cib_live and env.is_corosync_conf_live:
        # we do not try to get corosync.conf from live cluster when cib is not
        # taken from live cluster
        return get_existing_nodes_names_addrs(cib=tree)

    return get_existing_nodes_names_addrs(env.get_corosync_conf(), cib=tree)


def _check_special_cases(
    env: LibraryEnvironment,
    resource_agent_name: ResourceAgentName,
    resources_section: _Element,
    resource_id: str,
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    allow_not_suitable_command: bool,
) -> None:
    if (
        resource_agent_name != resource.remote_node.AGENT_NAME
        and not resource.guest_node.is_node_name_in_options(meta_attributes)
    ):
        # if no special case happens we won't take care about corosync.conf that
        # is needed for getting nodes to validate against
        return

    (
        existing_nodes_names,
        existing_nodes_addrs,
        report_list,
    ) = _get_nodes_to_validate_against(env, resources_section)

    report_list.extend(
        _validate_remote_connection(
            resource_agent_name,
            existing_nodes_addrs,
            resource_id,
            instance_attributes,
            allow_not_suitable_command,
        )
    )
    report_list.extend(
        _validate_guest_change(
            resources_section,
            existing_nodes_names,
            existing_nodes_addrs,
            meta_attributes,
            allow_not_suitable_command,
        )
    )

    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()


def _validate_clone_meta_attributes(
    report_processor: ReportProcessor,
    agent_facade_factory: ResourceAgentFacadeFactory,
    resource_el: _Element,
    meta_attrs: Mapping[str, str],
    force_flags: reports.types.ForceFlags,
) -> None:
    clone_child_el = resource.clone.get_inner_resource(resource_el)
    if clone_child_el is None:
        return

    group_id = None
    if resource.group.is_group(clone_child_el):
        group_id = str(clone_child_el.attrib["id"])

    inner_primitives = resource.clone.get_inner_primitives(resource_el)

    facade_cache: dict[ResourceAgentName, ResourceAgentFacade] = {}
    for primitive_el in inner_primitives:
        agent_name = resource.primitive.resource_agent_name_from_primitive(
            primitive_el
        )
        if agent_name.is_ocf:
            if agent_name in facade_cache:
                agent_facade = facade_cache[agent_name]
            else:
                agent_facade = _get_resource_agent_facade(
                    report_processor,
                    agent_facade_factory,
                    agent_name,
                    force_flags,
                )
                facade_cache[agent_name] = agent_facade

            if (
                agent_facade.metadata.ocf_version == OCF_1_1
                and is_true(meta_attrs.get(resource.clone.META_PROMOTABLE, "0"))
                and not agent_facade.metadata.provides_promotability
            ):
                report_processor.report(
                    reports.ReportItem(
                        reports.get_severity_from_flags(
                            reports.codes.FORCE,
                            force_flags,
                        ),
                        reports.messages.ResourceCloneIncompatibleMetaAttributes(
                            resource.clone.META_PROMOTABLE,
                            agent_name.to_dto(),
                            resource_id=primitive_el.get("id"),
                            group_id=group_id,
                        ),
                    )
                )
        else:
            report_processor.report_list(
                [
                    reports.ReportItem.error(
                        reports.messages.ResourceCloneIncompatibleMetaAttributes(
                            incompatible_attr,
                            agent_name.to_dto(),
                            resource_id=primitive_el.get("id"),
                            group_id=group_id,
                        )
                    )
                    for incompatible_attr in [
                        resource.clone.META_GLOBALLY_UNIQUE,
                        resource.clone.META_PROMOTABLE,
                    ]
                    if is_true(meta_attrs.get(incompatible_attr, "0"))
                ]
            )


_find_bundle = partial(
    find_element_by_tag_and_id, cib_const.TAG_RESOURCE_BUNDLE
)


def _are_meta_disabled(meta_attributes: Mapping[str, str]) -> bool:
    return meta_attributes.get("target-role", "Started").lower() == "stopped"


def _can_be_evaluated_as_positive_num(value: str) -> bool:
    string_wo_leading_zeros = str(value).lstrip("0")
    return bool(string_wo_leading_zeros) and (
        string_wo_leading_zeros[0] in list("123456789")
    )


def _is_clone_deactivated_by_meta(meta_attributes: Mapping[str, str]) -> bool:
    return _are_meta_disabled(meta_attributes) or any(
        not _can_be_evaluated_as_positive_num(meta_attributes.get(key, "1"))
        for key in ["clone-max", "clone-node-max"]
    )


def create(  # noqa: PLR0913
    env: LibraryEnvironment,
    resource_id: str,
    resource_agent_name: str,
    operation_list: List[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    *,
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    wait: WaitType = False,
    allow_not_suitable_command: bool = False,
    enable_agent_self_validation: bool = False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    """
    Create a primitive resource in a cib.

    env -- provides all for communication with externals
    resource_id -- is identifier of resource
    resource_agent_name -- contains name for the identification of agent
    operation_list -- contains attributes for each entered operation
        e.g. [{"name": "monitor", "timeout": "10s"}]
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for primitive/instance_attributes
    allow_absent_agent -- is a flag for allowing agent that is not installed
        in a system
    allow_invalid_operation -- is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    use_default_operations -- is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    ensure_disabled -- is flag that keeps resource in target-role "Stopped"
    wait -- is flag for controlling waiting for pacemaker idle mechanism
    allow_not_suitable_command -- turn forceable errors into warnings
        a resource representing
        - pacemaker remote node (resource agent is ocf:pacemaker:remote)
        - or pacemaker guest node (contains meta attribute remote-node)
        should not be created by this function since the creation of such
        resource should be accompanied by further actions (see
        pcs.lib.commands.remote_node);
        in the case of remote/guest node forcible error is produced when this
        flag is set to False and warning is produced otherwise
    enable_agent_self_validation -- if True, use agent self-validation feature
        to validate instance attributes
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    runner = env.cmd_runner()
    agent_factory = ResourceAgentFacadeFactory(runner, env.report_processor)
    agent_name = _get_resource_agent_name(
        runner, env.report_processor, resource_agent_name
    )
    resource_agent = _get_resource_agent_facade(
        env.report_processor,
        agent_factory,
        agent_name,
        [reports.codes.FORCE] if allow_absent_agent else [],
    )
    with resource_environment(
        env,
        wait,
        [resource_id],
        _ensure_disabled_after_wait(
            ensure_disabled or _are_meta_disabled(meta_attributes)
        ),
        required_cib_version=get_required_cib_version_for_primitive(
            operation_list
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent.metadata.name,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command,
        )

        primitive_element = resource.primitive.create(
            env.report_processor,
            runner,
            resources_section,
            id_provider,
            resource_id,
            resource_agent,
            operation_list,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
            enable_agent_self_validation=enable_agent_self_validation,
        )
        if env.report_processor.has_errors:
            raise LibraryError()

        if ensure_disabled:
            resource.common.disable(primitive_element, id_provider)


def create_as_clone(  # noqa: PLR0913
    env: LibraryEnvironment,
    resource_id: str,
    resource_agent_name: str,
    operation_list: List[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    clone_meta_options: Mapping[str, str],
    *,
    clone_id: Optional[str] = None,
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    wait: WaitType = False,
    allow_not_suitable_command: bool = False,
    allow_incompatible_clone_meta_attributes: bool = False,
    enable_agent_self_validation: bool = False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    """
    Create a primitive resource in a clone

    env -- provides all for communication with externals
    resource_id -- is identifier of resource
    resource_agent_name -- contains name for the identification of agent
    operation_list -- contains attributes for each entered operation
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for primitive/instance_attributes
    clone_meta_options -- contains attributes for clone/meta_attributes
    clone_id -- optional custom clone id, if not set then clone id is generated
        from primitive resource or group id
    allow_absent_agent -- is a flag for allowing agent that is not installed
        in a system
    allow_invalid_operation -- is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    use_default_operations -- is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    ensure_disabled -- is flag that keeps resource in target-role "Stopped"
    wait -- is flag for controlling waiting for pacemaker idle mechanism
    allow_not_suitable_command -- turn forceable errors into warnings
    allow_incompatible_clone_meta_attributes -- if True some incompatible clone
        meta attributes are treated as a warning, or as a forceable error if
        False
    enable_agent_self_validation -- if True, use agent self-validation feature
        to validate instance attributes
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    runner = env.cmd_runner()
    agent_factory = ResourceAgentFacadeFactory(runner, env.report_processor)
    agent_name = _get_resource_agent_name(
        runner, env.report_processor, resource_agent_name
    )
    resource_agent = _get_resource_agent_facade(
        env.report_processor,
        agent_factory,
        agent_name,
        [reports.codes.FORCE] if allow_absent_agent else [],
    )
    if resource_agent.metadata.name.standard != "ocf":
        for incompatible_attr in ("globally-unique", "promotable"):
            if is_true(clone_meta_options.get(incompatible_attr, "0")):
                env.report_processor.report(
                    reports.ReportItem.error(
                        reports.messages.ResourceCloneIncompatibleMetaAttributes(
                            incompatible_attr,
                            resource_agent.metadata.name.to_dto(),
                        )
                    )
                )
    elif resource_agent.metadata.ocf_version == "1.1" and (
        is_true(clone_meta_options.get("promotable", "0"))
        and not resource_agent.metadata.provides_promotability
    ):
        env.report_processor.report(
            reports.ReportItem(
                reports.get_severity(
                    reports.codes.FORCE,
                    allow_incompatible_clone_meta_attributes,
                ),
                reports.messages.ResourceCloneIncompatibleMetaAttributes(
                    "promotable",
                    resource_agent.metadata.name.to_dto(),
                ),
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    with resource_environment(
        env,
        wait,
        [resource_id],
        _ensure_disabled_after_wait(
            ensure_disabled
            or _are_meta_disabled(meta_attributes)
            or _is_clone_deactivated_by_meta(clone_meta_options)
        ),
        required_cib_version=get_required_cib_version_for_primitive(
            operation_list
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent.metadata.name,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command,
        )
        if clone_id is not None:
            env.report_processor.report_list(
                resource.clone.validate_clone_id(clone_id, id_provider),
            )
        if env.report_processor.has_errors:
            raise LibraryError()

        primitive_element = resource.primitive.create(
            env.report_processor,
            runner,
            resources_section,
            id_provider,
            resource_id,
            resource_agent,
            operation_list,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
            enable_agent_self_validation=enable_agent_self_validation,
        )

        clone_element = resource.clone.append_new(
            resources_section,
            id_provider,
            primitive_element,
            clone_meta_options,
            clone_id=clone_id,
        )
        if ensure_disabled:
            resource.common.disable(clone_element, id_provider)


def create_in_group(  # noqa: PLR0913
    env: LibraryEnvironment,
    resource_id: str,
    resource_agent_name: str,
    group_id: str,
    operation_list: List[Mapping[str, str]],
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
    allow_not_suitable_command: bool = False,
    enable_agent_self_validation: bool = False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    """
    Create resource in a cib and put it into defined group

    env -- provides all for communication with externals
    resource_id -- is identifier of resource
    resource_agent_name -- contains name for the identification of agent
    group_id -- is identificator for group to put primitive resource inside
    operation_list -- contains attributes for each entered operation
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for primitive/instance_attributes
    allow_absent_agent -- is a flag for allowing agent that is not installed
        in a system
    allow_invalid_operation -- is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    use_default_operations -- is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    ensure_disabled -- is flag that keeps resource in target-role "Stopped"
    adjacent_resource_id -- identify neighbor of a newly created resource
    put_after_adjacent -- is flag to put a newly create resource befor/after
        adjacent resource
    wait -- is flag for controlling waiting for pacemaker idle mechanism
    allow_not_suitable_command -- turn forceable errors into warnings
    enable_agent_self_validation -- if True, use agent self-validation feature
        to validate instance attributes
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    runner = env.cmd_runner()
    agent_factory = ResourceAgentFacadeFactory(runner, env.report_processor)
    agent_name = _get_resource_agent_name(
        runner, env.report_processor, resource_agent_name
    )
    resource_agent = _get_resource_agent_facade(
        env.report_processor,
        agent_factory,
        agent_name,
        [reports.codes.FORCE] if allow_absent_agent else [],
    )
    with resource_environment(
        env,
        wait,
        [resource_id],
        _ensure_disabled_after_wait(
            ensure_disabled or _are_meta_disabled(meta_attributes)
        ),
        required_cib_version=get_required_cib_version_for_primitive(
            operation_list
        ),
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent.metadata.name,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command,
        )

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

        primitive_element = resource.primitive.create(
            env.report_processor,
            runner,
            resources_section,
            id_provider,
            resource_id,
            resource_agent,
            operation_list,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
            enable_agent_self_validation=enable_agent_self_validation,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element, id_provider)

        if env.report_processor.report_list(
            resource.validations.validate_move_resources_to_group(
                group_element,
                [primitive_element],
                adjacent_resource_element,
            )
        ).has_errors:
            raise LibraryError()

        resource.hierarchy.move_resources_to_group(
            group_element,
            [primitive_element],
            adjacent_resource_element,
            put_after_adjacent,
        )


def create_into_bundle(  # noqa: PLR0913
    env: LibraryEnvironment,
    resource_id: str,
    resource_agent_name: str,
    operation_list: List[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    bundle_id: str,
    *,
    allow_absent_agent: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    ensure_disabled: bool = False,
    wait: WaitType = False,
    allow_not_suitable_command: bool = False,
    allow_not_accessible_resource: bool = False,
    enable_agent_self_validation: bool = False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-locals
    """
    Create a new resource in a cib and put it into an existing bundle

    env -- provides all for communication with externals
    resource_id -- is identifier of resource
    resource_agent_name -- contains name for the identification of agent
    operation_list -- contains attributes for each entered operation
    meta_attributes -- contains attributes for primitive/meta_attributes
    instance_attributes -- contains attributes for
        primitive/instance_attributes
    bundle_id -- is id of an existing bundle to put the created resource in
    allow_absent_agent -- is a flag for allowing agent that is not installed
        in a system
    allow_invalid_operation -- is a flag for allowing to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- is a flag for allowing to use
        instance attributes that are not listed in a resource agent metadata
        or for allowing to not use the instance_attributes that are required in
        resource agent metadata
    use_default_operations -- is a flag for stopping stopping of adding
        default cib operations (specified in a resource agent)
    ensure_disabled -- is flag that keeps resource in target-role "Stopped"
    wait -- is flag for controlling waiting for pacemaker idle mechanism
    allow_not_suitable_command -- turn forceable errors into warnings
    allow_not_accessible_resource -- turn forceable errors into warnings
    enable_agent_self_validation -- if True, use agent self-validation feature
        to validate instance attributes
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    runner = env.cmd_runner()
    agent_factory = ResourceAgentFacadeFactory(runner, env.report_processor)
    agent_name = _get_resource_agent_name(
        runner, env.report_processor, resource_agent_name
    )
    resource_agent = _get_resource_agent_facade(
        env.report_processor,
        agent_factory,
        agent_name,
        [reports.codes.FORCE] if allow_absent_agent else [],
    )
    required_cib_version = get_required_cib_version_for_primitive(
        operation_list
    )
    with resource_environment(
        env,
        wait,
        [resource_id],
        _ensure_disabled_after_wait(
            ensure_disabled or _are_meta_disabled(meta_attributes)
        ),
        required_cib_version=required_cib_version,
    ) as resources_section:
        id_provider = IdProvider(resources_section)
        _check_special_cases(
            env,
            resource_agent.metadata.name,
            resources_section,
            resource_id,
            meta_attributes,
            instance_attributes,
            allow_not_suitable_command,
        )

        primitive_element = resource.primitive.create(
            env.report_processor,
            runner,
            resources_section,
            id_provider,
            resource_id,
            resource_agent,
            operation_list,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
            enable_agent_self_validation=enable_agent_self_validation,
        )
        if ensure_disabled:
            resource.common.disable(primitive_element, id_provider)

        bundle_el = _find_bundle(resources_section, bundle_id)
        if not resource.bundle.is_pcmk_remote_accessible(bundle_el):
            env.report_processor.report(
                ReportItem(
                    severity=reports.item.get_severity(
                        reports.codes.FORCE,
                        allow_not_accessible_resource,
                    ),
                    message=reports.messages.ResourceInBundleNotAccessible(
                        bundle_id,
                        resource_id,
                    ),
                )
            )
        if env.report_processor.has_errors:
            raise LibraryError()
        resource.bundle.add_resource(bundle_el, primitive_element)


def bundle_create(  # noqa: PLR0913
    env,
    bundle_id,
    container_type,
    *,
    container_options=None,
    network_options=None,
    port_map=None,
    storage_map=None,
    meta_attributes=None,
    force_options=False,
    ensure_disabled=False,
    wait=False,
):
    # pylint: disable=too-many-arguments
    """
    Create a new bundle containing no resources

    LibraryEnvironment env -- provides communication with externals
    string bundle_id -- id of the new bundle
    string container_type -- container engine name (docker, lxc...)
    dict container_options -- container options
    dict network_options -- network options
    list of dict port_map -- a list of port mapping options
    list of dict storage_map -- a list of storage mapping options
    dict meta_attributes -- bundle's meta attributes
    bool force_options -- return warnings instead of forceable errors
    bool ensure_disabled -- set the bundle's target-role to "Stopped"
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    container_options = container_options or {}
    network_options = network_options or {}
    port_map = port_map or []
    storage_map = storage_map or []
    meta_attributes = meta_attributes or {}

    with resource_environment(
        env,
        wait,
        [bundle_id],
        _ensure_disabled_after_wait(
            ensure_disabled or _are_meta_disabled(meta_attributes)
        ),
        required_cib_version=(
            Version(3, 2, 0) if container_type == "podman" else None
        ),
    ) as resources_section:
        # no need to run validations related to remote and guest nodes as those
        # nodes can only be created from primitive resources
        id_provider = IdProvider(resources_section)
        if env.report_processor.report_list(
            resource.bundle.validate_new(
                id_provider,
                bundle_id,
                container_type,
                container_options,
                network_options,
                port_map,
                storage_map,
                # TODO meta attributes - there is no validation for now
                force_options,
            )
        ).has_errors:
            raise LibraryError()
        bundle_element = resource.bundle.append_new(
            resources_section,
            id_provider,
            bundle_id,
            container_type,
            container_options,
            network_options,
            port_map,
            storage_map,
            meta_attributes,
        )
        if ensure_disabled:
            resource.common.disable(bundle_element, id_provider)


def bundle_reset(  # noqa: PLR0913
    env,
    bundle_id,
    *,
    container_options=None,
    network_options=None,
    port_map=None,
    storage_map=None,
    meta_attributes=None,
    force_options=False,
    ensure_disabled=False,
    wait=False,
):
    # pylint: disable=too-many-arguments
    """
    Remove configuration of bundle bundle_id and create new one into it.

    LibraryEnvironment env -- provides communication with externals
    string bundle_id -- id of the bundle to reset
    dict container_options -- container options
    dict network_options -- network options
    list of dict port_map -- a list of port mapping options
    list of dict storage_map -- a list of storage mapping options
    dict meta_attributes -- bundle's meta attributes
    bool force_options -- return warnings instead of forceable errors
    bool ensure_disabled -- set the bundle's target-role to "Stopped"
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    container_options = container_options or {}
    network_options = network_options or {}
    port_map = port_map or []
    storage_map = storage_map or []
    meta_attributes = meta_attributes or {}

    with resource_environment(
        env,
        wait,
        [bundle_id],
        _ensure_disabled_after_wait(
            ensure_disabled or _are_meta_disabled(meta_attributes)
        ),
        # The only requirement for CIB schema version currently is:
        #   if container_type == "podman" then required_version = '3.2.0'
        # Since bundle_reset command doesn't change container type, there is no
        # need to check and upgrade CIB schema version.
    ) as resources_section:
        bundle_element = _find_bundle(resources_section, bundle_id)
        if env.report_processor.report_list(
            resource.bundle.validate_reset_to_minimal(bundle_element)
        ).has_errors:
            raise LibraryError()
        resource.bundle.reset_to_minimal(bundle_element)

        id_provider = IdProvider(resources_section)
        if env.report_processor.report_list(
            resource.bundle.validate_reset(
                id_provider,
                bundle_element,
                container_options,
                network_options,
                port_map,
                storage_map,
                # TODO meta attributes - there is no validation for now
                force_options,
            )
        ).has_errors:
            raise LibraryError()

        resource.bundle.update(
            id_provider,
            bundle_element,
            container_options,
            network_options,
            port_map_add=port_map,
            port_map_remove=[],
            storage_map_add=storage_map,
            storage_map_remove=[],
            meta_attributes=meta_attributes,
        )

        if ensure_disabled:
            resource.common.disable(bundle_element, id_provider)


def bundle_update(  # noqa: PLR0913
    env,
    bundle_id,
    *,
    container_options=None,
    network_options=None,
    port_map_add=None,
    port_map_remove=None,
    storage_map_add=None,
    storage_map_remove=None,
    meta_attributes=None,
    force_options=False,
    wait=False,
):
    # pylint: disable=too-many-arguments
    """
    Modify an existing bundle (does not touch encapsulated resources)

    LibraryEnvironment env -- provides communication with externals
    string bundle_id -- id of the bundle to modify
    dict container_options -- container options to modify
    dict network_options -- network options to modify
    list of dict port_map_add -- list of port mapping options to add
    list of string port_map_remove -- list of port mapping ids to remove
    list of dict storage_map_add -- list of storage mapping options to add
    list of string storage_map_remove -- list of storage mapping ids to remove
    dict meta_attributes -- meta attributes to update
    bool force_options -- return warnings instead of forceable errors
    mixed wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    container_options = container_options or {}
    network_options = network_options or {}
    port_map_add = port_map_add or []
    port_map_remove = port_map_remove or []
    storage_map_add = storage_map_add or []
    storage_map_remove = storage_map_remove or []
    meta_attributes = meta_attributes or {}

    # The only requirement for CIB schema version currently is:
    #   if container_type == "podman" then required_version = '3.2.0'
    # Since bundle_update command doesn't change container type, there is no
    # need to check and upgrade CIB schema version.
    with resource_environment(env, wait, [bundle_id]) as resources_section:
        # no need to run validations related to remote and guest nodes as those
        # nodes can only be created from primitive resources
        id_provider = IdProvider(resources_section)
        bundle_element = _find_bundle(resources_section, bundle_id)
        if env.report_processor.report_list(
            resource.bundle.validate_update(
                id_provider,
                bundle_element,
                container_options,
                network_options,
                port_map_add,
                port_map_remove,
                storage_map_add,
                storage_map_remove,
                # TODO meta attributes - there is no validation for now
                force_options,
            )
        ).has_errors:
            raise LibraryError()
        resource.bundle.update(
            id_provider,
            bundle_element,
            container_options,
            network_options,
            port_map_add,
            port_map_remove,
            storage_map_add,
            storage_map_remove,
            meta_attributes,
        )


def _disable_get_element_ids(
    disabled_resource_el_list: Iterable[_Element],
) -> Tuple[Set[str], Set[str]]:
    """
    Turn a list of elements asked by a user to be disabled to a list of their
    IDs and a list of IDs of their inner elements. Remember, the user can
    specify tags instead of resources. Therefore the list of disabled
    resources' IDs returned by this function may be different than the list of
    IDs entered in the command.
    """
    inner_resource_id_set = set()
    disabled_resource_id_set = set()
    for resource_el in disabled_resource_el_list:
        disabled_resource_id_set.add(cast(Optional[str], resource_el.get("id")))
        inner_resource_id_set.update(
            {
                cast(Optional[str], inner_resource_el.get("id"))
                for inner_resource_el in resource.common.get_all_inner_resources(
                    resource_el
                )
            }
        )
    # Make sure we only return found IDs and not None to match the function's
    # return type annotation.
    return (
        set(filter(None, disabled_resource_id_set)),
        set(filter(None, inner_resource_id_set)),
    )


def _disable_run_simulate(
    cmd_runner: CommandRunner,
    cib: _Element,
    disabled_resource_ids: Set[str],
    inner_resource_ids: Set[str],
    strict: bool,
) -> Tuple[str, Set[str]]:
    plaintext_status, transitions, dummy_cib = simulate_cib(cmd_runner, cib)
    simulated_operations = simulate_tools.get_operations_from_transitions(
        transitions
    )
    other_affected: Set[str] = set()
    if strict:
        other_affected = set(
            simulate_tools.get_resources_from_operations(
                simulated_operations, exclude_resources=disabled_resource_ids
            )
        )
    else:
        other_affected = set(
            simulate_tools.get_resources_left_stopped(
                simulated_operations, exclude_resources=disabled_resource_ids
            )
            + simulate_tools.get_resources_left_demoted(
                simulated_operations, exclude_resources=disabled_resource_ids
            )
        )

    # Stopping a clone stops all its inner resources. That should not block
    # stopping the clone.
    other_affected = other_affected - inner_resource_ids
    return plaintext_status, other_affected


def disable(
    env: LibraryEnvironment,
    resource_or_tag_ids: StringCollection,
    wait: WaitType = False,
    force_flags: reports.types.ForceFlags = (),
):
    """
    Disallow specified resources to be started by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become disabled, or in case
        of tag ids, all resources in tags are to be disabled
    wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    wait_timeout = env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()
    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids
    )
    env.report_processor.report_list(report_list)

    if any(
        resource.stonith.is_stonith(resource_el)
        for resource_el in resource_el_list
    ):
        env.report_processor.report_list(
            ensure_some_stonith_remains(
                env,
                get_resources(cib),
                [str(res.attrib["id"]) for res in resource_el_list],
                sbd_being_disabled=False,
                force_flags=force_flags,
            )
        )

    # Validation done, do the disabling. Do not mind errors that happened so
    # far. The disabling may report errors on its own and we want the user to
    # see those. In case of errors, we exit before pushing CIB, not making any
    # change to cluster configuration.
    env.report_processor.report_list(
        _resource_list_enable_disable(
            resource_el_list,
            resource.common.disable,
            IdProvider(cib),
            env.get_cluster_state(),
        )
    )

    if env.report_processor.has_errors:
        raise LibraryError()

    _push_cib_wait(
        env,
        wait_timeout,
        resource_or_tag_ids,
        _ensure_disabled_after_wait(True),
    )


def disable_safe(
    env: LibraryEnvironment,
    resource_or_tag_ids: List[str],
    strict: bool,
    wait: WaitType = False,
):
    """
    Disallow specified resources to be started by the cluster only if there is
    no effect on other resources

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become disabled, or in case
        of tag ids, all resources in tags are to be disabled
    strict -- if False, allow resources to be migrated
    wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    if not env.is_cib_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequired([file_type_codes.CIB])
            )
        )

    wait_timeout = env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()
    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids
    )
    env.report_processor.report_list(report_list)

    if any(
        resource.stonith.is_stonith(resource_el)
        for resource_el in resource_el_list
    ):
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.CommandArgumentTypeMismatch(
                    "stonith resources"
                )
            )
        )

    # Validation done, do the disabling. Do not mind errors that happened so
    # far. The disabling may report errors on its own and we want the user to
    # see those. In case of errors, we exit before pushing CIB, not making any
    # change to cluster configuration.
    env.report_processor.report_list(
        _resource_list_enable_disable(
            resource_el_list,
            resource.common.disable,
            IdProvider(cib),
            env.get_cluster_state(),
        )
    )
    if env.report_processor.has_errors:
        raise LibraryError()

    disabled_resource_id_set, inner_resource_id_set = _disable_get_element_ids(
        resource_el_list
    )
    plaintext_status, other_affected = _disable_run_simulate(
        env.cmd_runner(),
        cib,
        disabled_resource_id_set,
        inner_resource_id_set,
        strict,
    )
    if other_affected:
        env.report_processor.report_list(
            [
                ReportItem.error(
                    reports.messages.ResourceDisableAffectsOtherResources(
                        sorted(disabled_resource_id_set),
                        sorted(other_affected),
                    ),
                ),
                ReportItem.info(
                    reports.messages.PacemakerSimulationResult(
                        plaintext_status,
                    ),
                ),
            ]
        )

        if env.report_processor.has_errors:
            raise LibraryError()

    _push_cib_wait(
        env,
        wait_timeout,
        disabled_resource_id_set,
        _ensure_disabled_after_wait(True),
    )


def disable_simulate(
    env: LibraryEnvironment, resource_or_tag_ids: List[str], strict: bool
) -> Mapping[str, Union[str, List[str]]]:
    """
    Simulate disallowing specified resources to be started by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become disabled, or in case
        of tag ids, all resources in tags are to be disabled
    bool strict -- if False, allow resources to be migrated
    """
    if not env.is_cib_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequired([file_type_codes.CIB])
            )
        )

    cib = env.get_cib()
    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids
    )
    env.report_processor.report_list(report_list)

    # Validation done, do the disabling. Do not mind errors that happened so
    # far. The disabling may report errors on its own and we want the user to
    # see those. In case of errors, we exit before pushing CIB, not making any
    # change to cluster configuration.
    env.report_processor.report_list(
        _resource_list_enable_disable(
            resource_el_list,
            resource.common.disable,
            IdProvider(cib),
            env.get_cluster_state(),
        )
    )

    if env.report_processor.has_errors:
        raise LibraryError()

    disabled_resource_id_set, inner_resource_id_set = _disable_get_element_ids(
        resource_el_list
    )
    plaintext_status, other_affected = _disable_run_simulate(
        env.cmd_runner(),
        cib,
        disabled_resource_id_set,
        inner_resource_id_set,
        strict,
    )
    return dict(
        plaintext_simulated_status=plaintext_status,
        other_affected_resource_list=sorted(other_affected),
    )


def enable(
    env: LibraryEnvironment,
    resource_or_tag_ids: List[str],
    wait: WaitType = False,
):
    """
    Allow specified resources to be started by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become enabled, or in case
        of tag ids, all resources in tags are to be enabled
    wait -- False: no wait, None: wait default timeout, int: wait timeout
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    wait_timeout = env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()
    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids
    )
    env.report_processor.report_list(report_list)

    to_enable_set = set()
    for el in resource_el_list:
        to_enable_set.update(resource.common.find_resources_to_enable(el))

    if env.report_processor.report_list(
        _resource_list_enable_disable(
            to_enable_set,
            resource.common.enable,
            IdProvider(cib),
            env.get_cluster_state(),
        )
    ).has_errors:
        raise LibraryError()
    _push_cib_wait(
        env,
        wait_timeout,
        [str(el.get("id", "")) for el in resource_el_list],
        _ensure_disabled_after_wait(False),
    )


def _resource_list_enable_disable(
    resource_el_list: Iterable[_Element],
    func: Callable[[_Element, IdProvider], None],
    id_provider: IdProvider,
    cluster_state,
) -> ReportItemList:
    report_list = []
    for resource_el in resource_el_list:
        res_id = str(resource_el.attrib["id"])
        try:
            if not is_resource_managed(cluster_state, res_id):
                report_list.append(
                    ReportItem.warning(
                        reports.messages.ResourceIsUnmanaged(res_id)
                    )
                )
            func(resource_el, id_provider)
        except ResourceNotFound:
            report_list.append(
                ReportItem.error(
                    reports.messages.IdNotFound(
                        res_id,
                        ["bundle", "clone", "group", "master", "primitive"],
                    )
                )
            )
    return report_list


def unmanage(
    env: LibraryEnvironment,
    resource_or_tag_ids: List[str],
    with_monitor: bool = False,
) -> None:
    """
    Set specified resources not to be managed by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become unmanaged, or in case
        of tag ids, all resources in tags are to be managed
    with_monitor -- disable resources' monitor operations
    """
    cib = env.get_cib()
    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids, resource.common.find_resources_to_unmanage
    )
    env.report_processor.report_list(report_list)
    if env.report_processor.has_errors:
        raise LibraryError()

    primitives_set = set()
    for resource_el in resource_el_list:
        resource.common.unmanage(resource_el, IdProvider(cib))
        if with_monitor:
            primitives_set.update(resource.common.find_primitives(resource_el))

    for resource_el in primitives_set:
        for op in resource.operations.get_resource_operations(
            resource_el, ["monitor"]
        ):
            resource.operations.disable(op)
    env.push_cib()


def manage(
    env: LibraryEnvironment,
    resource_or_tag_ids: List[str],
    with_monitor: bool = False,
) -> None:
    """
    Set specified resources to be managed by the cluster

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become managed, or in case
        of tag id, all resources in tag are to be managed
    with_monitor -- enable resources' monitor operations
    """
    cib = env.get_cib()

    resource_el_list, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids
    )
    resource_el_to_manage_list = set()
    for el in resource_el_list:
        resource_el_to_manage_list.update(
            resource.common.find_resources_to_manage(el)
        )

    # manage all resources that need to be managed in order for the user
    # specified resource to become managed
    for resource_el in resource_el_to_manage_list:
        resource.common.manage(resource_el, IdProvider(cib))
        if with_monitor and resource.primitive.is_primitive(resource_el):
            for op in resource.operations.get_resource_operations(
                resource_el, ["monitor"]
            ):
                resource.operations.enable(op)

    # only report disabled monitor operations for user specified resources and
    # their primitives
    for resource_el in sorted(
        resource_el_list, key=lambda element: element.get("id", "")
    ):
        for primitive_el in resource.common.find_primitives(resource_el):
            op_list = resource.operations.get_resource_operations(
                primitive_el, ["monitor"]
            )
            monitor_enabled = False
            for op in op_list:
                if resource.operations.is_enabled(op):
                    monitor_enabled = True
                    break
            if op_list and not monitor_enabled:
                # do not advise enabling monitors if there are none defined
                report_list.append(
                    ReportItem.warning(
                        reports.messages.ResourceManagedNoMonitorEnabled(
                            str(primitive_el.get("id", ""))
                        )
                    )
                )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    env.push_cib()


def group_add(  # noqa: PLR0912
    env: LibraryEnvironment,
    group_id: str,
    resource_id_list: List[str],
    adjacent_resource_id: Optional[str] = None,
    put_after_adjacent: bool = True,
    wait: WaitType = False,
):
    """
    Move specified resources into an existing or new group

    LibraryEnvironment env provides all for communication with externals
    string group_id -- id of the target group
    iterable resource_id_list -- ids of resources to put into the group
    string adjacent_resource_id -- put resources beside this one if specified
    bool put_after_adjacent -- put resources after or before the adjacent one
    mixed wait -- flag for controlling waiting for pacemaker idle mechanism
    """
    # pylint: disable = too-many-locals
    # pylint: disable = too-many-branches

    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    wait_timeout = env.ensure_wait_satisfiable(wait)
    resources_section = get_resources(env.get_cib(None))

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
        group_element = get_element_by_id(get_root(resources_section), group_id)
    except ElementNotFound:
        group_id_reports: List[ReportItem] = []
        validate_id(
            group_id, description="group name", reporter=group_id_reports
        )
        env.report_processor.report_list(group_id_reports)
        group_element = resource.group.append_new(resources_section, group_id)

    (
        resource_element_list,
        id_not_found_list,
    ) = get_elements_by_ids(get_root(resources_section), resource_id_list)
    for resource_id in id_not_found_list:
        env.report_processor.report(
            ReportItem.error(reports.messages.IdNotFound(resource_id, []))
        )

    if env.report_processor.report_list(
        resource.validations.validate_move_resources_to_group(
            group_element,
            resource_element_list,
            adjacent_resource_element,
        )
    ).has_errors:
        raise LibraryError()

    # Check that elements to move won't leave their group empty. In that case,
    # the group must be removed. Current lib implementation doesn't check
    # for references to the removed group and may produce invalid CIB. For the
    # time being, this is caught and produces an error that asks the user
    # to run ungroup first which is implemented in old code and cleans up
    # references (like constraints) to the old group in CIB. For backwards
    # compatibility, we only show this error if the CIB push is unsuccessful.
    empty_group_report_list = []

    # Group discovery step: create a dict of sets with all resources of affected
    # groups
    all_resources = {}
    for resource_element in resource_element_list:
        old_parent = resource.common.get_parent_resource(resource_element)
        if (
            old_parent is not None
            and resource.group.is_group(old_parent)
            and str(old_parent.attrib["id"]) not in all_resources
        ):
            all_resources[str(old_parent.attrib["id"])] = {
                str(res.attrib["id"])
                for res in resource.common.get_inner_resources(old_parent)
            }
    affected_resources = set(resource_id_list)

    # Set comparison step to determine if groups will be emptied by move
    for old_parent_id, inner_resource_ids in all_resources.items():
        if inner_resource_ids <= affected_resources:
            empty_group_report_list.append(
                ReportItem.error(
                    reports.messages.CannotLeaveGroupEmptyAfterMove(
                        old_parent_id, list(inner_resource_ids)
                    )
                )
            )

    resource.hierarchy.move_resources_to_group(
        group_element,
        resource_element_list,
        adjacent_resource=adjacent_resource_element,
        put_after_adjacent=put_after_adjacent,
    )

    # We only want to show error about emptying groups if CIB push fails
    try:
        env.push_cib(wait_timeout=wait_timeout)
    except LibraryError as e:
        try:
            if e.args and any(
                isinstance(report.message, reports.messages.CibPushError)
                for report in e.args
            ):
                env.report_processor.report_list(empty_group_report_list)
                if env.report_processor.has_errors:
                    raise LibraryError() from None
        except AttributeError:
            # For accessing message inside something that's not a report
            pass
        raise
    _get_resource_state_wait(env, wait_timeout, [group_id], info_resource_state)


def get_failcounts(
    env, resource=None, node=None, operation=None, interval=None
):
    # pylint: disable=redefined-outer-name
    """
    List resources failcounts, optionally filtered by a resource, node or op

    LibraryEnvironment env
    string resource -- show failcounts for the specified resource only
    string node -- show failcounts for the specified node only
    string operation -- show failcounts for the specified operation only
    string interval -- show failcounts for the specified operation interval only
    """
    report_items = []
    if interval is not None and operation is None:
        report_items.append(
            ReportItem.error(
                reports.messages.PrerequisiteOptionIsMissing(
                    "interval", "operation"
                )
            )
        )
    if interval is not None:
        report_items.extend(
            ValueTimeInterval("interval").validate({"interval": interval})
        )
    if report_items:
        raise LibraryError(*report_items)

    interval_ms = (
        None if interval is None else timeout_to_seconds(interval) * 1000
    )

    all_failcounts = cib_status.get_resources_failcounts(
        get_status(env.get_cib())
    )
    return cib_status.filter_resources_failcounts(
        all_failcounts,
        resource=resource,
        node=node,
        operation=operation,
        interval=interval_ms,
    )


def move(
    env: LibraryEnvironment,
    resource_id: str,
    node: Optional[str] = None,
    master: bool = False,
    lifetime: Optional[str] = None,
    wait: WaitType = False,
) -> None:
    """
    Create a constraint to move a resource

    LibraryEnvironment env
    resource_id -- id of a resource to be moved
    node -- node to move the resource to, ban on the current node if None
    master -- limit the constraint to the Promoted role
    lifetime -- lifespan of the constraint, forever if None
    wait -- flag for controlling waiting for pacemaker idle mechanism
    """
    return _Move().run(
        env,
        resource_id,
        node=node,
        promoted=master,
        lifetime=lifetime,
        wait=wait,
    )


def _nodes_exist_reports(
    cib: _Element, node_names: StringCollection
) -> ReportItemList:
    existing_node_names = get_pacemaker_node_names(cib)
    return [
        reports.ReportItem.error(reports.messages.NodeNotFound(node_name))
        for node_name in (set(node_names) - existing_node_names)
    ]


class ResourceMoveAutocleanSimulationFailure(Exception):
    def __init__(self, other_resources_affected: bool):
        super().__init__()
        self._other_resources_affected = other_resources_affected

    @property
    def other_resources_affected(self) -> bool:
        return self._other_resources_affected


def move_autoclean(  # noqa: PLR0912, PLR0915
    env: LibraryEnvironment,
    resource_id: str,
    node: Optional[str] = None,
    master: bool = False,
    wait_timeout: int = 0,
    strict: bool = False,
) -> None:
    """
    Create a constraint to move a resource and afterward delete the constraint
    once resource is running on its new location. Command will fail if deletion
    of the constraint will cause the resource to move from its new location.

    resource_id -- id of a resource to be moved
    node -- node to move the resource to, ban on the current node if None
    master -- limit the constraint to the Promoted role
    wait_timeout -- timeout when waiting for the cluster to apply new
        configuration, if <= 0 wait indefinitely
    strict -- if True affecting other resources than the specified resource
        will cause failure. If False affecting other resources is allowed.
    """
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    wait_timeout = max(wait_timeout, 0)
    if not env.is_cib_live:
        raise LibraryError(
            ReportItem.error(
                reports.messages.LiveEnvironmentRequired([file_type_codes.CIB])
            )
        )
    cib = env.get_cib()
    cib_xml = etree_to_str(cib)
    resource_el, report_list = resource.common.find_one_resource(
        get_resources(cib), resource_id
    )
    if resource_el is not None:
        report_list.extend(
            resource.validations.validate_move(resource_el, master)
        )

    if node:
        report_list.extend(_nodes_exist_reports(cib, [node]))

    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    cluster_state = env.get_cluster_state()
    resource_state_before = get_resource_state(cluster_state, resource_id)
    if not is_resource_managed(cluster_state, resource_id):
        raise LibraryError(
            ReportItem.error(reports.messages.ResourceIsUnmanaged(resource_id))
        )
    if not _resource_running_on_nodes(resource_state_before):
        raise LibraryError(
            ReportItem.error(
                reports.messages.CannotMoveResourceNotRunning(resource_id)
            )
        )

    # add a move constraint to a temporary cib and get a cib diff which adds
    # the move constraint
    with get_tmp_cib(env.report_processor, cib_xml) as rsc_moved_cib_file:
        stdout, stderr, retval = resource_move(
            env.cmd_runner(dict(CIB_file=rsc_moved_cib_file.name)),
            resource_id,
            node=node,
            promoted=master,
        )
        rsc_moved_cib_file.seek(0)
        rsc_moved_cib_xml = rsc_moved_cib_file.read()

    if retval != 0:
        raise LibraryError(
            _move_ban_pcmk_error_report(
                resource_id, stdout, stderr, is_ban=False
            )
        )
    add_constraint_cib_diff = diff_cibs_xml(
        env.cmd_runner(), env.report_processor, cib_xml, rsc_moved_cib_xml
    )

    # clear the move constraint from the temporary cib and get a cib diff which
    # removes the move constraint
    with get_tmp_cib(
        env.report_processor, rsc_moved_cib_xml
    ) as rsc_moved_constraint_cleared_cib_file:
        stdout, stderr, retval = resource_unmove_unban(
            env.cmd_runner(
                dict(CIB_file=rsc_moved_constraint_cleared_cib_file.name)
            ),
            resource_id,
            node,
            master,
        )
        if retval != 0:
            raise LibraryError(
                ReportItem.error(
                    reports.messages.ResourceUnmoveUnbanPcmkError(
                        resource_id, stdout, stderr
                    )
                )
            )
        rsc_moved_constraint_cleared_cib_file.seek(0)
        constraint_removed_cib = rsc_moved_constraint_cleared_cib_file.read()
    remove_constraint_cib_diff = diff_cibs_xml(
        env.cmd_runner(),
        env.report_processor,
        rsc_moved_cib_xml,
        constraint_removed_cib,
    )

    # if both the diffs are no-op, nothing needs to be done
    if not (add_constraint_cib_diff and remove_constraint_cib_diff):
        env.report_processor.report(
            reports.ReportItem.info(reports.messages.NoActionNecessary())
        )
        return

    # simulate applying the diff which adds the move constraint
    _, move_transitions, after_move_simulated_cib = simulate_cib(
        env.cmd_runner(), get_cib(rsc_moved_cib_xml)
    )
    if strict:
        # check if other resources would be affected
        resources_affected_by_move = (
            simulate_tools.get_resources_from_operations(
                simulate_tools.get_operations_from_transitions(
                    move_transitions
                ),
                exclude_resources={resource_id},
            )
        )
        if resources_affected_by_move:
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.ResourceMoveAffectsOtherResources(
                        resource_id, resources_affected_by_move
                    )
                )
            )
    # verify that:
    # - a cib with added move constraint causes the resource to move by
    #   comparing the original status of the resource with a status computed
    #   from the cib with the added constraint
    # - applying the diff which removes the move constraint won't trigger
    #   moving the resource (or other resources) around
    try:
        _ensure_resource_moved_and_not_moved_back(
            env.cmd_runner,
            env.report_processor,
            etree_to_str(after_move_simulated_cib),
            remove_constraint_cib_diff,
            resource_id,
            strict,
            resource_state_before,
            node,
        )
    except ResourceMoveAutocleanSimulationFailure as e:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.ResourceMoveAutocleanSimulationFailure(
                    resource_id,
                    e.other_resources_affected,
                    node=node,
                    move_constraint_left_in_cib=False,
                )
            )
        ) from e

    # apply the diff which adds the move constraint to the live cib and wait
    # for the cluster to settle
    push_cib_diff_xml(env.cmd_runner(), add_constraint_cib_diff)
    env.report_processor.report(
        ReportItem.info(
            reports.messages.ResourceMoveConstraintCreated(resource_id)
        )
    )
    env.wait_for_idle(wait_timeout)
    # verify that:
    # - the live cib (now containing the move constraint) causes the resource
    #   to move by comparing the original status of the resource with a status
    #   computed from the live cib
    # - applying the diff which removes the move constraint won't trigger
    #   moving the resource (or other resources) around
    try:
        _ensure_resource_moved_and_not_moved_back(
            env.cmd_runner,
            env.report_processor,
            get_cib_xml(env.cmd_runner()),
            remove_constraint_cib_diff,
            resource_id,
            strict,
            resource_state_before,
            node,
        )
    except ResourceMoveAutocleanSimulationFailure as e:
        raise LibraryError(
            reports.ReportItem.error(
                reports.messages.ResourceMoveAutocleanSimulationFailure(
                    resource_id,
                    e.other_resources_affected,
                    node=node,
                    move_constraint_left_in_cib=True,
                )
            )
        ) from e
    # apply the diff which removes the move constraint to the live cib and wait
    # for the cluster to settle
    push_cib_diff_xml(env.cmd_runner(), remove_constraint_cib_diff)
    env.report_processor.report(
        ReportItem.info(
            reports.messages.ResourceMoveConstraintRemoved(resource_id)
        )
    )
    env.wait_for_idle(wait_timeout)
    if env.report_processor.report(
        _move_wait_report(
            resource_id,
            node,
            resource_state_before,
            get_resource_state(env.get_cluster_state(), resource_id),
        )
    ).has_errors:
        raise LibraryError()


def _ensure_resource_moved_and_not_moved_back(
    runner_factory: Callable[[Optional[Mapping[str, str]]], CommandRunner],
    report_processor: reports.ReportProcessor,
    cib_xml: str,
    remove_constraint_cib_diff: str,
    resource_id: str,
    strict: bool,
    resource_state_before: Dict[str, List[str]],
    node: Optional[str],
) -> None:
    with get_tmp_cib(report_processor, cib_xml) as rsc_unmove_cib_file:
        if not _was_resource_moved(
            node,
            resource_state_before,
            get_resource_state(
                get_cluster_status_dom(
                    runner_factory(dict(CIB_file=rsc_unmove_cib_file.name))
                ),
                resource_id,
            ),
        ):
            raise LibraryError(
                reports.ReportItem.error(
                    reports.messages.ResourceMoveNotAffectingResource(
                        resource_id
                    )
                )
            )
        push_cib_diff_xml(
            runner_factory(dict(CIB_file=rsc_unmove_cib_file.name)),
            remove_constraint_cib_diff,
        )
        rsc_unmove_cib_file.seek(0)
        rsc_unmove_cib_xml = rsc_unmove_cib_file.read()

    with get_tmp_cib(report_processor, cib_xml) as orig_cib_file:
        _, clean_transitions, _ = simulate_cib(
            runner_factory(dict(CIB_file=orig_cib_file.name)),
            get_cib(rsc_unmove_cib_xml),
        )

    clean_operations = simulate_tools.get_operations_from_transitions(
        clean_transitions
    )
    if strict:
        if clean_operations:
            raise ResourceMoveAutocleanSimulationFailure(True)
    elif any(
        rsc == resource_id
        for rsc in simulate_tools.get_resources_from_operations(
            clean_operations
        )
    ):
        raise ResourceMoveAutocleanSimulationFailure(False)


def ban(env, resource_id, node=None, master=False, lifetime=None, wait=False):
    """
    Create a constraint to keep a resource of a node

    LibraryEnvironment env
    string resource_id -- id of a resource to be banned
    string node -- node to ban the resource on, ban on the current node if None
    bool master -- limit the constraint to the Promoted role
    string lifetime -- lifespan of the constraint, forever if None
    mixed wait -- flag for controlling waiting for pacemaker idle mechanism
    """
    return _Ban().run(
        env,
        resource_id,
        node=node,
        promoted=master,
        lifetime=lifetime,
        wait=wait,
    )


def _resource_running_on_nodes(
    resource_state: Dict[str, List[str]],
) -> FrozenSet[str]:
    if resource_state:
        return frozenset(
            resource_state.get(const.PCMK_ROLE_PROMOTED, [])
            + resource_state.get(const.PCMK_ROLE_PROMOTED_LEGACY, [])
            + resource_state.get(const.PCMK_ROLE_STARTED, [])
        )
    return frozenset()


def _was_resource_moved(
    node: Optional[str],
    resource_state_before: Dict[str, List[str]],
    resource_state_after: Dict[str, List[str]],
) -> bool:
    running_on_nodes = _resource_running_on_nodes(resource_state_after)
    return not bool(
        resource_state_before
        and (  # running resource moved
            not running_on_nodes
            or (node and node not in running_on_nodes)
            or (resource_state_before == resource_state_after)
        )
    )


def _move_wait_report(
    resource_id: str,
    node: Optional[str],
    resource_state_before: Dict[str, List[str]],
    resource_state_after: Dict[str, List[str]],
) -> ReportItem:
    severity = reports.item.ReportItemSeverity.info()
    if not _was_resource_moved(
        node, resource_state_before, resource_state_after
    ):
        severity = reports.item.ReportItemSeverity.error()
    if not resource_state_after:
        return ReportItem(
            severity,
            reports.messages.ResourceDoesNotRun(resource_id),
        )
    return ReportItem(
        severity,
        reports.messages.ResourceRunningOnNodes(
            resource_id,
            resource_state_after,
        ),
    )


def _move_ban_pcmk_error_report(
    resource_id: str, stdout: str, stderr: str, is_ban: bool
) -> reports.ReportItem:
    active_in_locations = re.search(
        f"Resource '{resource_id}' not moved: active in (?P<locations>\\d+) locations",
        stderr,
    )
    if active_in_locations:
        if active_in_locations.group("locations") == "0":
            message_stopped = (
                reports.messages.CannotBanResourceStoppedNoNodeSpecified
                if is_ban
                else reports.messages.CannotMoveResourceStoppedNoNodeSpecified
            )
            return reports.ReportItem.error(message_stopped(resource_id))
        message_multiple = (
            reports.messages.CannotBanResourceMultipleInstancesNoNodeSpecified
            if is_ban
            else reports.messages.CannotMoveResourceMultipleInstancesNoNodeSpecified
        )
        return reports.ReportItem.error(message_multiple(resource_id))

    if not is_ban and "Multiple items match request" in stderr:
        return reports.ReportItem.error(
            reports.messages.CannotMoveResourceMultipleInstances(resource_id)
        )

    message_generic = (
        reports.messages.ResourceBanPcmkError
        if is_ban
        else reports.messages.ResourceMovePcmkError
    )
    return reports.ReportItem.error(
        message_generic(resource_id, stdout, stderr)
    )


class _MoveBanTemplate:
    _is_ban = False

    def _validate(self, resource_el, promoted):
        raise NotImplementedError()

    def _run_action(self, runner, resource_id, node, promoted, lifetime):
        raise NotImplementedError()

    def _report_action_pcmk_success(self, resource_id, stdout, stderr):
        raise NotImplementedError()

    @staticmethod
    def _report_resource_may_or_may_not_move(
        resource_id: str,
    ) -> ReportItemList:
        del resource_id
        return []

    @staticmethod
    def _report_wait_result(
        resource_id,
        node,
        resource_running_on_before,
        resource_running_on_after,
    ):
        raise NotImplementedError()

    def run(
        self,
        env: LibraryEnvironment,
        resource_id,
        node=None,
        promoted=False,
        lifetime=None,
        wait: WaitType = False,
    ):
        # pylint: disable=too-many-locals
        # validate

        if wait is not False:
            # deprecated in the first version of 0.12
            env.report_processor.report(
                reports.ReportItem.deprecation(
                    reports.messages.ResourceWaitDeprecated()
                )
            )

        wait_timeout = env.ensure_wait_satisfiable(wait)  # raises on error

        cib = env.get_cib()
        resource_el, report_list = resource.common.find_one_resource(
            get_resources(cib), resource_id
        )
        if resource_el is not None:
            report_list.extend(self._validate(resource_el, promoted))
        if node:
            report_list.extend(_nodes_exist_reports(cib, [node]))
        if env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()

        # get current status for wait processing
        if wait_timeout >= 0:
            resource_running_on_before = get_resource_state(
                env.get_cluster_state(), resource_id
            )

        # run the action
        stdout, stderr, retval = self._run_action(
            env.cmd_runner(),
            resource_id,
            node=node,
            promoted=promoted,
            lifetime=lifetime,
        )
        if retval != 0:
            raise LibraryError(
                _move_ban_pcmk_error_report(
                    resource_id, stdout, stderr, self._is_ban
                )
            )

        if node and not stdout and not stderr:
            env.report_processor.report_list(
                self._report_resource_may_or_may_not_move(resource_id)
            )
        env.report_processor.report(
            self._report_action_pcmk_success(resource_id, stdout, stderr)
        )

        # process wait
        if wait_timeout >= 0:
            env.wait_for_idle(wait_timeout)
            resource_running_on_after = get_resource_state(
                env.get_cluster_state(), resource_id
            )
            if env.report_processor.report(
                self._report_wait_result(
                    resource_id,
                    node,
                    resource_running_on_before,
                    resource_running_on_after,
                )
            ).has_errors:
                raise LibraryError()


class _Move(_MoveBanTemplate):
    def _validate(self, resource_el, promoted):
        return resource.validations.validate_move(resource_el, promoted)

    def _run_action(self, runner, resource_id, node, promoted, lifetime):
        return resource_move(
            runner, resource_id, node=node, promoted=promoted, lifetime=lifetime
        )

    def _report_action_pcmk_success(self, resource_id, stdout, stderr):
        return ReportItem.info(
            reports.messages.ResourceMovePcmkSuccess(
                resource_id,
                stdout,
                stderr,
            )
        )

    @staticmethod
    def _report_resource_may_or_may_not_move(
        resource_id: str,
    ) -> ReportItemList:
        return [
            ReportItem.warning(
                reports.messages.ResourceMayOrMayNotMove(resource_id)
            )
        ]

    @staticmethod
    def _report_wait_result(
        resource_id,
        node,
        resource_running_on_before,
        resource_running_on_after,
    ):
        return _move_wait_report(
            resource_id,
            node,
            resource_running_on_before,
            resource_running_on_after,
        )


class _Ban(_MoveBanTemplate):
    _is_ban = True

    def _validate(self, resource_el, promoted):
        return resource.validations.validate_ban(resource_el, promoted)

    def _run_action(self, runner, resource_id, node, promoted, lifetime):
        return resource_ban(
            runner, resource_id, node=node, promoted=promoted, lifetime=lifetime
        )

    def _report_action_pcmk_success(
        self,
        resource_id: str,
        stdout: str,
        stderr: str,
    ) -> ReportItem:
        return ReportItem.info(
            reports.messages.ResourceBanPcmkSuccess(resource_id, stdout, stderr)
        )

    @staticmethod
    def _report_wait_result(
        resource_id,
        node,
        resource_running_on_before,
        resource_running_on_after,
    ):
        running_on_nodes = _resource_running_on_nodes(resource_running_on_after)
        if node:
            banned_nodes = frozenset([node])
        else:
            banned_nodes = _resource_running_on_nodes(
                resource_running_on_before
            )

        severity = reports.item.ReportItemSeverity.info()
        if not banned_nodes.isdisjoint(running_on_nodes) or (
            resource_running_on_before and not running_on_nodes
        ):
            severity = reports.item.ReportItemSeverity.error()
        if not resource_running_on_after:
            return ReportItem(
                severity,
                reports.messages.ResourceDoesNotRun(resource_id),
            )
        return ReportItem(
            severity,
            reports.messages.ResourceRunningOnNodes(
                resource_id,
                resource_running_on_after,
            ),
        )


def unmove_unban(
    env, resource_id, node=None, master=False, expired=False, wait=False
):
    """
    Remove all constraints created by move and ban

    LibraryEnvironment env
    string resource_id -- id of a resource to be unmoved/unbanned
    string node -- node to limit unmoving/unbanning to, all nodes if None
    bool master -- only remove constraints for Promoted role
    bool expired -- only remove constrains which have already expired
    mixed wait -- flag for controlling waiting for pacemaker idle mechanism
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    # validate
    wait_timeout = env.ensure_wait_satisfiable(wait)  # raises on error

    resource_el, report_list = resource.common.find_one_resource(
        get_resources(env.get_cib()), resource_id
    )
    if resource_el is not None:
        report_list.extend(
            resource.validations.validate_unmove_unban(resource_el, master)
        )
    if expired and not has_resource_unmove_unban_expired_support(
        env.cmd_runner()
    ):
        report_list.append(
            ReportItem.error(
                reports.messages.ResourceUnmoveUnbanPcmkExpiredNotSupported()
            )
        )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    # run the action
    stdout, stderr, retval = resource_unmove_unban(
        env.cmd_runner(),
        resource_id,
        node=node,
        promoted=master,
        expired=expired,
    )
    if retval != 0:
        raise LibraryError(
            ReportItem.error(
                reports.messages.ResourceUnmoveUnbanPcmkError(
                    resource_id, stdout, stderr
                )
            )
        )
    env.report_processor.report(
        ReportItem.info(
            reports.messages.ResourceUnmoveUnbanPcmkSuccess(
                resource_id, stdout, stderr
            )
        )
    )

    # process wait
    if wait_timeout >= 0:
        env.wait_for_idle(wait_timeout)
        if env.report_processor.report(
            info_resource_state(env.get_cluster_state(), resource_id)
        ).has_errors:
            raise LibraryError()


def _find_resource_elem(
    cib: _Element,
    resource_id: str,
) -> _Element:
    """
    Find a resource element in CIB and handle errors.

    cib -- CIB
    resource_id -- name of the resource
    """
    try:
        resource_el = get_element_by_id(cib, resource_id)
    except ElementNotFound as exc:
        raise LibraryError(
            ReportItem.error(
                reports.messages.IdNotFound(
                    resource_id, expected_types=["resource"]
                )
            )
        ) from exc
    if not resource.common.is_resource(resource_el):
        raise LibraryError(
            ReportItem.error(
                reports.messages.IdBelongsToUnexpectedType(
                    resource_id,
                    expected_types=["resource"],
                    current_type=resource_el.tag,
                )
            )
        )
    return resource_el


def get_resource_relations_tree(
    env: LibraryEnvironment,
    resource_id: str,
) -> Mapping[str, Any]:
    """
    Return a dict representing tree-like structure of resources and their
    relations.

    env -- library environment
    resource_id -- id of a resource which should be the root of the relation
        tree
    """
    cib = env.get_cib()
    resource_el = _find_resource_elem(cib, resource_id)
    if resource.stonith.is_stonith(resource_el):
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.CommandArgumentTypeMismatch("stonith resource")
            )
        )
        raise LibraryError()

    (
        resources_dict,
        relations_dict,
    ) = resource.relations.ResourceRelationsFetcher(cib).get_relations(
        resource_id
    )
    return dto.to_dict(
        resource.relations.ResourceRelationTreeBuilder(
            resources_dict, relations_dict
        )
        .get_tree(resource_id)
        .to_dto()
    )


def _find_resources_expand_tags(
    cib: _Element,
    resource_or_tag_ids: StringCollection,
    additional_search: Optional[Callable[[_Element], List[_Element]]] = None,
) -> Tuple[List[_Element], ReportItemList]:
    rsc_or_tag_el_list, report_list = resource.common.find_resources(
        cib,
        resource_or_tag_ids,
        resource_tags=cib_const.TAG_LIST_RESOURCE | {cib_const.TAG_TAG},
    )

    resource_set = set()
    for el in rsc_or_tag_el_list:
        resource_set.update(
            expand_tag(el, only_expand_types=cib_const.TAG_LIST_RESOURCE)
        )
    if not additional_search:
        return list(resource_set), report_list

    final_set = set()
    for el in resource_set:
        final_set.update(additional_search(el))
    return list(final_set), report_list


def get_required_cib_version_for_primitive(
    op_list: Iterable[Mapping[str, str]],
) -> Optional[Version]:
    for op in op_list:
        if op.get("on-fail", "") == "demote":
            return Version(3, 4, 0)
    return None


def is_any_resource_except_stonith(
    env: LibraryEnvironment,
    resource_id_list: List[str],
) -> bool:
    """
    Return True if any resource is a non stonith resource. False otherwise.
    """
    cib = env.get_cib()
    return any(
        not resource.stonith.is_stonith(resource_el)
        for resource_el in _find_resources_expand_tags(cib, resource_id_list)[0]
    )


def is_any_stonith(
    env: LibraryEnvironment,
    resource_id_list: List[str],
) -> bool:
    """
    Return True if any resource is a stonith resource. False otherwise.
    """
    cib = env.get_cib()
    return any(
        resource.stonith.is_stonith(resource_el)
        for resource_el in _find_resources_expand_tags(cib, resource_id_list)[0]
    )


def get_configured_resources(env: LibraryEnvironment) -> CibResourcesDto:
    resources = get_resources(env.get_cib())
    bundles = []
    for bundle_el in resources.findall(cib_const.TAG_RESOURCE_BUNDLE):
        bundle_dto = resource.bundle.bundle_element_to_dto(bundle_el)
        bundles.append(bundle_dto)
        if not (bundle_dto.container_type and bundle_dto.container_options):
            env.report_processor.report(
                reports.ReportItem.warning(
                    reports.messages.ResourceBundleUnsupportedContainerType(
                        str(bundle_el.attrib["id"]),
                        supported_container_types=sorted(
                            resource.bundle.GENERIC_CONTAINER_TYPES
                        ),
                        updating_options=False,
                    )
                )
            )
    return CibResourcesDto(
        primitives=[
            resource.primitive.primitive_element_to_dto(resource_el)
            for resource_el in resources.findall(
                f".//{cib_const.TAG_RESOURCE_PRIMITIVE}"
            )
        ],
        clones=[
            resource.clone.clone_element_to_dto(resource_el)
            for resource_el in resources.findall(cib_const.TAG_RESOURCE_CLONE)
        ]
        + [
            resource.clone.master_element_to_dto(resource_el)
            for resource_el in resources.findall(cib_const.TAG_RESOURCE_MASTER)
        ],
        groups=[
            resource.group.group_element_to_dto(resource_el)
            for resource_el in resources.findall(
                f".//{cib_const.TAG_RESOURCE_GROUP}"
            )
        ],
        bundles=bundles,
    )


def restart(
    env: LibraryEnvironment,
    resource_id: str,
    node: Optional[str] = None,
    timeout: Optional[str] = None,
) -> None:
    """
    Restart a resource

    resource_id -- id of the resource to be restarted
    node -- name of the node to limit the restart to
    timeout -- abort if the command doesn't finish in this time (integer + unit)
    """
    cib = env.get_cib()

    # To be able to restart bundle instances, which are not to be found in CIB,
    # do not fail if specified ID is not found in CIB. Pacemaker provides
    # reasonable messages when the ID to be restarted is not a resource or
    # doesn't exist. We only search for the resource in order to provide hints
    # when the user attempts to restart bundle's or clone's inner resources.
    resource_found = False
    try:
        resource_el = get_element_by_id(cib, resource_id)
        resource_found = True
    except ElementNotFound:
        pass

    if resource_found:
        if not resource.common.is_resource(resource_el):
            env.report_processor.report(
                ReportItem.error(
                    reports.messages.IdBelongsToUnexpectedType(
                        resource_id,
                        expected_types=["resource"],
                        current_type=resource_el.tag,
                    )
                )
            )
            raise LibraryError()

        if resource.stonith.is_stonith(resource_el):
            env.report_processor.report(
                reports.ReportItem.error(
                    reports.messages.CommandArgumentTypeMismatch(
                        "stonith resource"
                    )
                )
            )
            raise LibraryError()

        parent_resource_el = resource.clone.get_parent_any_clone(resource_el)
        if parent_resource_el is None:
            parent_resource_el = resource.bundle.get_parent_bundle(resource_el)
        if parent_resource_el is not None:
            env.report_processor.report(
                reports.ReportItem.warning(
                    reports.messages.ResourceRestartUsingParentRersource(
                        str(resource_el.attrib["id"]),
                        str(parent_resource_el.attrib["id"]),
                    )
                )
            )
            resource_el = parent_resource_el

        if node and not (
            resource.clone.is_any_clone(resource_el)
            or resource.bundle.is_bundle(resource_el)
        ):
            env.report_processor.report(
                reports.ReportItem.error(
                    reports.messages.ResourceRestartNodeIsForMultiinstanceOnly(
                        str(resource_el.attrib["id"]),
                        resource_el.tag,
                        node,
                    )
                )
            )

    if timeout is not None:
        env.report_processor.report_list(
            ValueTimeInterval("timeout").validate({"timeout": timeout})
        )

    if env.report_processor.has_errors:
        raise LibraryError()

    resource_restart(
        env.cmd_runner(),
        str(resource_el.attrib["id"]) if resource_found else resource_id,
        node=node,
        timeout=timeout,
    )


def update_meta(
    env: LibraryEnvironment,
    resource_id: str,
    meta_attrs: Mapping[str, str],
    force_flags: reports.types.ForceFlags,
) -> None:
    """
    Update meta attributes of all resource types without stonith check

    env -- library environment
    resource_id -- id of resource to update
    meta_attrs -- meta attributes to update with desired values
    force_flags -- force flags
    """
    cib = env.get_cib()
    resource_el = _find_resource_elem(cib, resource_id)
    id_provider = IdProvider(cib)
    cib_validate_with = get_pacemaker_version_by_which_cib_was_validated(cib)
    if resource.clone.is_master(resource_el):
        resource.clone.convert_master_to_promotable(
            id_provider, cib_validate_with, resource_el
        )

    meta_attrs_nvset_list = find_nvsets(resource_el, NVSET_META)
    meta_attrs_nvset = (
        meta_attrs_nvset_list[0] if meta_attrs_nvset_list else None
    )

    (
        existing_nodes_names,
        existing_nodes_addrs,
        report_list,
    ) = get_existing_nodes_names_addrs(
        env.get_corosync_conf() if env.is_cib_live else None,
        cib=cib,
    )
    env.report_processor.report_list(report_list)

    existing_meta_attrs = (
        nvset_to_dict_except_without_values(meta_attrs_nvset)
        if meta_attrs_nvset is not None
        else {}
    )
    if not resource.stonith.is_stonith(resource_el):
        env.report_processor.report_list(
            resource.guest_node.validate_updating_guest_attributes(
                cib,
                existing_nodes_names,
                existing_nodes_addrs,
                meta_attrs,
                existing_meta_attrs,
                force_flags,
            )
        )

    cmd_runner = env.cmd_runner()

    if resource.clone.is_any_clone(resource_el):
        _validate_clone_meta_attributes(
            env.report_processor,
            ResourceAgentFacadeFactory(cmd_runner, env.report_processor),
            resource_el,
            meta_attrs,
            force_flags,
        )

    if env.report_processor.has_errors:
        raise LibraryError()

    # Do not add element if user didn't provide any value
    if meta_attrs_nvset is None and any(meta_attrs.values()):
        nvset_append_new(
            resource_el,
            id_provider,
            cib_validate_with,
            NVSET_META,
            nvpair_dict=meta_attrs,
            nvset_options={},
        )
    elif meta_attrs_nvset is not None:
        nvset_update(meta_attrs_nvset, id_provider, meta_attrs)

    env.push_cib()

    # If remote node was removed or its name changed, it needs to be removed
    # from pacemaker
    if (
        reports.codes.FORCE in force_flags
        and resource.guest_node.OPTION_REMOTE_NODE in meta_attrs
        and resource.guest_node.OPTION_REMOTE_NODE in existing_meta_attrs
        and existing_meta_attrs[resource.guest_node.OPTION_REMOTE_NODE]
        != meta_attrs[resource.guest_node.OPTION_REMOTE_NODE]
    ):
        remove_node(
            cmd_runner,
            existing_meta_attrs[resource.guest_node.OPTION_REMOTE_NODE],
        )


def stop(
    env: LibraryEnvironment,
    resource_or_tag_ids: StringCollection,
    force_flags: reports.types.ForceFlags = (),
) -> None:
    """
    Stop the specified resources similarly to 'disable'. Unlike disable,
    this command finds all resources including inner resources and then
    disables all of the found primitives, making it more probable that
    the resources will really be stopped by pacemaker.

    env -- provides all for communication with externals
    resource_or_tag_ids -- ids of the resources to become stopped, or in case
        of tag ids, all resources in tags are to be stopped
    force_flags -- force flags
    """
    cib = env.get_cib()
    id_provider = IdProvider(cib)
    resource_elements, report_list = _find_resources_expand_tags(
        cib, resource_or_tag_ids
    )
    env.report_processor.report_list(report_list)

    resources_to_stop = []
    for el in resource_elements:
        resources_to_stop.extend(resource.common.find_primitives(el))
        # we also need to disable bundle resources
        if resource.common.is_bundle(el):
            resources_to_stop.append(el)

    resource_ids = []
    stonith_resource_ids = []
    for resource_el in resources_to_stop:
        resource_id = str(resource_el.attrib["id"])
        resource_ids.append(resource_id)
        if resource.stonith.is_stonith(resource_el):
            stonith_resource_ids.append(resource_id)
    resource_ids.sort()

    if stonith_resource_ids:
        env.report_processor.report_list(
            ensure_some_stonith_remains(
                env,
                get_resources(cib),
                stonith_resources_to_ignore=stonith_resource_ids,
                sbd_being_disabled=False,
                force_flags=force_flags,
            )
        )
    env.report_processor.report_list(
        _ensure_resources_managed(
            env.get_cluster_state(), resource_ids, force_flags
        )
    )

    if env.report_processor.has_errors:
        raise LibraryError()

    env.report_processor.report(
        reports.ReportItem.info(
            reports.messages.StoppingResources(resource_ids)
        )
    )
    for el in resources_to_stop:
        resource.common.disable(el, id_provider)

    env.push_cib()


def _ensure_resources_managed(
    state: _Element,
    resource_ids: StringSequence,
    force_flags: reports.types.ForceFlags,
) -> reports.ReportItemList:
    report_list: reports.ReportItemList = []
    try:
        parser = ClusterStatusParser(state)
        try:
            status_dto = parser.status_xml_to_dto()
        except ClusterStatusParsingError as e:
            report_list.append(cluster_status_parsing_error_to_report(e))
            return report_list
        report_list.extend(parser.get_warnings())

        status = ResourcesStatusFacade.from_resources_status_dto(status_dto)
        for r_id in resource_ids:
            if not status.exists(r_id, None):
                # Pacemaker does not put misconfigured resources into cluster
                # status and we are unable to check state of such resources.
                # This happens for e.g. bundle with primitive resource inside
                # and no IP address for the bundle specified. We expect the
                # resource to be stopped since it is misconfigured. Stopping it
                # again even when it is unmanaged should not break anything.
                report_list.append(
                    reports.ReportItem.debug(
                        reports.messages.ConfiguredResourceMissingInStatus(
                            r_id, ResourceState.UNMANAGED
                        )
                    )
                )
            elif status.is_state(r_id, None, ResourceState.UNMANAGED):
                report_list.append(
                    reports.ReportItem(
                        reports.get_severity(
                            reports.codes.FORCE,
                            reports.codes.FORCE in force_flags,
                        ),
                        reports.messages.ResourceIsUnmanaged(r_id),
                    )
                )
    except NotImplementedError:
        # TODO remove when issue with bundles in status is fixed
        report_list.extend(
            reports.ReportItem(
                reports.get_severity(
                    reports.codes.FORCE,
                    reports.codes.FORCE in force_flags,
                ),
                reports.messages.ResourceIsUnmanaged(resource_id),
            )
            for resource_id in resource_ids
            if not is_resource_managed(state, resource_id)
        )

    return report_list
