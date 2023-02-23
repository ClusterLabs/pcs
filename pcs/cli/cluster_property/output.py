from shlex import quote
from typing import (
    Optional,
    Sequence,
)

from pcs.cli.nvset import nvset_dto_to_lines
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import (
    CibNvsetDto,
    ListCibNvsetDto,
)
from pcs.common.resource_agent.dto import ResourceAgentParameterDto
from pcs.common.str_tools import (
    format_list,
    format_name_value_default_list,
    format_name_value_list,
    format_optional,
    indent,
)
from pcs.common.types import StringSequence


class PropertyConfigurationFacade:
    def __init__(
        self,
        properties: Sequence[CibNvsetDto],
        properties_metadata: Sequence[ResourceAgentParameterDto],
    ) -> None:
        self._properties = properties
        self._properties_metadata = properties_metadata
        self._name_nvpair_dto_map = (
            {
                nvpair_dto.name: nvpair_dto
                for nvpair_dto in self._properties[0].nvpairs
            }
            if self._properties
            else {}
        )
        self._defaults_map = {
            parameter.name: parameter.default
            for parameter in self._properties_metadata
            if parameter.default is not None
        }

    @classmethod
    def from_properties_dtos(
        cls,
        properties_dto: ListCibNvsetDto,
        properties_metadata_dto: ClusterPropertyMetadataDto,
    ) -> "PropertyConfigurationFacade":
        return cls(
            properties_dto.sets,
            properties_metadata_dto.properties_metadata,
        )

    @property
    def properties(self) -> Sequence[CibNvsetDto]:
        return self._properties

    @property
    def properties_metadata(self) -> Sequence[ResourceAgentParameterDto]:
        return self._properties_metadata

    @property
    def defaults(self) -> dict[str, str]:
        return self._defaults_map

    def get_property_value(self, property_name: str) -> Optional[str]:
        property_dto = self._name_nvpair_dto_map.get(property_name)
        return property_dto.value if property_dto else None

    def get_name_value_default_list(self) -> list[tuple[str, str, bool]]:
        name_value_default_list = [
            (nvpair_dto.name, nvpair_dto.value, False)
            for nvpair_dto in self._name_nvpair_dto_map.values()
        ]
        name_value_default_list.extend(
            [
                (metadata_dto.name, metadata_dto.default, True)
                for metadata_dto in self._properties_metadata
                if metadata_dto.name not in self._name_nvpair_dto_map
                and metadata_dto.default is not None
            ]
        )
        return name_value_default_list


def properties_to_text(
    properties_facade: PropertyConfigurationFacade,
) -> list[str]:
    if properties_facade.properties:
        return nvset_dto_to_lines(
            properties_facade.properties[0],
            nvset_label="Cluster Properties",
        )
    return []


def properties_to_text_with_default_mark(
    properties_facade: PropertyConfigurationFacade,
    property_names_list: Optional[StringSequence] = None,
) -> list[str]:
    lines: list[str] = []
    _id = (
        properties_facade.properties[0].id
        if properties_facade.properties
        else ""
    )
    id_part = format_optional(_id, template=" {}")
    lines = [f"Cluster Properties:{id_part}"]
    tuple_list = [
        item
        for item in properties_facade.get_name_value_default_list()
        if not property_names_list or item[0] in property_names_list
    ]
    lines.extend(indent(format_name_value_default_list(sorted(tuple_list))))
    return lines


def properties_to_cmd(
    properties_facade: PropertyConfigurationFacade,
) -> list[str]:
    if properties_facade.properties and properties_facade.properties[0].nvpairs:
        options = [
            quote("=".join([nvpair.name, nvpair.value]))
            for nvpair in properties_facade.properties[0].nvpairs
        ]
        return ["pcs property set"] + indent(options)
    return []


def properties_defaults_to_text(
    properties_facade: PropertyConfigurationFacade,
    property_names: Optional[StringSequence] = None,
) -> list[str]:
    return format_name_value_list(
        sorted(
            [
                (key, value)
                for key, value in properties_facade.defaults.items()
                if not property_names or key in property_names
            ]
        )
    )


def _parameter_metadata_to_text(
    metadata: ResourceAgentParameterDto,
) -> list[str]:
    text: list[str] = []
    desc = ""
    if metadata.longdesc:
        desc = metadata.longdesc.replace("\n", " ")
    if not desc and metadata.shortdesc:
        desc = metadata.shortdesc.replace("\n", " ")
    if not desc:
        desc = "No description available"
    text.append(f"Description: {desc}")
    if metadata.enum_values:
        type_or_allowed_values = "Allowed values: {}".format(
            format_list(metadata.enum_values)
        )
    else:
        type_or_allowed_values = f"Type: {metadata.type}"
    text.append(type_or_allowed_values)
    if metadata.default:
        text.append(f"Default: {metadata.default}")
    return [metadata.name] + indent(text)


def cluster_property_metadata_to_text(
    metadata: Sequence[ResourceAgentParameterDto],
) -> list[str]:
    """
    Convert cluster property metadata to lines of description text.
    Output example:

    property-name
      Description: <longdesc or shortdesc>
      Type: <type> / Allowed values: <enum values>
      Default: <default value>

    metadata - list of ResourceAgentParameterDto which is used for cluster
        property metadata
    """
    text: list[str] = []
    for metadata_dto in metadata:
        text.extend(_parameter_metadata_to_text(metadata_dto))
    return text
