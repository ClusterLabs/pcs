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
    indent,
)
from pcs.common.types import (
    StringCollection,
    StringSequence,
)


class PropertyConfigurationFacade:
    def __init__(
        self,
        properties: Sequence[CibNvsetDto],
        properties_metadata: Sequence[ResourceAgentParameterDto],
        readonly_properties: StringCollection,
    ) -> None:
        self._properties = properties
        self._properties_metadata = properties_metadata
        self._readonly_properties = readonly_properties
        self._defaults_map = {
            metadata.name: metadata.default
            for metadata in self._properties_metadata
            if metadata.default is not None
        }
        self._name_nvpair_dto_map = (
            {
                nvpair_dto.name: nvpair_dto
                for nvpair_dto in self._properties[0].nvpairs
            }
            if self._properties
            else {}
        )

    @classmethod
    def from_properties_dtos(
        cls,
        properties_dto: ListCibNvsetDto,
        properties_metadata_dto: ClusterPropertyMetadataDto,
    ) -> "PropertyConfigurationFacade":
        return cls(
            properties_dto.nvsets,
            properties_metadata_dto.properties_metadata,
            properties_metadata_dto.readonly_properties,
        )

    @classmethod
    def from_properties_config(
        cls, properties: ListCibNvsetDto
    ) -> "PropertyConfigurationFacade":
        return cls(
            properties.nvsets,
            [],
            [],
        )

    @classmethod
    def from_properties_metadata(
        cls, properties_metadata_dto: ClusterPropertyMetadataDto
    ) -> "PropertyConfigurationFacade":
        return cls(
            [],
            properties_metadata_dto.properties_metadata,
            properties_metadata_dto.readonly_properties,
        )

    @property
    def properties(self) -> Sequence[CibNvsetDto]:
        return self._properties

    @property
    def readonly_properties(self) -> StringCollection:
        return self._readonly_properties

    def get_property_value(
        self, property_name: str, custom_default=None
    ) -> Optional[str]:
        nvpair = self._name_nvpair_dto_map.get(property_name)
        return nvpair.value if nvpair else custom_default

    def get_property_value_or_default(
        self, property_name: str, custom_default=None
    ) -> Optional[str]:
        value = self.get_property_value(property_name)
        if value is not None:
            return value
        return self._defaults_map.get(property_name, custom_default)

    @staticmethod
    def _filter_names_advanced(
        metadata: ResourceAgentParameterDto,
        property_names: Optional[StringSequence] = None,
        advanced: Optional[bool] = None,
    ) -> bool:
        return bool(
            (
                not property_names
                and (advanced is None or metadata.advanced == advanced)
            )
            or (
                property_names
                and metadata.name in property_names
                and (advanced is None or metadata.advanced == advanced)
            )
        )

    def get_defaults(
        self,
        property_names: Optional[StringSequence] = None,
        advanced: Optional[bool] = None,
    ) -> dict[str, str]:
        return {
            metadata.name: metadata.default
            for metadata in self._properties_metadata
            if metadata.default is not None
            and self._filter_names_advanced(metadata, property_names, advanced)
        }

    def get_properties_metadata(
        self,
        property_names: Optional[StringSequence] = None,
        advanced: Optional[bool] = None,
    ) -> Sequence[ResourceAgentParameterDto]:
        return [
            metadata
            for metadata in self._properties_metadata
            if self._filter_names_advanced(metadata, property_names, advanced)
        ]

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
    property_names: Optional[StringSequence] = None,
) -> list[str]:
    lines: list[str] = []
    id_part = (
        f" {properties_facade.properties[0].id}"
        if properties_facade.properties
        else ""
    )
    lines = [f"Cluster Properties:{id_part}"]
    tuple_list = [
        item
        for item in properties_facade.get_name_value_default_list()
        if not property_names or item[0] in property_names
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
            if nvpair.name not in properties_facade.readonly_properties
        ]
        if options:
            return ["pcs property set --force --"] + indent(options)
    return []


def properties_defaults_to_text(property_dict: dict[str, str]) -> list[str]:
    """
    Convert property default values to lines of text.

    property_dict -- name to default value map
    """
    return format_name_value_list(
        sorted((key, value) for key, value in property_dict.items())
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

    return [
        f"{metadata.name} (advanced use only)"
        if metadata.advanced
        else metadata.name
    ] + indent(text)


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
