from typing import TYPE_CHECKING, Callable, Iterable, Mapping, Optional

from lxml.etree import _Element

from pcs import settings
from pcs.common import reports
from pcs.common.file import RawFileError
from pcs.lib import node_communication_format
from pcs.lib.cib.remove_elements import (
    ElementsToRemove,
    ensure_resources_stopped,
    remove_specified_elements,
)
from pcs.lib.cib.resource import (
    guest_node,
    primitive,
    remote_node,
)
from pcs.lib.cib.tools import (
    ElementSearcher,
    IdProvider,
    get_resources,
)

# TODO lib.commands should never import each other. This is to be removed when
# the 'resource create' commands are overhauled.
from pcs.lib.commands.resource import get_required_cib_version_for_primitive
from pcs.lib.communication.nodes import (
    DistributeFiles,
    GetHostInfo,
    GetOnlineTargets,
    RemoveFiles,
    ServiceAction,
)
from pcs.lib.communication.tools import run as run_com
from pcs.lib.communication.tools import run_and_raise
from pcs.lib.env import (
    LibraryEnvironment,
    WaitType,
)
from pcs.lib.errors import LibraryError
from pcs.lib.file.instance import FileInstance
from pcs.lib.file.raw_file import raw_file_error_report
from pcs.lib.node import get_existing_nodes_names_addrs
from pcs.lib.pacemaker import state
from pcs.lib.pacemaker.live import remove_node
from pcs.lib.resource_agent import (
    ResourceAgentError,
    ResourceAgentFacadeFactory,
    resource_agent_error_to_report_item,
)
from pcs.lib.tools import generate_binary_key

if TYPE_CHECKING:
    from pcs.lib.corosync.config_facade import (
        ConfigFacade as CorosyncConfigFacade,
    )


def _reports_skip_new_node(new_node_name, reason_type):
    assert reason_type in {"unreachable", "not_live_cib"}
    return [
        reports.ReportItem.info(
            reports.messages.FilesDistributionSkipped(
                reason_type, ["pacemaker authkey"], [new_node_name]
            )
        ),
        reports.ReportItem.info(
            reports.messages.ServiceCommandsOnNodesSkipped(
                reason_type,
                ["pacemaker_remote start", "pacemaker_remote enable"],
                [new_node_name],
            )
        ),
    ]


def _get_targets_for_add(
    target_factory,
    report_processor,
    existing_nodes_names,
    new_nodes_names,
    skip_offline_nodes,
):
    # Get targets for all existing nodes and report unknown (not-authorized)
    # nodes.
    (
        target_report_list,
        existing_target_list,
    ) = target_factory.get_target_list_with_reports(
        existing_nodes_names, skip_non_existing=skip_offline_nodes
    )
    report_processor.report_list(target_report_list)
    # Get a target for the new node.
    (
        target_report_list,
        new_target_list,
    ) = target_factory.get_target_list_with_reports(
        new_nodes_names,
        skip_non_existing=skip_offline_nodes,
        # continue even if the new node is unknown when skip is True
        report_none_host_found=False,
    )
    report_processor.report_list(target_report_list)
    return existing_target_list, new_target_list


def _host_check_remote_node(host_info_dict):
    # Version of services may not be the same across the existing cluster
    # nodes, so it's not easy to make this check properly.
    report_list = []
    required_service_list = ["pacemaker_remote"]
    required_as_stopped_service_list = required_service_list + [
        "pacemaker",
        "corosync",
    ]
    for host_name, host_info in host_info_dict.items():
        try:
            services = host_info["services"]
            missing_service_list = [
                service
                for service in required_service_list
                if not services[service]["installed"]
            ]
            if missing_service_list:
                report_list.append(
                    reports.ReportItem.error(
                        reports.messages.ServiceNotInstalled(
                            host_name, sorted(missing_service_list)
                        )
                    )
                )
            cannot_be_running_service_list = [
                service
                for service in required_as_stopped_service_list
                if service in services and services[service]["running"]
            ]
            if cannot_be_running_service_list:
                report_list.append(
                    reports.ReportItem.error(
                        reports.messages.HostAlreadyInClusterServices(
                            host_name,
                            sorted(cannot_be_running_service_list),
                        )
                    )
                )
            if host_info["cluster_configuration_exists"]:
                report_list.append(
                    reports.ReportItem.error(
                        reports.messages.HostAlreadyInClusterConfig(host_name)
                    )
                )
        except (KeyError, TypeError):
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.InvalidResponseFormat(host_name)
                )
            )
    return report_list


