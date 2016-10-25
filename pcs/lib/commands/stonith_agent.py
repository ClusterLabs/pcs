from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import resource_agent
from pcs.lib.commands.resource_agent import _complete_agent_list
from pcs.lib.errors import LibraryError


def list_agents(lib_env, describe=True, search=None):
    """
    List all stonith agents on the local host, optionally filtered and described
    bool describe load and return agents' description as well
    string search return only agents which name contains this string
    """
    runner = lib_env.cmd_runner()
    agent_names = resource_agent.list_stonith_agents(runner)
    return _complete_agent_list(
        runner,
        agent_names,
        describe,
        search,
        resource_agent.StonithAgent
    )


def describe_agent(lib_env, agent_name):
    """
    Get agent's description (metadata) in a structure
    string agent_name name of the agent (not containing "stonith:" prefix)
    """
    try:
        metadata = resource_agent.StonithAgent(
            lib_env.cmd_runner(),
            agent_name
        )
        return metadata.get_full_info()
    except resource_agent.ResourceAgentError as e:
        raise LibraryError(
            resource_agent.resource_agent_error_to_report_item(e)
        )

