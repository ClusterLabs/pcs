from typing import Any, Dict, List, Optional

from pcs.common.interface.dto import to_dict
from pcs.lib import resource_agent
from pcs.lib.commands.resource_agent import _complete_agent_list
from pcs.lib.env import LibraryEnvironment


# TODO return a list of DTOs
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
    agent_names = resource_agent.list_stonith_agents(runner)
    return _complete_agent_list(
        runner, agent_names, describe, search, resource_agent.StonithAgent
    )


# TODO return a DTO
# for now, it is transformed to a dict for backward compatibility
def describe_agent(
    lib_env: LibraryEnvironment, agent_name: str
) -> Dict[str, Any]:
    """
    Get agent's description (metadata) in a structure

    agent_name -- name of the agent (not containing "stonith:" prefix)
    """
    agent = resource_agent.find_valid_stonith_agent_by_name(
        lib_env.report_processor,
        lib_env.cmd_runner(),
        agent_name,
        absent_agent_supported=False,
    )
    return to_dict(agent.get_full_info())
