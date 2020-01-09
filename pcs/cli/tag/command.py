from typing import (
    Any,
    Sequence,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import InputModifiers
from pcs.common.tools import indent

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

def tag_config(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    tag_list = lib.tag.config(argv)
    if not tag_list:
        print(" No tags defined")
        return
    lines = []
    for tag in tag_list:
        lines.append(tag["tag_id"])
        lines.extend(indent(tag["idref_list"]))
    print("\n".join(lines))

def tag_remove(
    lib: Any,
    argv: Sequence[str],
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) < 1:
        raise CmdLineInputError()
    lib.tag.remove(argv)
