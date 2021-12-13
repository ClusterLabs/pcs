from typing import Any, Dict, Iterable, List, Optional

from pcs.common.interface.dto import to_dict
from pcs.common.reports import ReportProcessor
from pcs.lib.cib.resource.agent import (
    action_to_operation,
    complete_operations_options,
    get_default_operations,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.external import CommandRunner
from pcs.lib.resource_agent import (
    find_one_resource_agent_by_type,
    list_resource_agents,
    list_resource_agents_ocf_providers,
    list_resource_agents_standards,
    list_resource_agents_standards_and_providers,
    resource_agent_error_to_report_item,
    split_resource_agent_name,
    ListResourceAgentNameDto,
    ResourceAgentError,
    ResourceAgentFacadeFactory,
    ResourceAgentMetadata,
    ResourceAgentMetadataDto,
    ResourceAgentName,
    ResourceAgentNameDto,
    StandardProviderTuple,
)
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


# backward compatibility layer - export agent metadata in the legacy format
def _agent_metadata_to_dict(
    agent: ResourceAgentMetadata, describe: bool = False
) -> Dict[str, str]:
    agent_dto = agent.to_dto()
    agent_dict = to_dict(agent_dto)
    del agent_dict["name"]
    agent_dict["name"] = agent.name.full_name
    agent_dict["standard"] = agent.name.standard
    agent_dict["provider"] = agent.name.provider
    agent_dict["type"] = agent.name.type

    agent_dict["actions"] = [
        action_to_operation(action, keep_extra_keys=True)
        for action in agent_dto.actions
    ]
    agent_dict["default_actions"] = (
        complete_operations_options(
            get_default_operations(agent, keep_extra_keys=True)
        )
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
        except ResourceAgentError:
            # Reports are still printed to stdout therefore we cannot report
            # this as it would end up in the same output as # list of agents.
            pass
    return agent_list


def get_agent_metadata(
    lib_env: LibraryEnvironment, agent_name: ResourceAgentNameDto
) -> ResourceAgentMetadataDto:
    """
    Return agent's metadata

    agent_name -- name of the agent
    """
    runner = lib_env.cmd_runner()
    report_processor = lib_env.report_processor
    agent_factory = ResourceAgentFacadeFactory(runner, report_processor)
    try:
        return agent_factory.facade_from_parsed_name(
            ResourceAgentName.from_dto(agent_name)
        ).metadata.to_dto()
    except ResourceAgentError as e:
        lib_env.report_processor.report(resource_agent_error_to_report_item(e))
        raise LibraryError() from e


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
