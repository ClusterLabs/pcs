from typing import Any, Dict, Iterable, List, Optional, Type

from pcs.common.interface.dto import to_dict
from pcs.lib import resource_agent
from pcs.lib.env import LibraryEnvironment
from pcs.lib.external import CommandRunner


def list_standards(lib_env: LibraryEnvironment) -> List[str]:
    """
    List resource agents standards (ocf, lsb, ... ) on the local host
    """
    return resource_agent.list_resource_agents_standards(lib_env.cmd_runner())


def list_ocf_providers(lib_env: LibraryEnvironment) -> List[str]:
    """
    List resource agents ocf providers on the local host
    """
    return resource_agent.list_resource_agents_ocf_providers(
        lib_env.cmd_runner()
    )


def list_agents_for_standard_and_provider(
    lib_env: LibraryEnvironment, standard_provider: Optional[str] = None
) -> List[str]:
    """
    List resource agents for specified standard on the local host

    standard_provider -- standard[:provider], e.g. None, ocf, ocf:pacemaker
    """
    if standard_provider:
        standards = [standard_provider]
    else:
        standards = resource_agent.list_resource_agents_standards(
            lib_env.cmd_runner()
        )
    agents = []
    for std in standards:
        agents += resource_agent.list_resource_agents(lib_env.cmd_runner(), std)
    return sorted(agents, key=str.lower)


# TODO return a list of DTOs
# for now, it is transformed to a list of dicts for backward compatibility
def list_agents(
    lib_env: LibraryEnvironment,
    describe: bool = True,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List all resource agents on the local host, optionally filtered and
        described

    describe -- load and return agents' description as well
    search -- return only agents which name contains this string
    """
    runner = lib_env.cmd_runner()

    # list agents for all standards and providers
    agent_names = []
    for std in resource_agent.list_resource_agents_standards_and_providers(
        runner
    ):
        agent_names += [
            "{0}:{1}".format(std, agent)
            for agent in resource_agent.list_resource_agents(runner, std)
        ]
    return _complete_agent_list(
        runner,
        sorted(agent_names, key=str.lower),
        describe,
        search,
        resource_agent.ResourceAgent,
    )


def _complete_agent_list(
    runner: CommandRunner,
    agent_names: Iterable[str],
    describe: bool,
    search: Optional[str],
    metadata_class: Type[resource_agent.CrmAgent],
) -> List[Dict[str, Any]]:
    # filter agents by name if requested
    if search:
        search_lower = search.lower()
        agent_names = [
            name for name in agent_names if search_lower in name.lower()
        ]

    # complete the output and load descriptions if requested
    agent_list = []
    for name in agent_names:
        try:
            agent_metadata = metadata_class(runner, name)
            metadata_dto = (
                agent_metadata.get_full_info()
                if describe
                else agent_metadata.get_name_info()
            )
            agent_list.append(to_dict(metadata_dto))
        except resource_agent.ResourceAgentError:
            # we don't return it in the list:
            #
            # UnableToGetAgentMetadata - if we cannot get valid metadata, it's
            # not a resource agent
            #
            # InvalidResourceAgentName - invalid name cannot be used with a new
            # resource. The list of names is gained from "crm_resource" whilst
            # pcs is doing the validation. So there can be a name that pcs does
            # not recognize as valid.
            #
            # Providing a warning is not the way (currently). Other components
            # read this list and do not expect warnings there. Using the stderr
            # (to separate warnings) is currently difficult.
            pass
    return agent_list


# TODO return aDTO
# for now, it is transformed to a dict for backward compatibility
def describe_agent(
    lib_env: LibraryEnvironment, agent_name: str
) -> Dict[str, Any]:
    """
    Get agent's description (metadata) in a structure

    agent_name -- name of the agent
    """
    agent = resource_agent.find_valid_resource_agent_by_name(
        lib_env.report_processor,
        lib_env.cmd_runner(),
        agent_name,
        absent_agent_supported=False,
    )
    return to_dict(agent.get_full_info())
