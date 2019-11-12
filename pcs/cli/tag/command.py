from typing import (
    Any,
    Sequence,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers

def tag_create(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) < 2:
        raise CmdLineInputError()
    tag_id, idref_list = argv[0], argv[1:]
    lib.tag.create(tag_id, idref_list)
