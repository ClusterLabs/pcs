from typing import List

from pcs import settings
from pcs.common import reports
from pcs.common.str_tools import split_multiline
from pcs.lib.external import CommandRunner

from .error import (
    AgentNameGuessFoundMoreThanOne,
    AgentNameGuessFoundNone,
)
from .types import (
    ResourceAgentName,
    StandardProviderTuple,
)

_IGNORED_AGENTS = frozenset(
    [
        "fence_ack_manual",
        "fence_check",
        "fence_kdump_send",
        "fence_legacy",
        "fence_na",
        "fence_node",
        "fence_nss_wrapper",
        "fence_pcmk",
        "fence_sanlockd",
        "fence_tool",
        "fence_virtd",
        "fence_vmware_helper",
    ]
)


def list_resource_agents_standards(runner: CommandRunner) -> List[str]:
    """
    Return a list of resource agents standards (ocf, lsb, ...) on the local host
    """
    # retval is the number of standards found
    stdout, dummy_stderr, dummy_retval = runner.run(
        [settings.crm_resource_exec, "--list-standards"]
    )
    return sorted(set(split_multiline(stdout)), key=str.lower)


def list_resource_agents_ocf_providers(runner: CommandRunner) -> List[str]:
    """
    Return a list of resource agents ocf providers on the local host
    """
    # retval is the number of providers found
    stdout, dummy_stderr, dummy_retval = runner.run(
        [settings.crm_resource_exec, "--list-ocf-providers"]
    )
    return sorted(set(split_multiline(stdout)), key=str.lower)


def list_resource_agents_standards_and_providers(
    runner: CommandRunner,
) -> List[StandardProviderTuple]:
    """
    Return a list of all standard[:provider] on the local host
    """
    result = []
    for standard in list_resource_agents_standards(runner):
        if standard == "ocf":
            # do not list "ocf" when we're going to list "ocf:{provider}"
            result.extend(
                [
                    StandardProviderTuple(standard, provider)
                    for provider in list_resource_agents_ocf_providers(runner)
                ]
            )
        else:
            result.append(StandardProviderTuple(standard))
    return sorted(result)


def list_resource_agents(
    runner: CommandRunner, standard_provider: StandardProviderTuple
) -> List[str]:
    """
    Return a list of resource agents of the specified standard on the local host

    standard_provider -- standard[:provider], e.g. lsb, ocf, ocf:pacemaker
    """
    # retval is 0 on success, anything else when no agents were found
    stdout, dummy_stderr, retval = runner.run(
        [
            settings.crm_resource_exec,
            "--list-agents",
            (
                f"{standard_provider.standard}:{standard_provider.provider}"
                if standard_provider.provider
                else standard_provider.standard
            ),
        ]
    )
    return (
        sorted(set(split_multiline(stdout)) - _IGNORED_AGENTS, key=str.lower)
        if retval == 0
        else []
    )


### find an agent by its name


def find_one_resource_agent_by_type(
    runner: CommandRunner,
    report_processor: reports.ReportProcessor,
    type_: str,
) -> ResourceAgentName:
    """
    Get one resource agent with the specified type from all standards:providers

    type_ -- last part of an agent's name
    """
    possible_names = _find_all_resource_agents_by_type(runner, type_)
    if len(possible_names) == 1:
        report_processor.report(
            reports.ReportItem.info(
                reports.messages.AgentNameGuessed(
                    type_, possible_names[0].full_name
                )
            )
        )
        return possible_names[0]
    if possible_names:
        raise AgentNameGuessFoundMoreThanOne(
            type_, sorted([name.full_name for name in possible_names])
        )
    raise AgentNameGuessFoundNone(type_)


def _find_all_resource_agents_by_type(
    runner: CommandRunner, type_: str
) -> List[ResourceAgentName]:
    """
    List resource agents with the specified type from all standards:providers

    type_ -- last part of an agent name
    """
    type_lower = type_.lower()
    possible_names = []
    for std_provider in list_resource_agents_standards_and_providers(runner):
        for existing_type in list_resource_agents(runner, std_provider):
            if type_lower == existing_type.lower():
                possible_names.append(
                    ResourceAgentName(
                        std_provider.standard,
                        std_provider.provider,
                        existing_type,
                    )
                )
    return possible_names
