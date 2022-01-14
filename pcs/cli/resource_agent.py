from typing import List
from pcs.common import reports
from pcs.common.resource_agent.dto import ResourceAgentNameDto
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.tools import print_to_stderr


def get_resource_agent_full_name(agent_name: ResourceAgentNameDto) -> str:
    provider = f":{agent_name.provider}" if agent_name.provider else ""
    return f"{agent_name.standard}{provider}:{agent_name.type}"


def find_single_agent(
    agent_names: List[ResourceAgentNameDto], to_find: str
) -> ResourceAgentNameDto:
    to_find_normalized = to_find.lower()
    matches = [
        agent_name
        for agent_name in agent_names
        if agent_name.type.lower() == to_find_normalized
    ]
    if len(matches) == 1:
        print_to_stderr(
            reports.messages.AgentNameGuessed(
                to_find, get_resource_agent_full_name(matches[0])
            ).message
        )
        return matches[0]

    report_msg: reports.item.ReportItemMessage
    if matches:
        report_msg = reports.messages.AgentNameGuessFoundMoreThanOne(
            to_find, sorted(map(get_resource_agent_full_name, matches))
        )
    else:
        report_msg = reports.messages.AgentNameGuessFoundNone(to_find)
    raise CmdLineInputError(report_msg.message)