def _prepare_pacemaker_remote_environment(
    env,
    report_processor,
    existing_nodes_target_list,
    new_node_target,
    new_node_name,
    skip_offline_nodes,
    allow_incomplete_distribution,
    allow_fails,
):
    if new_node_target:
        com_cmd = GetOnlineTargets(
            report_processor,
            ignore_offline_targets=skip_offline_nodes,
        )
        com_cmd.set_targets([new_node_target])
        online_new_target_list = run_com(env.get_node_communicator(), com_cmd)
        if not online_new_target_list and not skip_offline_nodes:
            raise LibraryError()
    else:
        online_new_target_list = []

    # check new nodes
    if online_new_target_list:
        com_cmd = GetHostInfo(report_processor)
        com_cmd.set_targets(online_new_target_list)
        report_processor.report_list(
            _host_check_remote_node(
                run_com(env.get_node_communicator(), com_cmd)
            )
        )
        if report_processor.has_errors:
            raise LibraryError()
    else:
        report_processor.report_list(
            _reports_skip_new_node(new_node_name, "unreachable")
        )

    # share pacemaker authkey
    authkey_file = FileInstance.for_pacemaker_key()
    try:
        if authkey_file.raw_file.exists():
            authkey_content = authkey_file.read_raw()
            authkey_targets = online_new_target_list
        else:
            authkey_content = generate_binary_key(
                random_bytes_count=settings.pacemaker_authkey_bytes
            )
            authkey_targets = (
                existing_nodes_target_list + online_new_target_list
            )
    except RawFileError as e:
        report_processor.report(raw_file_error_report(e))
    if report_processor.has_errors:
        raise LibraryError()

    if authkey_targets:
        com_cmd = DistributeFiles(
            report_processor,
            node_communication_format.pcmk_authkey_file(authkey_content),
            skip_offline_targets=skip_offline_nodes,
            allow_fails=allow_incomplete_distribution,
        )
        com_cmd.set_targets(authkey_targets)
        run_and_raise(env.get_node_communicator(), com_cmd)

    # start and enable pacemaker_remote
    if online_new_target_list:
        com_cmd = ServiceAction(
            report_processor,
            node_communication_format.create_pcmk_remote_actions(
                [
                    "start",
                    "enable",
                ]
            ),
            allow_fails=allow_fails,
        )
        com_cmd.set_targets(online_new_target_list)
        run_and_raise(env.get_node_communicator(), com_cmd)


def _ensure_resource_running(env: LibraryEnvironment, resource_id):
    if env.report_processor.report(
        state.ensure_resource_running(env.get_cluster_state(), resource_id)
    ).has_errors:
        raise LibraryError()


