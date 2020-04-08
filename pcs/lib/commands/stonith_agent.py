from pcs.lib import resource_agent
from pcs.lib.commands.resource_agent import _complete_agent_list


def list_agents(lib_env, describe=True, search=None):
    """
    List all stonith agents on the local host, optionally filtered and described
    bool describe load and return agents' description as well
    string search return only agents which name contains this string
    """
    runner = lib_env.cmd_runner()
    agent_names = resource_agent.list_stonith_agents(runner)
    return _complete_agent_list(
        runner, agent_names, describe, search, resource_agent.StonithAgent
    )


def describe_agent(lib_env, agent_name):
    """
    Get agent's description (metadata) in a structure
    string agent_name name of the agent (not containing "stonith:" prefix)
    """
    agent = resource_agent.find_valid_stonith_agent_by_name(
        lib_env.report_processor,
        lib_env.cmd_runner(),
        agent_name,
        absent_agent_supported=False,
    )
    return agent.get_full_info()
