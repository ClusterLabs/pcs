from collections import defaultdict
from dataclasses import dataclass
from typing import (
    AbstractSet,
    List,
    Mapping,
    NewType,
    Optional,
)

from pcs.common.resource_agent.dto import (
    ResourceAgentActionDto,
    ResourceAgentMetadataDto,
    ResourceAgentNameDto,
    ResourceAgentParameterDto,
)

CrmAttrAgent = NewType("CrmAttrAgent", str)
CrmResourceAgent = NewType("CrmResourceAgent", str)
FakeAgentName = NewType("FakeAgentName", str)
OcfVersion = NewType("OcfVersion", str)
_FAKE_AGENT_STANDARD = "__pcmk_internal"


@dataclass(frozen=True)
class ResourceAgentName:
    standard: str
    provider: Optional[str]
    type: str

    @property
    def full_name(self) -> str:
        return ":".join(filter(None, [self.standard, self.provider, self.type]))

    @property
    def is_pcmk_fake_agent(self) -> bool:
        return self.standard == _FAKE_AGENT_STANDARD

    @property
    def is_stonith(self) -> bool:
        return self.standard == "stonith"

    @property
    def is_ocf(self) -> bool:
        return self.standard == "ocf"

    def to_dto(self) -> ResourceAgentNameDto:
        return ResourceAgentNameDto(
            standard=self.standard,
            provider=self.provider,
            type=self.type,
        )

    @classmethod
    def from_dto(cls, dto: ResourceAgentNameDto) -> "ResourceAgentName":
        return cls(
            dto.standard,
            dto.provider,
            dto.type,
        )


@dataclass(frozen=True)
class ResourceAgentActionOcf1_0:  # pylint: disable=invalid-name
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
    start_delay: Optional[str]
    # optional by both OCF 1.0 and 1.1
    depth: Optional[str]
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    automatic: Optional[str]
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    on_target: Optional[str]


@dataclass(frozen=True)
class ResourceAgentActionOcf1_1:  # pylint: disable=invalid-name
    # pylint: disable=too-many-instance-attributes

    # (start, stop, promote...), mandatory by both OCF 1.0 and 1.1
    name: str
    # mandatory by both OCF 1.0 and 1.1, sometimes not defined by agents
    timeout: Optional[str]
    # optional by both OCF 1.0 and 1.1
    interval: Optional[str]
    # optional by OCF 1.1
    role: Optional[str]
    # OCF name: 'start-delay', optional by both OCF 1.0 and 1.1
    start_delay: Optional[str]
    # optional by both OCF 1.0 and 1.1
    depth: Optional[str]
    # not allowed by any OCF, defined in OCF 1.0 agents anyway, most probably
    # will be used in OCF 1.1 agents as well as it holds important information
    automatic: Optional[str]
    # not allowed by any OCF, defined in OCF 1.0 agents anyway, most probably
    # will be used in OCF 1.1 agents as well as it holds important information
    on_target: Optional[str]


@dataclass(frozen=True)
class ResourceAgentParameterOcf1_0:  # pylint: disable=invalid-name
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
    # is this a required parameter?
    required: Optional[str]
    # is this parameter deprecated?
    deprecated: Optional[str]
    # name of a deprecated parameter obsoleted by this one
    obsoletes: Optional[str]
    # should the parameter's value be unique across same agent resources?
    unique: Optional[str]


@dataclass(frozen=True)
class ResourceAgentParameterOcf1_1:  # pylint: disable=invalid-name
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
    # is this a required parameter?
    required: Optional[str]
    # Is the parameter meant for advanced users?
    advanced: Optional[str]
    # is this parameter deprecated?
    deprecated: bool
    # list of parameters deprecating this one
    deprecated_by: List[str]
    # text describing / explaining the deprecation
    deprecated_desc: Optional[str]
    # should the parameter's value be unique across same agent resources?
    # OCF 1.1 defines "unique" as well, but it is deprecated and we ignore it
    unique_group: Optional[str]
    # changing this parameter's value triggers a reload instead of a restart
    reloadable: Optional[str]


@dataclass(frozen=True)
class ResourceAgentMetadataOcf1_0:  # pylint: disable=invalid-name
    name: ResourceAgentName
    shortdesc: Optional[str]
    longdesc: Optional[str]
    parameters: List[ResourceAgentParameterOcf1_0]
    actions: List[ResourceAgentActionOcf1_0]


@dataclass(frozen=True)
class ResourceAgentMetadataOcf1_1:  # pylint: disable=invalid-name
    name: ResourceAgentName
    shortdesc: Optional[str]
    longdesc: Optional[str]
    parameters: List[ResourceAgentParameterOcf1_1]
    actions: List[ResourceAgentActionOcf1_1]


@dataclass(frozen=True)
class ResourceAgentAction:
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
    start_delay: Optional[str]
    # optional by both OCF 1.0 and 1.1
    depth: Optional[str]
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    automatic: bool
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    on_target: bool

    def to_dto(self) -> ResourceAgentActionDto:
        return ResourceAgentActionDto(
            self.name,
            self.timeout,
            self.interval,
            self.role,
            self.start_delay,
            self.depth,
            self.automatic,
            self.on_target,
        )


@dataclass(frozen=True)
class ResourceAgentParameter:
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

    def to_dto(self) -> ResourceAgentParameterDto:
        return ResourceAgentParameterDto(
            self.name,
            self.shortdesc,
            self.longdesc,
            self.type,
            self.default,
            self.enum_values,
            self.required,
            self.advanced,
            self.deprecated,
            self.deprecated_by,
            self.deprecated_desc,
            self.unique_group,
            self.reloadable,
        )


@dataclass(frozen=True)
class ResourceAgentMetadata:
    name: ResourceAgentName
    agent_exists: bool
    ocf_version: OcfVersion
    shortdesc: Optional[str]
    longdesc: Optional[str]
    parameters: List[ResourceAgentParameter]
    actions: List[ResourceAgentAction]

    @property
    def provides_unfencing(self) -> bool:
        if not self.name.is_stonith:
            return False
        for action in self.actions:
            if action.name == "on" and action.on_target and action.automatic:
                return True
        return False

    @property
    def provides_self_validation(self) -> bool:
        return any(action.name == "validate-all" for action in self.actions)

    @property
    def provides_promotability(self) -> bool:
        return {action.name for action in self.actions} >= {
            "promote",
            "demote",
        }

    @property
    def unique_parameter_groups(self) -> Mapping[str, AbstractSet[str]]:
        result = defaultdict(set)
        for param in self.parameters:
            if param.unique_group:
                result[param.unique_group].add(param.name)
        return dict(result)

    def to_dto(self) -> ResourceAgentMetadataDto:
        return ResourceAgentMetadataDto(
            self.name.to_dto(),
            self.shortdesc,
            self.longdesc,
            [parameter.to_dto() for parameter in self.parameters],
            [action.to_dto() for action in self.actions],
        )


@dataclass(frozen=True, order=True)
class StandardProviderTuple:
    standard: str
    provider: Optional[str] = None

    @property
    def is_stonith(self) -> bool:
        return self.standard == "stonith"