def node_add_remote(  # noqa: PLR0912, PLR0913, PLR0915
    env: LibraryEnvironment,
    node_name: str,
    node_addr: Optional[str],
    operations: Iterable[Mapping[str, str]],
    meta_attributes: Mapping[str, str],
    instance_attributes: Mapping[str, str],
    *,
    skip_offline_nodes: bool = False,
    allow_incomplete_distribution: bool = False,
    allow_pacemaker_remote_service_fail: bool = False,
    allow_invalid_operation: bool = False,
    allow_invalid_instance_attributes: bool = False,
    use_default_operations: bool = True,
    wait: WaitType = False,
):
    # pylint: disable=too-many-arguments
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    create an ocf:pacemaker:remote resource and use it as a remote node

    env -- provides all for communication with externals
    node_name -- the name of the new node
    node_addr -- the address of the new node or None for default
    operations -- attributes for each entered operation
    meta_attributes -- attributes for primitive/meta_attributes
    instance_attributes -- attributes for primitive/instance_attributes
    skip_offline_nodes -- if True, ignore when some nodes are offline
    allow_incomplete_distribution -- if True, allow this command to
        finish successfully even if file distribution did not succeed
    allow_pacemaker_remote_service_fail -- if True, allow this command to
        finish successfully even if starting/enabling pacemaker_remote did not
        succeed
    allow_invalid_operation -- if True, allow to use operations that
        are not listed in a resource agent metadata
    allow_invalid_instance_attributes -- if True, allow to use instance
        attributes that are not listed in a resource agent metadata and allow to
        omit required instance_attributes
    use_default_operations -- if True, add operations specified in
        a resource agent metadata to the resource
    wait -- a flag for controlling waiting for pacemaker idle mechanism
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    wait_timeout = env.ensure_wait_satisfiable(wait)

    report_processor = env.report_processor
    cib = env.get_cib(
        minimal_version=get_required_cib_version_for_primitive(operations)
    )
    id_provider = IdProvider(cib)
    if env.is_cib_live:
        corosync_conf: Optional[CorosyncConfigFacade] = env.get_corosync_conf()
    else:
        corosync_conf = None
        report_processor.report(
            reports.ReportItem.info(
                reports.messages.CorosyncNodeConflictCheckSkipped(
                    reports.const.REASON_NOT_LIVE_CIB,
                )
            )
        )
    (
        existing_nodes_names,
        existing_nodes_addrs,
        report_list,
    ) = get_existing_nodes_names_addrs(corosync_conf, cib)
    if env.is_cib_live:
        # We just reported corosync checks are going to be skipped so we
        # shouldn't complain about errors related to corosync nodes
        report_processor.report_list(report_list)

    try:
        resource_agent_facade = ResourceAgentFacadeFactory(
            env.cmd_runner(), report_processor
        ).facade_from_parsed_name(remote_node.AGENT_NAME)
    except ResourceAgentError as e:
        report_processor.report(resource_agent_error_to_report_item(e))
        raise LibraryError() from e

    existing_target_list = []
    if env.is_cib_live:
        target_factory = env.get_node_target_factory()
        existing_target_list, new_target_list = _get_targets_for_add(
            target_factory,
            report_processor,
            existing_nodes_names,
            [node_name],
            skip_offline_nodes,
        )
        new_target = new_target_list[0] if new_target_list else None
        # default node_addr to an address from known-hosts
        if node_addr is None:
            if new_target:
                node_addr = new_target.first_addr
                node_addr_source = (
                    reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                )
            else:
                node_addr = node_name
                node_addr_source = (
                    reports.const.DEFAULT_ADDRESS_SOURCE_HOST_NAME
                )
            report_processor.report(
                reports.ReportItem.info(
                    reports.messages.UsingDefaultAddressForHost(
                        node_name, node_addr, node_addr_source
                    )
                )
            )
    # default node_addr to an address from known-hosts
    elif node_addr is None:
        known_hosts = env.get_known_hosts([node_name])
        if known_hosts:
            node_addr = known_hosts[0].dest.addr
            node_addr_source = reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
        else:
            node_addr = node_name
            node_addr_source = reports.const.DEFAULT_ADDRESS_SOURCE_HOST_NAME
        report_processor.report(
            reports.ReportItem.info(
                reports.messages.UsingDefaultAddressForHost(
                    node_name, node_addr, node_addr_source
                )
            )
        )

    # validate inputs
    report_list = remote_node.validate_create(
        existing_nodes_names,
        existing_nodes_addrs,
        resource_agent_facade.metadata,
        node_name,
        node_addr,
        instance_attributes,
    )
    if report_processor.report_list(report_list).has_errors:
        raise LibraryError()
    # validation + cib setup
    # TODO extract the validation to a separate function
    try:
        remote_resource_element = remote_node.create(
            env.report_processor,
            env.cmd_runner(),
            resource_agent_facade,
            get_resources(cib),
            id_provider,
            node_addr,
            node_name,
            operations,
            meta_attributes,
            instance_attributes,
            allow_invalid_operation,
            allow_invalid_instance_attributes,
            use_default_operations,
        )
    except LibraryError as e:
        # Check unique id conflict with check against nodes. Until validation
        # resource create is not separated, we need to make unique post
        # validation.
        already_exists = []
        unified_report_list = []
        for report_item in report_list + list(e.args):
            dto_obj = report_item.message.to_dto()
            if dto_obj.code not in (
                reports.codes.ID_ALREADY_EXISTS,
                reports.codes.RESOURCE_INSTANCE_ATTR_VALUE_NOT_UNIQUE,
            ):
                unified_report_list.append(report_item)
            elif (
                "id" in dto_obj.payload
                and dto_obj.payload["id"] not in already_exists
            ):
                unified_report_list.append(report_item)
                already_exists.append(dto_obj.payload["id"])
        report_list = unified_report_list

    report_processor.report_list(report_list)
    if report_processor.has_errors:
        raise LibraryError()

    # everything validated, let's set it up
    if env.is_cib_live:
        _prepare_pacemaker_remote_environment(
            env,
            report_processor,
            existing_target_list,
            new_target,
            node_name,
            skip_offline_nodes,
            allow_incomplete_distribution,
            allow_pacemaker_remote_service_fail,
        )
    else:
        report_processor.report_list(
            _reports_skip_new_node(node_name, "not_live_cib")
        )

    env.push_cib(wait_timeout=wait_timeout)
    if wait_timeout >= 0:
        _ensure_resource_running(env, remote_resource_element.attrib["id"])


