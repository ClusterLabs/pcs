import json
from typing import Any, Callable

from pcs.cli.cluster_property.output import PropertyConfigurationFacade
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import lines_to_str
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_OPTION,
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    OUTPUT_FORMAT_VALUE_TEXT,
    Argv,
    InputModifiers,
)
from pcs.common.interface.dto import to_dict
from pcs.common.pacemaker.node import CibNodeListDto
from pcs.utils import print_warning_if_utilization_attrs_has_no_effect

from .output import (
    config_dto_to_attribute_cmd,
    config_dto_to_attribute_lines,
    config_dto_to_utilization_cmd,
    config_dto_to_utilization_lines,
    filter_nodes_by_node_name,
    filter_nodes_nvpairs_by_name,
)


def _node_output_cmd(
    lib: Any,
    argv: Argv,
    modifiers: InputModifiers,
    supported_options: list[str],
    to_cmd: Callable[[CibNodeListDto], list[str]],
    to_lines: Callable[[CibNodeListDto], list[str]],
    utilization_warning: bool = False,
) -> None:
    """
    Options:
      * -f - CIB file
      * --name - specify attribute name for output filter
      * --output-format - supported formats: text, cmd, json
    """
    modifiers.ensure_only_supported(
        *supported_options, output_format_supported=True
    )
    if len(argv) > 1 or modifiers.is_specified("--force"):
        raise CmdLineInputError()
    output_format = modifiers.get_output_format()
    if output_format != OUTPUT_FORMAT_VALUE_TEXT and (
        argv or modifiers.is_specified("--name")
    ):
        raise CmdLineInputError(
            f"filtering is not supported with {OUTPUT_FORMAT_OPTION}="
            f"{OUTPUT_FORMAT_VALUE_CMD}|{OUTPUT_FORMAT_VALUE_JSON}"
        )
    config_dto = lib.node.get_config_dto()
    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        output = ";\n".join(to_cmd(config_dto))
    elif output_format == OUTPUT_FORMAT_VALUE_JSON:
        output = json.dumps(to_dict(config_dto))
    else:
        if argv:
            node_name = argv[0]
            config_dto = filter_nodes_by_node_name(config_dto, node_name)
            if not config_dto.nodes:
                raise CmdLineInputError(f"Unable to find a node: {node_name}")
        if modifiers.is_specified("--name"):
            config_dto = filter_nodes_nvpairs_by_name(
                config_dto, str(modifiers.get("--name"))
            )
        if utilization_warning:
            print_warning_if_utilization_attrs_has_no_effect(
                PropertyConfigurationFacade.from_properties_dtos(
                    lib.cluster_property.get_properties(),
                    lib.cluster_property.get_properties_metadata(),
                )
            )
        output = lines_to_str(to_lines(config_dto))
    if output:
        print(output)


def node_attribute_output_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --name - specify attribute name for output filter
      * --output-format - supported formats: text, cmd, json
    """
    _node_output_cmd(
        lib,
        argv,
        modifiers,
        ["-f", "--force", "--name"],
        config_dto_to_attribute_cmd,
        config_dto_to_attribute_lines,
    )


def node_utilization_output_cmd(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file
      * --name - specify attribute name for output filter
      * --output-format - supported formats: text, cmd, json
    """
    _node_output_cmd(
        lib,
        argv,
        modifiers,
        ["-f", "--name"],
        config_dto_to_utilization_cmd,
        config_dto_to_utilization_lines,
        utilization_warning=True,
    )
