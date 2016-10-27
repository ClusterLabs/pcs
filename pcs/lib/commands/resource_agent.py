from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import resource_agent


def list_standards(lib_env):
    """
    List resource agents standards (ocf, lsb, ... ) on the local host
    """
    return resource_agent.list_resource_agents_standards(lib_env.cmd_runner())


def list_ocf_providers(lib_env):
    """
    List resource agents ocf providers on the local host
    """
    return resource_agent.list_resource_agents_ocf_providers(
        lib_env.cmd_runner()
    )


def list_agents_for_standard_and_provider(lib_env, standard_provider=None):
    """
    List resource agents for specified standard on the local host
    string standard_provider standard[:provider], e.g. None, ocf, ocf:pacemaker
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
    return sorted(
        agents,
        # works with both str and unicode in both python 2 and 3
        key=lambda x: x.lower()
    )


def list_agents(lib_env, describe=True, search=None):
    """
    List all resource agents on the local host, optionally filtered and
        described
    bool describe load and return agents' description as well
    string search return only agents which name contains this string
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
    agent_names.sort(
        # works with both str and unicode in both python 2 and 3
        key=lambda x: x.lower()
    )
    return _complete_agent_list(
        runner,
        agent_names,
        describe,
        search,
        resource_agent.ResourceAgent
    )


def _complete_agent_list(
    runner, agent_names, describe, search, metadata_class
):
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
            if describe:
                agent_list.append(agent_metadata.get_description_info())
            else:
                agent_list.append(agent_metadata.get_name_info())
        except resource_agent.UnableToGetAgentMetadata:
            # if we cannot get valid metadata, it's not a resource agent and
            # we don't return it in the list
            pass
    return agent_list


def describe_agent(lib_env, agent_name):
    """
    Get agent's description (metadata) in a structure
    string agent_name name of the agent
    """
    agent = resource_agent.find_valid_resource_agent_by_name(
        lib_env.report_processor,
        lib_env.cmd_runner(),
        agent_name,
    )
    return agent.get_full_info()
