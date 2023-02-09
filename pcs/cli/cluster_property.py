import json
from shlex import quote
from typing import (
    Any,
    Optional,
    Sequence,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    InputModifiers,
    ensure_unique_args,
    prepare_options,
)
from pcs.cli.nvset import nvset_dto_to_lines
from pcs.cli.reports.output import deprecation_warning
from pcs.common import reports
from pcs.common.interface import dto
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import (
    CibNvpairDto,
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


def set_property(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --force - allow unknown options
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    if not argv:
        raise CmdLineInputError()
    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)
    cluster_options = prepare_options(argv)
    lib.cluster_property.set_properties(cluster_options, force_flags)


def unset_property(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
) -> None:
    """
    Options:
      * --force - no error when removing not existing properties
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    if not argv:
        raise CmdLineInputError()
    force_flags = set()
    if modifiers.get("--force"):
        force_flags.add(reports.codes.FORCE)
    else:
        ensure_unique_args(argv)

    lib.cluster_property.set_properties(
        {name: "" for name in argv}, force_flags
    )


def list_property_deprecated(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
):
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs property config' instead."
    )
    return config(lib, argv, modifiers)


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

    def get_name_default_value_dict(self) -> dict[str, str]:
        return {
            parameter.name: parameter.default
            for parameter in self._properties_metadata
            if parameter.default is not None
        }

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


def _pairs_to_cmd_options(nvpairs: Sequence[CibNvpairDto]) -> list[str]:
    return [quote("=".join((nvpair.name, nvpair.value))) for nvpair in nvpairs]


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


def properties_to_text(
    properties_facade: PropertyConfigurationFacade,
) -> list[str]:
    if properties_facade.properties:
        return nvset_dto_to_lines(
            properties_facade.properties[0],
            nvset_label="Cluster Properties",
        )
    return []


def config(lib: Any, argv: StringSequence, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --all - list configured properties with values and properties with
          default values if not in configuration
      * --defaults - list only default values of properties, only properties
          with a default value are listed
      * --output-format - supported formats: text, cmd, json
    """
    modifiers.ensure_only_supported(
        "-f", "--all", "--defaults", output_format_supported=True
    )
    mutually_exclusive_options = ["--all", "--defaults", "--output-format"]
    if argv and modifiers.is_specified_any(mutually_exclusive_options):
        raise CmdLineInputError(
            "cannot specify properties when using {}".format(
                format_list(mutually_exclusive_options)
            )
        )
    modifiers.ensure_not_mutually_exclusive(
        "--all", "--defaults", "--output-format"
    )
    output_format = modifiers.get_output_format()

    if modifiers.get("--defaults"):
        # do not load set properties
        # --defaults should work without a cib file
        set_properties = ListCibNvsetDto(sets=[])
    else:
        set_properties = lib.cluster_property.get_properties()
    properties_facade = PropertyConfigurationFacade.from_properties_dtos(
        set_properties,
        lib.cluster_property.get_properties_metadata(),
    )

    if argv:
        output = "\n".join(
            properties_to_text_with_default_mark(
                properties_facade, property_names_list=argv
            )
        )
    elif modifiers.get("--all"):
        output = "\n".join(
            properties_to_text_with_default_mark(properties_facade)
        )
    elif modifiers.get("--defaults"):
        deprecation_warning(
            "Option --defaults is deprecated and will be removed. "
            "Please use command 'pcs property defaults' instead."
        )
        output = "\n".join(
            format_name_value_list(
                sorted(properties_facade.get_name_default_value_dict().items())
            )
        )
    elif output_format == "cmd":
        output = " \\\n".join(properties_to_cmd(properties_facade))
    elif output_format == "json":
        output = json.dumps(
            dto.to_dict(ListCibNvsetDto(properties_facade.properties[0:1]))
        )
    else:
        output = "\n".join(
            nvset_dto_to_lines(
                properties_facade.properties[0],
                nvset_label="Cluster Properties",
            )
            if properties_facade.properties
            else []
        )

    if output:
        print(output)


def print_cluster_properties_definition_legacy(
    lib: Any, argv: StringSequence, modifiers: InputModifiers
) -> None:
    """
    Options: no options
    """
    modifiers.ensure_only_supported()
    if argv:
        raise CmdLineInputError()
    print(
        json.dumps(
            lib.cluster_property.get_cluster_properties_definition_legacy()
        )
    )
