from collections import defaultdict
from collections.abc import Mapping, Set
from dataclasses import dataclass
from typing import NewType

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
    provider: str | None
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
    automatic: str | None
    # not allowed by any OCF, defined in OCF 1.0 agents anyway
    on_target: str | None


@dataclass(frozen=True)
class ResourceAgentActionOcf1_1:  # pylint: disable=invalid-name
    # pylint: disable=too-many-instance-attributes

    # (start, stop, promote...), mandatory by both OCF 1.0 and 1.1
    name: str
    # mandatory by both OCF 1.0 and 1.1, sometimes not defined by agents
    timeout: str | None
    # optional by both OCF 1.0 and 1.1
    interval: str | None
    # optional by OCF 1.1
    role: str | None
    # OCF name: 'start-delay', optional by both OCF 1.0 and 1.1
    start_delay: str | None
    # optional by both OCF 1.0 and 1.1
    depth: str | None
    # not allowed by any OCF, defined in OCF 1.0 agents anyway, most probably
    # will be used in OCF 1.1 agents as well as it holds important information
    automatic: str | None
    # not allowed by any OCF, defined in OCF 1.0 agents anyway, most probably
    # will be used in OCF 1.1 agents as well as it holds important information
    on_target: str | None


@dataclass(frozen=True)
class ResourceAgentParameterOcf1_0:  # pylint: disable=invalid-name
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
    # is this a required parameter?
    required: str | None
    # is this parameter deprecated?
    deprecated: str | None
    # name of a deprecated parameter obsoleted by this one
    obsoletes: str | None
    # should the parameter's value be unique across same agent resources?
    unique: str | None


@dataclass(frozen=True)
class ResourceAgentParameterOcf1_1:  # pylint: disable=invalid-name
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
    # is this a required parameter?
    required: str | None
    # Is the parameter meant for advanced users?
    advanced: str | None
    # is this parameter deprecated?
    deprecated: bool
    # list of parameters deprecating this one
    deprecated_by: list[str]
    # text describing / explaining the deprecation
    deprecated_desc: str | None
    # should the parameter's value be unique across same agent resources?
    # OCF 1.1 defines "unique" as well, but it is deprecated and we ignore it
    unique_group: str | None
    # changing this parameter's value triggers a reload instead of a restart
    reloadable: str | None


@dataclass(frozen=True)
class ResourceAgentMetadataOcf1_0:  # pylint: disable=invalid-name
    name: ResourceAgentName
    shortdesc: str | None
    longdesc: str | None
    parameters: list[ResourceAgentParameterOcf1_0]
    actions: list[ResourceAgentActionOcf1_0]


@dataclass(frozen=True)
class ResourceAgentMetadataOcf1_1:  # pylint: disable=invalid-name
    name: ResourceAgentName
    shortdesc: str | None
    longdesc: str | None
    parameters: list[ResourceAgentParameterOcf1_1]
    actions: list[ResourceAgentActionOcf1_1]


@dataclass(frozen=True)
class ResourceAgentAction:
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
    shortdesc: str | None
    longdesc: str | None
    parameters: list[ResourceAgentParameter]
    actions: list[ResourceAgentAction]

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
    def unique_parameter_groups(self) -> Mapping[str, Set[str]]:
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
    provider: str | None = None

    @property
    def is_stonith(self) -> bool:
        return self.standard == "stonith"
