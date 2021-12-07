from typing import Any, Dict, List, Optional

from pcs.lib.commands.resource_agent import (
    _agent_metadata_to_dict,
    _complete_agent_list,
    _get_agent_names,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError
from pcs.lib.resource_agent import (
    resource_agent_error_to_report_item,
    InvalidResourceAgentName,
    ResourceAgentError,
    ResourceAgentFacadeFactory,
    ResourceAgentName,
    StandardProviderTuple,
)


# deprecated: use pcs.commands.resource_agent.get_agent_list instead
# for now, it is transformed to a list of dicts for backward compatibility
def list_agents(
    lib_env: LibraryEnvironment,
    describe: bool = True,
    search: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    List all stonith agents on the local host, optionally filtered and described

    describe -- load and return agents' description as well
    search -- return only agents which name contains this string
    """
    runner = lib_env.cmd_runner()
    return _complete_agent_list(
        runner,
        lib_env.report_processor,
        sorted(
            _get_agent_names(runner, StandardProviderTuple("stonith")),
            key=lambda item: item.full_name,
        ),
        describe,
        search,
    )


# deprecated: use pcs.commands.resource_agent.get_agent_metadata instead
# for now, it is transformed to a dict for backward compatibility
def describe_agent(
    lib_env: LibraryEnvironment, agent_name: str
) -> Dict[str, Any]:
    """
    Get agent's description (metadata) in a structure

    agent_name -- name of the agent (not containing "stonith:" prefix)
    """
    runner = lib_env.cmd_runner()
    agent_factory = ResourceAgentFacadeFactory(runner, lib_env.report_processor)
    try:
        if ":" in agent_name:
            raise InvalidResourceAgentName(agent_name)
        return _agent_metadata_to_dict(
            agent_factory.facade_from_parsed_name(
                ResourceAgentName("stonith", None, agent_name)
            ).metadata,
            describe=True,
        )
    except ResourceAgentError as e:
        lib_env.report_processor.report(
            resource_agent_error_to_report_item(e, is_stonith=True)
        )
        raise LibraryError() from e