def node_add_guest(  # noqa: PLR0912, PLR0915
    env: LibraryEnvironment,
    node_name,
    resource_id,
    options,
    skip_offline_nodes=False,
    allow_incomplete_distribution=False,
    allow_pacemaker_remote_service_fail=False,
    wait: WaitType = False,
):
    # pylint: disable=too-many-branches
    # pylint: disable=too-many-locals
    # pylint: disable=too-many-statements
    """
    Make a guest node from the specified resource

    LibraryEnvironment env -- provides all for communication with externals
    string node_name -- name of the guest node
    string resource_id -- specifies resource that should become a guest node
    dict options -- guest node options (remote-port, remote-addr,
        remote-connect-timeout)
    bool skip_offline_nodes -- if True, ignore when some nodes are offline
    bool allow_incomplete_distribution -- if True, allow this command to
        finish successfully even if file distribution did not succeed
    bool allow_pacemaker_remote_service_fail -- if True, allow this command to
        finish successfully even if starting/enabling pacemaker_remote did not
        succeed
    mixed wait -- a flag for controlling waiting for pacemaker idle mechanism
    """
    if wait is not False:
        # deprecated in the first version of 0.12
        env.report_processor.report(
            reports.ReportItem.deprecation(
                reports.messages.ResourceWaitDeprecated()
            )
        )

    wait_timeout = env.ensure_wait_satisfiable(wait)

    report_processor = env.report_processor
    cib = env.get_cib()
    id_provider = IdProvider(cib)
    corosync_conf: Optional[CorosyncConfigFacade]
    if env.is_cib_live:
        corosync_conf = env.get_corosync_conf()
    else:
        corosync_conf = None
        report_processor.report(
            reports.ReportItem.info(
                reports.messages.CorosyncNodeConflictCheckSkipped(
                    reports.const.REASON_NOT_LIVE_CIB,
                )
            )
        )
    (
        existing_nodes_names,
        existing_nodes_addrs,
        report_list,
    ) = get_existing_nodes_names_addrs(corosync_conf, cib)
    if env.is_cib_live:
        # We just reported corosync checks are going to be skipped so we
        # shouldn't complain about errors related to corosync nodes
        report_processor.report_list(report_list)

    existing_target_list = []
    if env.is_cib_live:
        target_factory = env.get_node_target_factory()
        existing_target_list, new_target_list = _get_targets_for_add(
            target_factory,
            report_processor,
            existing_nodes_names,
            [node_name],
            skip_offline_nodes,
        )
        new_target = new_target_list[0] if new_target_list else None
        # default remote-addr to an address from known-hosts
        if "remote-addr" not in options or options["remote-addr"] is None:
            if new_target:
                new_addr = new_target.first_addr
                new_addr_source = (
                    reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
                )
            else:
                new_addr = node_name
                new_addr_source = reports.const.DEFAULT_ADDRESS_SOURCE_HOST_NAME
            options["remote-addr"] = new_addr
            report_processor.report(
                reports.ReportItem.info(
                    reports.messages.UsingDefaultAddressForHost(
                        node_name, new_addr, new_addr_source
                    )
                )
            )
    # default remote-addr to an address from known-hosts
    elif "remote-addr" not in options or options["remote-addr"] is None:
        known_hosts = env.get_known_hosts([node_name])
        if known_hosts:
            new_addr = known_hosts[0].dest.addr
            new_addr_source = reports.const.DEFAULT_ADDRESS_SOURCE_KNOWN_HOSTS
        else:
            new_addr = node_name
            new_addr_source = reports.const.DEFAULT_ADDRESS_SOURCE_HOST_NAME
        options["remote-addr"] = new_addr
        report_processor.report(
            reports.ReportItem.info(
                reports.messages.UsingDefaultAddressForHost(
                    node_name, new_addr, new_addr_source
                )
            )
        )

    # validate inputs
    report_list = guest_node.validate_set_as_guest(
        cib, existing_nodes_names, existing_nodes_addrs, node_name, options
    )
    searcher = ElementSearcher(primitive.TAG, resource_id, get_resources(cib))
    if searcher.element_found():
        resource_element = searcher.get_element()
        report_list.extend(guest_node.validate_is_not_guest(resource_element))
    else:
        report_list.extend(searcher.get_errors())

    report_processor.report_list(report_list)
    if report_processor.has_errors:
        raise LibraryError()

    # everything validated, let's set it up
    guest_node.set_as_guest(
        resource_element,
        id_provider,
        node_name,
        options.get("remote-addr", None),
        options.get("remote-port", None),
        options.get("remote-connect-timeout", None),
    )

    if env.is_cib_live:
        _prepare_pacemaker_remote_environment(
            env,
            report_processor,
            existing_target_list,
            new_target,
            node_name,
            skip_offline_nodes,
            allow_incomplete_distribution,
            allow_pacemaker_remote_service_fail,
        )
    else:
        report_processor.report_list(
            _reports_skip_new_node(node_name, "not_live_cib")
        )

    env.push_cib(wait_timeout=wait_timeout)
    if wait_timeout >= 0:
        _ensure_resource_running(env, resource_id)


