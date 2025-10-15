from dataclasses import (
    dataclass,
    field,
)
from typing import (
    List,
    Optional,
    Sequence,
)

from pcs.common.interface.dto import (
    DataTransferObject,
    meta,
)


@dataclass(frozen=True)
class ResourceAgentNameDto(DataTransferObject):
    standard: str
    provider: Optional[str]
    type: str


def get_resource_agent_full_name(agent_name: ResourceAgentNameDto) -> str:
    return ":".join(
        filter(
            None, [agent_name.standard, agent_name.provider, agent_name.type]
        )
    )


@dataclass(frozen=True)
class ListResourceAgentNameDto(DataTransferObject):
    names: List[ResourceAgentNameDto]


@dataclass(frozen=True)
class ResourceAgentActionDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes

    # (start, stop, promote...), mandatory by both OCF 1.0 and 1.1
    name: str
    # mandatory by both OCF 1.0 and 1.1, sometimes not defined by agents
    timeout: Optional[str]
    # optional by both OCF 1.0 and 1.1
    interval: Optional[str]
    # optional by OCF 1.1
    # not allowed by OCF 1.0, defined in OCF 1.0 agents anyway
    role: Optional[str]
    # OCF name: 'start-delay', optional by both OCF 1.0 and 1.1
    start_delay: Optional[str] = field(metadata=meta(name="start-delay"))
    # optional by both OCF 1.0 and 1.1
    depth: Optional[str]
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
    shortdesc: Optional[str]
    # long description
    longdesc: Optional[str]
    # data type of the parameter
    type: str
    # default value of the parameter
    default: Optional[str]
    # allowed values, only defined if type == 'select'
    enum_values: Optional[List[str]]
    # True if it is a required parameter, False otherwise
    required: bool
    # True if the parameter is meant for advanced users
    advanced: bool
    # True if the parameter is deprecated, False otherwise
    deprecated: bool
    # list of parameters deprecating this one
    deprecated_by: List[str]
    # text describing / explaining the deprecation
    deprecated_desc: Optional[str]
    # should the parameter's value be unique across same agent resources?
    unique_group: Optional[str]
    # changing this parameter's value triggers a reload instead of a restart
    reloadable: bool


@dataclass(frozen=True)
class ResourceAgentMetadataDto(DataTransferObject):
    name: ResourceAgentNameDto
    shortdesc: Optional[str]
    longdesc: Optional[str]
    parameters: List[ResourceAgentParameterDto]
    actions: List[ResourceAgentActionDto]


@dataclass(frozen=True)
class ResourceMetaAttributesMetadataDto(DataTransferObject):
    metadata: Sequence[ResourceAgentParameterDto]
    is_fencing: bool
