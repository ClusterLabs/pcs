import json
from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import lines_to_str
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    Argv,
    InputModifiers,
)
from pcs.common.interface.dto import to_dict

from .output import config_dto_to_cmd, config_dto_to_lines


def alert_config(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
      * --output-format - supported formats: text, cmd, json
    """
    modifiers.ensure_only_supported("-f", output_format_supported=True)
    output_format = modifiers.get_output_format()
    if argv:
        raise CmdLineInputError

    config_dto = lib.alert.get_config_dto()

    if output_format == OUTPUT_FORMAT_VALUE_JSON:
        print(json.dumps(to_dict(config_dto), indent=2))
        return

    if output_format == OUTPUT_FORMAT_VALUE_CMD:
        result_cmd = config_dto_to_cmd(config_dto)
        if result_cmd:
            print(";\n".join(result_cmd))
        return

    result_text = lines_to_str(config_dto_to_lines(config_dto))
    if result_text:
        print(result_text)
