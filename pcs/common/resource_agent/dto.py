from dataclasses import dataclass

from pcs.common.interface.dto import DataTransferObject


@dataclass(frozen=True)
class ResourceAgentNameDto(DataTransferObject):
    standard: str
    provider: str | None
    type: str


def get_resource_agent_full_name(agent_name: ResourceAgentNameDto) -> str:
    return ":".join(
        filter(
            None, [agent_name.standard, agent_name.provider, agent_name.type]
        )
    )


@dataclass(frozen=True)
class ListResourceAgentNameDto(DataTransferObject):
    names: list[ResourceAgentNameDto]


@dataclass(frozen=True)
class ResourceAgentActionDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes

    # (start, stop, promote...), mandatory by both OCF 1.0 and 1.1
    name: str
    # mandatory by both OCF 1.0 and 1.1, sometimes not defined by agents
    timeout: str | None
    # optional by both OCF 1.0 and 1.1
    interval: str | None
    # optional by OCF 1.1
    # not allowed by OCF 1.0, defined in OCF 1.0 agents anyway
    role: str | None
    # OCF name: 'start-delay', optional by both OCF 1.0 and 1.1
    start_delay: str | None
    # optional by both OCF 1.0 and 1.1
    depth: str | None
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    automatic: bool
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    on_target: bool


@dataclass(frozen=True)
class ResourceAgentParameterDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes

    # name of the parameter
    name: str
    # short description
    shortdesc: str | None
    # long description
    longdesc: str | None
    # data type of the parameter
    type: str
    # default value of the parameter
    default: str | None
    # allowed values, only defined if type == 'select'
    enum_values: list[str] | None
    # True if it is a required parameter, False otherwise
    required: bool
    # True if the parameter is meant for advanced users
    advanced: bool
    # True if the parameter is deprecated, False otherwise
    deprecated: bool
    # list of parameters deprecating this one
    deprecated_by: list[str]
    # text describing / explaining the deprecation
    deprecated_desc: str | None
    # should the parameter's value be unique across same agent resources?
    unique_group: str | None
    # changing this parameter's value triggers a reload instead of a restart
    reloadable: bool


@dataclass(frozen=True)
class ResourceAgentMetadataDto(DataTransferObject):
    name: ResourceAgentNameDto
    shortdesc: str | None
    longdesc: str | None
    parameters: list[ResourceAgentParameterDto]
    actions: list[ResourceAgentActionDto]


@dataclass(frozen=True)
class ResourceMetaAttributesMetadataDto(DataTransferObject):
    name: str
    parameters: list[ResourceAgentParameterDto]
