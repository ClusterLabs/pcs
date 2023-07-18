import json
from typing import Any

from pcs.cli.cluster_property.output import (
    PropertyConfigurationFacade,
    cluster_property_metadata_to_text,
    properties_defaults_to_text,
    properties_to_cmd,
    properties_to_text,
    properties_to_text_with_default_mark,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import smart_wrap_text
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_OPTION,
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    OUTPUT_FORMAT_VALUE_TEXT,
    Argv,
    InputModifiers,
    ensure_unique_args,
    prepare_options,
)
from pcs.cli.reports.output import deprecation_warning
from pcs.common import reports
from pcs.common.interface import dto
from pcs.common.pacemaker.cluster_property import ClusterPropertyMetadataDto
from pcs.common.pacemaker.nvset import ListCibNvsetDto
from pcs.common.str_tools import (
    format_list,
    format_plural,
)


def set_property(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
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


def unset_property(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
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
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs property config' instead."
    )
    return config(lib, argv, modifiers)


def config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
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
    modifiers.ensure_not_mutually_exclusive(*mutually_exclusive_options)
    output_format = modifiers.get_output_format()

    if (
        argv
        or output_format == OUTPUT_FORMAT_VALUE_CMD
        or modifiers.get("--all")
    ):
        properties_facade = PropertyConfigurationFacade.from_properties_dtos(
            lib.cluster_property.get_properties(),
            lib.cluster_property.get_properties_metadata(),
        )
    elif modifiers.get("--defaults"):
        # do not load set properties
        # --defaults should work without a cib file
        properties_facade = (
            PropertyConfigurationFacade.from_properties_metadata(
                lib.cluster_property.get_properties_metadata()
            )
        )
    else:
        # json or default text
        # do not load properties metadata, only configured properties are needed
        properties_facade = PropertyConfigurationFacade.from_properties_config(
            lib.cluster_property.get_properties()
        )

    if argv:
        output = "\n".join(
            properties_to_text_with_default_mark(
                properties_facade, property_names=argv
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
            properties_defaults_to_text(
                properties_facade.get_defaults(include_advanced=True)
            )
        )
    elif output_format == OUTPUT_FORMAT_VALUE_CMD:
        output = " \\\n".join(properties_to_cmd(properties_facade))
    elif output_format == OUTPUT_FORMAT_VALUE_JSON:
        output = json.dumps(
            dto.to_dict(ListCibNvsetDto(properties_facade.properties[0:1]))
        )
    else:
        output = "\n".join(properties_to_text(properties_facade))

    if output:
        print(output)


def defaults(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --full - also list advanced cluster properties
    """
    modifiers.ensure_only_supported("--full")
    if argv and modifiers.is_specified("--full"):
        raise CmdLineInputError("cannot specify properties when using '--full'")
    properties_facade = PropertyConfigurationFacade.from_properties_metadata(
        lib.cluster_property.get_properties_metadata()
    )
    defaults_dict = properties_facade.get_defaults(
        argv, include_advanced=modifiers.is_specified("--full")
    )
    extra_args = set(argv) - defaults_dict.keys()
    if extra_args:
        raise CmdLineInputError(
            "No default value for {property_pl}: {name_list}".format(
                property_pl=format_plural(extra_args, "property"),
                name_list=format_list(list(extra_args)),
            )
        )
    output = "\n".join(properties_defaults_to_text(defaults_dict))
    if output:
        print(output)


def describe(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --full - also list advanced cluster properties
      * --output-format - supported formats: text, json
    """
    modifiers.ensure_only_supported("--full", output_format_supported=True)
    if argv and modifiers.is_specified("--full"):
        raise CmdLineInputError("cannot specify properties when using '--full'")
    output_format = modifiers.get_output_format(
        supported_formats={OUTPUT_FORMAT_VALUE_TEXT, OUTPUT_FORMAT_VALUE_JSON}
    )
    if output_format == OUTPUT_FORMAT_VALUE_JSON and (
        argv or modifiers.is_specified("--full")
    ):
        raise CmdLineInputError(
            "property filtering is not supported with "
            f"{OUTPUT_FORMAT_OPTION}={OUTPUT_FORMAT_VALUE_JSON}"
        )
    properties_facade = PropertyConfigurationFacade.from_properties_metadata(
        lib.cluster_property.get_properties_metadata()
    )
    if output_format == OUTPUT_FORMAT_VALUE_JSON:
        output = json.dumps(
            dto.to_dict(
                ClusterPropertyMetadataDto(
                    properties_metadata=properties_facade.properties_metadata,
                    readonly_properties=properties_facade.readonly_properties,
                )
            )
        )
    else:
        filtered_metadata = properties_facade.get_properties_metadata(
            argv, include_advanced=modifiers.is_specified("--full")
        )
        extra_args = set(argv) - {
            metadata.name for metadata in filtered_metadata
        }
        if extra_args:
            raise CmdLineInputError(
                "No description for {property_pl}: {name_list}".format(
                    property_pl=format_plural(extra_args, "property"),
                    name_list=format_list(list(extra_args)),
                )
            )
        output = "\n".join(
            smart_wrap_text(
                cluster_property_metadata_to_text(
                    sorted(filtered_metadata, key=lambda x: x.name)
                )
            )
        )
    if output:
        print(output)


def print_cluster_properties_definition_legacy(
    lib: Any, argv: Argv, modifiers: InputModifiers
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
