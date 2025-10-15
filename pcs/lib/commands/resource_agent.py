from typing import (
    Any,
    Dict,
    Iterable,
    List,
    Optional,
    cast,
)

from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.resource.operations import (
    OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME,
    ListCibResourceOperationDto,
)
from pcs.common.reports import (
    ReportItemSeverity,
    ReportProcessor,
)
from pcs.lib.cib.resource.agent import (
    get_default_operations,
    operation_dto_to_legacy_dict,
)
from pcs.lib.cib.resource.operations import uniquify_operations_intervals
from pcs.lib.cib.resource.types import ResourceOperationOut
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.resource_agent import (
    ListResourceAgentNameDto,
    ResourceAgentActionDto,
    ResourceAgentError,
    ResourceAgentFacadeFactory,
    ResourceAgentMetadata,
    ResourceAgentMetadataDto,
    ResourceAgentName,
    ResourceAgentNameDto,
    ResourceMetaAttributesMetadataDto,
    StandardProviderTuple,
    find_one_resource_agent_by_type,
    get_crm_resource_metadata,
    list_resource_agents,
    list_resource_agents_ocf_providers,
    list_resource_agents_standards,
    list_resource_agents_standards_and_providers,
    resource_agent_error_to_report_item,
    split_resource_agent_name,
)
from pcs.lib.resource_agent import const as ra_const
from pcs.lib.resource_agent.name import name_to_void_metadata


def list_standards(lib_env: LibraryEnvironment) -> List[str]:
    """
    List resource agents standards (ocf, lsb, ... ) on the local host
    """
    return [
        standard
        for standard in list_resource_agents_standards(lib_env.cmd_runner())
        if standard != "stonith"
    ]


def list_ocf_providers(lib_env: LibraryEnvironment) -> List[str]:
    """
    List resource agents ocf providers on the local host
    """
    return list_resource_agents_ocf_providers(lib_env.cmd_runner())


def list_agents_for_standard_and_provider(
    lib_env: LibraryEnvironment, standard_provider: Optional[str] = None
) -> List[str]:
    """
    List resource agents for specified standard on the local host

    standard_provider -- standard[:provider], e.g. None, ocf, ocf:pacemaker
    """
    if standard_provider:
        if standard_provider[-1] == ":":
            standard_provider = standard_provider[:-1]
        std_prov_list = [
            StandardProviderTuple(*standard_provider.split(":", 1))
        ]
    else:
        std_prov_list = list_resource_agents_standards_and_providers(
            lib_env.cmd_runner()
        )
    agents = []
    for std_prov in std_prov_list:
        if std_prov.is_stonith:
            continue
        agents += list_resource_agents(lib_env.cmd_runner(), std_prov)
    return sorted(agents, key=str.lower)


