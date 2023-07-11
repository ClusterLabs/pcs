from shlex import quote
from typing import (
    Dict,
    List,
    Optional,
    Sequence,
    Tuple,
)

from pcs.cli.nvset import nvset_dto_to_lines
from pcs.cli.resource.output import resource_agent_parameter_metadata_to_text
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import (
    CibNvsetDto,
    ListCibNvsetDto,
)
from pcs.common.resource_agent.dto import ResourceAgentParameterDto
from pcs.common.str_tools import (
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
        self._first_nvpair_set = (
            self._properties[0].nvpairs if self._properties else []
        )
        self._properties_metadata = properties_metadata
        self._readonly_properties = readonly_properties
        self._defaults_map = self.get_defaults(include_advanced=True)
        self._name_nvpair_dto_map = {
            nvpair_dto.name: nvpair_dto for nvpair_dto in self._first_nvpair_set
        }

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
        cls, properties_dto: ListCibNvsetDto
    ) -> "PropertyConfigurationFacade":
        return cls(
            properties_dto.nvsets,
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
    def properties_metadata(self) -> Sequence[ResourceAgentParameterDto]:
        return self._properties_metadata

    @property
    def readonly_properties(self) -> StringCollection:
        return self._readonly_properties

    def get_property_value(
        self, property_name: str, custom_default: Optional[str] = None
    ) -> Optional[str]:
        nvpair = self._name_nvpair_dto_map.get(property_name)
        return nvpair.value if nvpair else custom_default

    def get_property_value_or_default(
        self, property_name: str, custom_default: Optional[str] = None
    ) -> Optional[str]:
        value = self.get_property_value(property_name)
        if value is not None:
            return value
        return self._defaults_map.get(property_name, custom_default)

    def get_defaults(
        self,
        property_names: Optional[StringSequence] = None,
        include_advanced: bool = False,
    ) -> Dict[str, str]:
        return {
            metadata.name: metadata.default
            for metadata in self.get_properties_metadata(
                property_names, include_advanced
            )
            if metadata.default is not None
        }

    def get_properties_metadata(
        self,
        property_names: Optional[StringSequence] = None,
        include_advanced: bool = False,
    ) -> Sequence[ResourceAgentParameterDto]:
        if property_names:
            filtered_metadata = [
                metadata
                for metadata in self._properties_metadata
                if metadata.name in property_names
            ]
        else:
            filtered_metadata = [
                metadata
                for metadata in self._properties_metadata
                if include_advanced or not metadata.advanced
            ]
        deduplicated_metadata = {
            metadata.name: metadata for metadata in filtered_metadata
        }
        return list(deduplicated_metadata.values())

    def get_name_value_default_list(self) -> List[Tuple[str, str, bool]]:
        name_value_default_list = [
            (nvpair_dto.name, nvpair_dto.value, False)
            for nvpair_dto in self._first_nvpair_set
        ]
        name_value_default_list.extend(
            [
                (metadata_dto.name, metadata_dto.default, True)
                for metadata_dto in self.get_properties_metadata(
                    include_advanced=True
                )
                if metadata_dto.name not in self._name_nvpair_dto_map
                and metadata_dto.default is not None
            ]
        )
        return name_value_default_list


def properties_to_text(
    properties_facade: PropertyConfigurationFacade,
) -> List[str]:
    """
    Return a text format of configured properties.

    properties_facade -- cluster property configuration and metadata
    """
    if properties_facade.properties:
        return nvset_dto_to_lines(
            properties_facade.properties[0],
            nvset_label="Cluster Properties",
        )
    return ["Cluster Properties:"]


def properties_to_text_with_default_mark(
    properties_facade: PropertyConfigurationFacade,
    property_names: Optional[StringSequence] = None,
) -> List[str]:
    """
    Return text format of configured properties or property default values.
    If default property value is missing then property is not displayed at all.
    If property_names is specified, then only properties from the list is
    displayed.

    properties_facade -- cluster property configuration and metadata
    property_names -- properties to be displayed
    """
    lines: List[str] = []
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
) -> List[str]:
    """
    Convert configured properties to the `pcs property set` command.

    properties_facade -- cluster property configuration and metadata
    """
    if properties_facade.properties and properties_facade.properties[0].nvpairs:
        options = [
            quote("=".join([nvpair.name, nvpair.value]))
            for nvpair in properties_facade.properties[0].nvpairs
            if nvpair.name not in properties_facade.readonly_properties
        ]
        if options:
            return ["pcs property set --force --"] + indent(options)
    return []


def properties_defaults_to_text(property_dict: Dict[str, str]) -> List[str]:
    """
    Convert property default values to lines of text.

    property_dict -- name to default value map
    """
    return format_name_value_list(sorted(property_dict.items()))


def cluster_property_metadata_to_text(
    metadata: Sequence[ResourceAgentParameterDto],
) -> List[str]:
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
    text: List[str] = []
    for parameter_dto in metadata:
        text.extend(resource_agent_parameter_metadata_to_text(parameter_dto))
    return text


def properties_to_text_legacy(
    properties_facade: PropertyConfigurationFacade,
    property_names: Optional[StringSequence] = None,
    defaults_only=False,
    include_defaults=False,
) -> List[str]:
    """
    Return legacy text format of configured properties. If property_names is
    specified, then only properties from the list are displayed. If specified
    property is missing, then property with its default value is displayed.
    Parameters property_names, defaults_only and include_defaults are
    mutually_exclusive.

    properties_facade -- cluster property configuration and metadata
    property_names -- properties to be displayed
    defaults_only -- display only properties default values
    include_defaults -- display default values for not configured properties
    """
    mutual_exclusive = [
        bool(param)
        for param in [property_names, defaults_only, include_defaults]
    ]
    if mutual_exclusive.count(True) > 1:
        raise AssertionError("Mutually exclusive parameters were used.")
    text = ["Cluster Properties:"]
    configured_properties_dict = {}
    if properties_facade.properties:
        configured_properties_dict = {
            nvpair.name: nvpair.value
            for nvpair in properties_facade.properties[0].nvpairs
        }
    default_properties_dict = properties_facade.get_defaults(
        include_advanced=True
    )
    all_properties_dict = {
        **default_properties_dict,
        **configured_properties_dict,
    }
    if defaults_only:
        properties_dict = default_properties_dict
    elif include_defaults:
        properties_dict = all_properties_dict
    elif property_names:
        properties_dict = {
            name: value
            for name, value in all_properties_dict.items()
            if name in property_names
        }
    else:
        properties_dict = configured_properties_dict
    for name, value in sorted(properties_dict.items()):
        text.append(f" {name}: {value}")
    return text