def _find_resources_to_remove(
    cib: _Element,
    node_type: str,
    node_identifier: str,
    allow_remove_multiple_nodes: bool,
    find_resources: Callable[[_Element, str], list[_Element]],
) -> tuple[list[_Element], reports.ReportItemList]:
    resource_element_list = find_resources(get_resources(cib), node_identifier)

    report_list = []
    if not resource_element_list:
        report_list.append(
            reports.ReportItem.error(
                reports.messages.NodeNotFound(node_identifier, [node_type])
            )
        )
    if len(resource_element_list) > 1:
        report_list.append(
            reports.ReportItem(
                severity=reports.item.get_severity(
                    reports.codes.FORCE,
                    allow_remove_multiple_nodes,
                ),
                message=reports.messages.MultipleResultsFound(
                    "resource",
                    [
                        str(resource.attrib["id"])
                        for resource in resource_element_list
                    ],
                    node_identifier,
                ),
            )
        )

    return resource_element_list, report_list


def _destroy_pcmk_remote_env(
    env, node_names_list, skip_offline_nodes, allow_fails
):
    actions = node_communication_format.create_pcmk_remote_actions(
        [
            "stop",
            "disable",
        ]
    )
    files = {
        "pacemaker_remote authkey": {"type": "pcmk_remote_authkey"},
    }
    target_list = env.get_node_target_factory().get_target_list(
        node_names_list,
        skip_non_existing=skip_offline_nodes,
    )

    com_cmd = ServiceAction(
        env.report_processor,
        actions,
        skip_offline_targets=skip_offline_nodes,
        allow_fails=allow_fails,
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)

    com_cmd = RemoveFiles(
        env.report_processor,
        files,
        skip_offline_targets=skip_offline_nodes,
        allow_fails=allow_fails,
    )
    com_cmd.set_targets(target_list)
    run_and_raise(env.get_node_communicator(), com_cmd)


def _report_skip_live_parts_in_remove(node_names_list):
    return [
        reports.ReportItem.info(
            reports.messages.ServiceCommandsOnNodesSkipped(
                reports.const.REASON_NOT_LIVE_CIB,
                ["pacemaker_remote stop", "pacemaker_remote disable"],
                node_names_list,
            )
        ),
        reports.ReportItem.info(
            reports.messages.FilesRemoveFromNodesSkipped(
                reports.const.REASON_NOT_LIVE_CIB,
                ["pacemaker authkey"],
                node_names_list,
            )
        ),
    ]


def get_resource_ids(
    env: LibraryEnvironment, node_identifier: str
) -> list[str]:
    """
    Return resource ids of resources that represent the given node_identifier

    env -- provides all for communication with externals
    node_identifier -- node name or hostname
    """
    return [
        str(element.attrib["id"])
        for element in remote_node.find_node_resources(
            get_resources(env.get_cib()), node_identifier
        )
    ]


