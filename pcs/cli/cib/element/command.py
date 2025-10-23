from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import Argv, InputModifiers


def description(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")

    if len(argv) == 1:
        element_id = argv[0]
        description = lib.cib.element_description_get(element_id)
        if description:
            print(description)
    elif len(argv) == 2:
        element_id, description = argv[0], argv[1]
        lib.cib.element_description_set(element_id, description)
    else:
        raise CmdLineInputError()
