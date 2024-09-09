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
from pcs.cli.reports.output import warn
from pcs.cli.resource import command as resource_cmd
from pcs.cli.stonith.levels.output import (
    stonith_level_config_to_cmd,
    stonith_level_config_to_text,
)
from pcs.common.str_tools import indent


def config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * --output-format - supported formats: text, cmd, json
      * -f CIB file
    """
    output_format = modifiers.get_output_format()
    output = resource_cmd.config_common(lib, argv, modifiers, stonith=True)

    if output_format == OUTPUT_FORMAT_VALUE_JSON:
        # JSON output format does not include fencing levels because it would
        # change the current JSON structure and break existing user tooling
        warn(
            "Fencing levels are not included because this command could only "
            "export stonith configuration previously. This cannot be changed "
            "to avoid breaking existing tooling. To export fencing levels, run "
            "'pcs stonith level config --output-format=json'"
        )
        print(output)
        return

    fencing_topology_dto = lib.fencing_topology.get_config_dto()
    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        # we can look at the output of config_common as one command
        output = format_cmd_list(
            [output, *stonith_level_config_to_cmd(fencing_topology_dto)]
        )
    else:
        text_output = stonith_level_config_to_text(fencing_topology_dto)
        if text_output:
            output += "\n\nFencing Levels:\n" + lines_to_str(
                smart_wrap_text(indent(text_output))
            )

    if output:
        print(output)
