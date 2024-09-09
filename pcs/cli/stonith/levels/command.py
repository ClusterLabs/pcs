import json
from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import (
    format_cmd_list,
    lines_to_str,
)
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    Argv,
    InputModifiers,
)
from pcs.cli.stonith.levels import output as levels_output
from pcs.common.interface.dto import to_dict


def config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --output-format - supported formats: text, cmd, json
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", output_format_supported=True)
    output_format = modifiers.get_output_format()
    if argv:
        raise CmdLineInputError

    fencing_topology_dto = lib.fencing_topology.get_config_dto()

    if output_format == OUTPUT_FORMAT_VALUE_JSON:
        output = json.dumps(to_dict(fencing_topology_dto))
    elif output_format == OUTPUT_FORMAT_VALUE_CMD:
        output = format_cmd_list(
            levels_output.stonith_level_config_to_cmd(fencing_topology_dto)
        )
    else:
        output = lines_to_str(
            levels_output.stonith_level_config_to_text(fencing_topology_dto)
        )

    if output:
        print(output)