def node_remove_remote(
    env: LibraryEnvironment,
    node_identifier: str,
    force_flags: reports.types.ForceFlags = (),
):
    """
    remove a resource representing remote node and destroy remote node

    env -- provides all for communication with externals
    node_identifier -- node name or hostname
    force_flags -- list of flags codes
    """
    cib = env.get_cib()
    report_processor = env.report_processor
    force = reports.codes.FORCE in force_flags

    resource_element_list, report_list = _find_resources_to_remove(
        cib,
        "remote",
        node_identifier,
        allow_remove_multiple_nodes=force,
        find_resources=remote_node.find_node_resources,
    )
    if report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    node_names_list = sorted(
        {
            remote_node.get_node_name_from_resource(node_element)
            for node_element in resource_element_list
        }
    )

    resource_ids = [str(el.attrib["id"]) for el in resource_element_list]
    elements_to_remove = ElementsToRemove(cib, resource_ids)

    if env.is_cib_live:
        report_processor.report_list(
            ensure_resources_stopped(
                env.get_cluster_state(), resource_ids, force_flags
            )
        )
    else:
        report_processor.report(
            reports.ReportItem.warning(
                reports.messages.StoppedResourcesBeforeDeleteCheckSkipped(
                    resource_ids, reports.const.REASON_NOT_LIVE_CIB
                )
            )
        )
    if env.report_processor.has_errors:
        raise LibraryError()

    if not env.is_cib_live:
        report_processor.report_list(
            _report_skip_live_parts_in_remove(node_names_list)
        )
    else:
        _destroy_pcmk_remote_env(
            env,
            node_names_list,
            skip_offline_nodes=reports.codes.SKIP_OFFLINE_NODES in force_flags,
            allow_fails=force,
        )

    # the user could have provided hostname, so we want to show them which
    # resources are going to be removed
    report_processor.report(
        reports.ReportItem.info(
            reports.messages.CibRemoveResources(resource_ids)
        )
    )
    report_processor.report_list(
        elements_to_remove.dependant_elements.to_reports()
    )
    report_processor.report_list(
        elements_to_remove.element_references.to_reports()
    )

    remove_specified_elements(cib, elements_to_remove)
    env.push_cib()

    # remove node from pcmk caches
    if env.is_cib_live:
        for node_name in node_names_list:
            remove_node(env.cmd_runner(), node_name)
    else:
        report_processor.report(
            reports.ReportItem.warning(
                reports.messages.NodeRemoveInPacemakerSkipped(
                    reports.const.REASON_NOT_LIVE_CIB, node_names_list
                )
            )
        )


def node_remove_guest(
    env: LibraryEnvironment,
    node_identifier,
    skip_offline_nodes=False,
    allow_remove_multiple_nodes=False,
    allow_pacemaker_remote_service_fail=False,
    wait: WaitType = False,
):
    """
    remove a resource representing remote node and destroy remote node

    LibraryEnvironment env provides all for communication with externals
    string node_identifier -- node name, hostname or resource id
    bool skip_offline_nodes -- a flag for ignoring when some nodes are offline
    bool allow_remove_multiple_nodes -- is a flag for allowing
        remove unexpected multiple occurrence of remote node for node_identifier
    bool allow_pacemaker_remote_service_fail -- is a flag for allowing
        successfully finish this command even if stoping/disabling
        pacemaker_remote not succeeded
    """
    wait_timeout = env.ensure_wait_satisfiable(wait)
    cib = env.get_cib()

    resource_element_list, report_list = _find_resources_to_remove(
        cib,
        "guest",
        node_identifier,
        allow_remove_multiple_nodes,
        guest_node.find_node_resources,
    )
    if env.report_processor.report_list(report_list).has_errors:
        raise LibraryError()

    node_names_list = sorted(
        {
            guest_node.get_node_name_from_resource(node_element)
            for node_element in resource_element_list
        }
    )

    if not env.is_cib_live:
        env.report_processor.report_list(
            _report_skip_live_parts_in_remove(node_names_list)
        )
    else:
        _destroy_pcmk_remote_env(
            env,
            node_names_list,
            skip_offline_nodes,
            allow_pacemaker_remote_service_fail,
        )

    for resource_element in resource_element_list:
        guest_node.unset_guest(resource_element)

    env.push_cib(wait_timeout=wait_timeout)

    # remove node from pcmk caches
    if env.is_cib_live:
        for node_name in node_names_list:
            remove_node(env.cmd_runner(), node_name)
    else:
        env.report_processor.report(
            reports.ReportItem.warning(
                reports.messages.NodeRemoveInPacemakerSkipped(
                    reports.const.REASON_NOT_LIVE_CIB, node_names_list
                )
            )
        )
