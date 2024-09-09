import json
from typing import Any

from pcs.cli.common.output import (
    format_cmd_list,
    lines_to_str,
    smart_wrap_text,
)
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    Argv,
    InputModifiers,
)
from pcs.cli.resource.output import (
    ResourcesConfigurationFacade,
    resources_to_cmd,
    resources_to_text,
)
from pcs.common.interface import dto
from pcs.common.pacemaker.resource.list import CibResourcesDto


def config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    output = config_common(lib, argv, modifiers, stonith=False)
    if output:
        print(output)


def config_common(
    lib: Any, argv: Argv, modifiers: InputModifiers, stonith: bool
) -> str:
    """
    Also used by stonith commands.

    Options:
      * -f - CIB file
      * --output-format - supported formats: text, cmd, json
    """
    modifiers.ensure_only_supported("-f", output_format_supported=True)
    resources_facade = (
        ResourcesConfigurationFacade.from_resources_dto(
            lib.resource.get_configured_resources()
        )
        .filter_stonith(stonith)
        .filter_resources(argv)
    )
    output_format = modifiers.get_output_format()
    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        output = format_cmd_list(
            [" \\\n".join(cmd) for cmd in resources_to_cmd(resources_facade)]
        )
    elif output_format == OUTPUT_FORMAT_VALUE_JSON:
        output = json.dumps(
            dto.to_dict(
                CibResourcesDto(
                    primitives=resources_facade.primitives,
                    clones=resources_facade.clones,
                    groups=resources_facade.groups,
                    bundles=resources_facade.bundles,
                )
            )
        )
    else:
        output = lines_to_str(
            smart_wrap_text(resources_to_text(resources_facade))
        )
    return output
