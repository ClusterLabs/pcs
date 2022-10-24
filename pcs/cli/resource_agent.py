from typing import List

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.tools import print_to_stderr
from pcs.common import reports
from pcs.common.resource_agent.dto import (
    ResourceAgentNameDto,
    get_resource_agent_full_name,
)


def is_stonith(agent_name: ResourceAgentNameDto) -> bool:
    return agent_name.standard == "stonith"


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
