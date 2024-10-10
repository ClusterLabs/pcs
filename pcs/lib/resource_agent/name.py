import re

from . import const
from .error import InvalidResourceAgentName
from .types import (
    ResourceAgentMetadata,
    ResourceAgentName,
)


def split_resource_agent_name(full_agent_name: str) -> ResourceAgentName:
    """
    Parse a resource agent name string to a structure

    full_agent_name -- agent name to parse
    """
    # Full_agent_name could be for example "systemd:lvm2-pvscan@252:2".
    # Note the second colon is not a separator between a provider and a type.
    # This regexp only matches systemd and service agents with instances.
    # Systemd and service agents without instances are matched by a generic
    # regexp below.
    match = re.match(
        "^(?P<standard>systemd|service):(?P<type>[^:@]+@.*)$",
        full_agent_name,
    )
    if match:
        return ResourceAgentName(
            match.group("standard"), None, match.group("type")
        )

    # This allows even bad combinations like "systemd:provider:agent" or
    # "ocf:agent". Those are caught by checks bellow to keep the regexp simple.
    match = re.match(
        "^(?P<standard>[^:]+)(:(?P<provider>[^:]+))?:(?P<type>[^:]+)$",
        full_agent_name,
    )
    if not match:
        raise InvalidResourceAgentName(full_agent_name)

    standard = match.group("standard")
    provider = match.group("provider") if match.group("provider") else None
    agent_type = match.group("type")

    # These are all the standards valid in a CIB. To get a list of standards
    # supported by pacemaker in the local environment, use result of
    # "crm_resource --list-standards" or "list_resource_agents_standards"
    allowed_standards = {
        "heartbeat",
        "lsb",
        "ocf",
        "service",
        "stonith",
        "systemd",
    }
    if standard not in allowed_standards:
        raise InvalidResourceAgentName(full_agent_name)
    if standard == "ocf" and not provider:
        raise InvalidResourceAgentName(full_agent_name)
    if standard != "ocf" and provider:
        raise InvalidResourceAgentName(full_agent_name)

    return ResourceAgentName(standard, provider, agent_type)


def name_to_void_metadata(name: ResourceAgentName) -> ResourceAgentMetadata:
    """
    Create a non-existent agent metadata for a given agent name

    name -- agent name to put into agent metadata
    """
    return ResourceAgentMetadata(
        name,
        agent_exists=False,
        ocf_version=const.OCF_1_0,
        shortdesc=None,
        longdesc=None,
        parameters=[],
        actions=[],
    )