# deprecated: use get_agent_list instead
# for now, it is transformed to a list of dicts for backward compatibility
def list_agents(
    lib_env: LibraryEnvironment,
    describe: bool = True,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List all resource agents on the local host, optionally filtered and
        described

    describe -- load and return agents' metadata as well
    search -- return only agents which name contains this string
    """
    runner = lib_env.cmd_runner()

    # list agents for all standards and providers
    agent_names = []
    for std_prov in list_resource_agents_standards_and_providers(runner):
        if std_prov.is_stonith:
            continue
        agent_names.extend(_get_agent_names(runner, std_prov))
    return _complete_agent_list(
        runner,
        lib_env.report_processor,
        sorted(agent_names, key=lambda item: item.full_name),
        describe,
        search,
    )


def _get_agent_names(
    runner: CommandRunner, standard_provider: StandardProviderTuple
) -> List[ResourceAgentName]:
    return [
        ResourceAgentName(
            standard_provider.standard, standard_provider.provider, agent
        )
        for agent in list_resource_agents(runner, standard_provider)
    ]


def get_agents_list(lib_env: LibraryEnvironment) -> ListResourceAgentNameDto:
    """
    List all resource agents on the local host
    """
    runner = lib_env.cmd_runner()
    agent_names = []
    for std_prov in list_resource_agents_standards_and_providers(runner):
        agent_names.extend(_get_agent_names(runner, std_prov))
    return ListResourceAgentNameDto(
        names=[
            name.to_dto()
            for name in sorted(agent_names, key=lambda item: item.full_name)
        ]
    )


def _action_to_operation(
    action: ResourceAgentActionDto,
) -> ResourceOperationOut:
    """
    Transform agent action data to CIB operation data
    """
    # This function bridges new agent framework, which provides data in
    # dataclasses, to old resource create code and transforms new data
    # structures to a format expected by the old code. When resource create is
    # overhauled, this function is expected to be removed.
    operation = {}
    for key, value in to_dict(action).items():
        if key == "depth":
            # "None" values are not put to CIB, so this keeps the key in place
            # while making sure it's not put in CIB. I'm not sure why depth ==
            # 0 is treated like this, but I keep it in place so the behavior is
            # the same as it has been for a long time. If pcs starts using
            # depth / OCF_CHECK_LEVEL or there is other demand for it, consider
            # changing this so value of "0" is put in CIB.
            operation[OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME] = (
                None if value == "0" else value
            )
        elif key == "start_delay":
            operation["start-delay"] = value
        else:
            operation[key] = value
    return cast(ResourceOperationOut, operation)


# backward compatibility layer - export agent metadata in the legacy format
def _agent_metadata_to_dict(
    agent: ResourceAgentMetadata, describe: bool = False
) -> Dict[str, Any]:
    agent_dto = agent.to_dto()
    agent_dict = to_dict(agent_dto)
    del agent_dict["name"]
    agent_dict["name"] = agent.name.full_name
    agent_dict["standard"] = agent.name.standard
    agent_dict["provider"] = agent.name.provider
    agent_dict["type"] = agent.name.type

    agent_dict["actions"] = [
        _action_to_operation(action) for action in agent_dto.actions
    ]
    operations_defaults = {
        OCF_CHECK_LEVEL_INSTANCE_ATTRIBUTE_NAME: None,
        "automatic": False,
        "on_target": False,
    }
    agent_dict["default_actions"] = (
        [
            operation_dto_to_legacy_dict(op, operations_defaults)
            for op in get_default_operations(agent)
        ]
        if describe
        else []
    )
    return agent_dict


def _complete_agent_list(
    runner: CommandRunner,
    report_processor: ReportProcessor,
    agent_names: Iterable[ResourceAgentName],
    describe: bool,
    search: Optional[str],
) -> List[Dict[str, Any]]:
    agent_factory = ResourceAgentFacadeFactory(runner, report_processor)
    search_lower = search.lower() if search else None
    agent_list = []
    for name in agent_names:
        if search_lower and search_lower not in name.full_name.lower():
            continue
        try:
            metadata = (
                agent_factory.facade_from_parsed_name(name).metadata
                if describe
                else name_to_void_metadata(name)
            )
            agent_list.append(_agent_metadata_to_dict(metadata, describe))
        except ResourceAgentError as e:
            report_processor.report(
                resource_agent_error_to_report_item(
                    e, ReportItemSeverity.warning()
                )
            )
    return agent_list


def _get_agent_metadata(
    runner: CommandRunner,
    report_processor: ReportProcessor,
    agent_name: ResourceAgentNameDto,
) -> ResourceAgentMetadata:
    agent_factory = ResourceAgentFacadeFactory(runner, report_processor)
    try:
        return agent_factory.facade_from_parsed_name(
            ResourceAgentName.from_dto(agent_name)
        ).metadata
    except ResourceAgentError as e:
        report_processor.report(resource_agent_error_to_report_item(e))
        raise LibraryError() from e


def get_agent_metadata(
    lib_env: LibraryEnvironment, agent_name: ResourceAgentNameDto
) -> ResourceAgentMetadataDto:
    """
    Return agent's metadata

    agent_name -- name of the agent
    """
    return _get_agent_metadata(
        lib_env.cmd_runner(),
        lib_env.report_processor,
        agent_name,
    ).to_dto()


# deprecated: use get_agent_metadata instead
# for now, it is transformed to a dict for backward compatibility
def describe_agent(
    lib_env: LibraryEnvironment, agent_name: str
) -> Dict[str, Any]:
    """
    Get agent's description (metadata) in a structure

    agent_name -- name of the agent
    """
    runner = lib_env.cmd_runner()
    report_processor = lib_env.report_processor
    agent_factory = ResourceAgentFacadeFactory(runner, report_processor)
    try:
        found_name = (
            split_resource_agent_name(agent_name)
            if ":" in agent_name
            else find_one_resource_agent_by_type(
                runner, report_processor, agent_name
            )
        )
        return _agent_metadata_to_dict(
            agent_factory.facade_from_parsed_name(found_name).metadata,
            describe=True,
        )
    except ResourceAgentError as e:
        lib_env.report_processor.report(resource_agent_error_to_report_item(e))
        raise LibraryError() from e


def get_agent_default_operations(
    lib_env: LibraryEnvironment,
    agent_name: ResourceAgentNameDto,
    necessary_only: bool = False,
) -> ListCibResourceOperationDto:
    report_list, operation_list = uniquify_operations_intervals(
        get_default_operations(
            _get_agent_metadata(
                lib_env.cmd_runner(), lib_env.report_processor, agent_name
            ),
            necessary_only,
        )
    )
    lib_env.report_processor.report_list(report_list)
    return ListCibResourceOperationDto(operations=operation_list)


def get_structured_agent_name(
    lib_env: LibraryEnvironment, agent_name: str
) -> ResourceAgentNameDto:
    # This is a temporary solution and should never be available via pcsd REST
    # API. The code for splitting an agent name will be eventually moved to cli
    # once all old commands that require this will be replaced and removed.
    try:
        return split_resource_agent_name(agent_name).to_dto()
    except ResourceAgentError as e:
        lib_env.report_processor.report(resource_agent_error_to_report_item(e))
        raise LibraryError() from e


def get_resource_meta_attributes_metadata(
    lib_env: LibraryEnvironment, is_fencing: bool
) -> ResourceMetaAttributesMetadataDto:
    """
    Return meta-attributes metadata for a resource

    is_fencing -- if True, get additional metadata for a fencing resource
    """
    try:
        metadata = get_crm_resource_metadata(
            lib_env.cmd_runner(), ra_const.PRIMITIVE_META, is_fencing=is_fencing
        )
    except ResourceAgentError as e:
        lib_env.report_processor.report(resource_agent_error_to_report_item(e))
        raise LibraryError() from e

    return ResourceMetaAttributesMetadataDto(
        metadata=[parameter.to_dto() for parameter in metadata.parameters],
        is_fencing=is_fencing,
    )
