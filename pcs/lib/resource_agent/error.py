from pcs.common import reports
from pcs.common.types import StringCollection

from . import const

_DEFAULT_SEVERITY = reports.ReportItemSeverity.error()


class ResourceAgentError(Exception):
    def __init__(self, agent_name: str):
        super().__init__()
        self.agent_name = agent_name


class AgentNameGuessFoundMoreThanOne(ResourceAgentError):
    def __init__(self, searched_name: str, names_found: StringCollection):
        super().__init__(searched_name)
        self.names_found = names_found

    @property
    def searched_name(self) -> str:
        return self.agent_name


class AgentNameGuessFoundNone(ResourceAgentError):
    @property
    def searched_name(self) -> str:
        return self.agent_name


class InvalidResourceAgentName(ResourceAgentError):
    pass


class UnableToGetAgentMetadata(ResourceAgentError):
    def __init__(self, agent_name: str, message: str):
        super().__init__(agent_name)
        self.message = message


class UnsupportedOcfVersion(ResourceAgentError):
    def __init__(self, agent_name: str, ocf_version: str):
        super().__init__(agent_name)
        self.ocf_version = ocf_version


def resource_agent_error_to_report_item(
    e: ResourceAgentError,
    severity: reports.ReportItemSeverity = _DEFAULT_SEVERITY,
    is_stonith: bool = False,
) -> reports.ReportItem:
    """
    Transform a ResourceAgentError to a ReportItem
    """
    message: reports.item.ReportItemMessage = (
        reports.messages.AgentGenericError(e.agent_name)
    )
    if isinstance(e, AgentNameGuessFoundMoreThanOne):
        message = reports.messages.AgentNameGuessFoundMoreThanOne(
            e.searched_name, sorted(e.names_found)
        )
    elif isinstance(e, AgentNameGuessFoundNone):
        message = reports.messages.AgentNameGuessFoundNone(e.searched_name)
    elif isinstance(e, InvalidResourceAgentName):
        if is_stonith:
            message = reports.messages.InvalidStonithAgentName(e.agent_name)
        else:
            message = reports.messages.InvalidResourceAgentName(e.agent_name)
    elif isinstance(e, UnableToGetAgentMetadata):
        message = reports.messages.UnableToGetAgentMetadata(
            e.agent_name, e.message
        )
    elif isinstance(e, UnsupportedOcfVersion):
        message = reports.messages.AgentImplementsUnsupportedOcfVersion(
            e.agent_name,
            e.ocf_version,
            sorted(const.SUPPORTED_OCF_VERSIONS),
        )
    return reports.ReportItem(severity, message)
