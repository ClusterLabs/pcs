from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    InputModifiers,
    group_by_keywords,
)
from pcs.cli.reports.output import (
    deprecation_warning,
    print_to_stderr,
)
from pcs.common.str_tools import indent
from pcs.common.types import StringSequence


def tag_create(
    lib: Any,
    argv: StringSequence,
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


def tag_list_cmd(
    lib: Any,
    argv: StringSequence,
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs tag config' instead."
    )
    return tag_config(lib, argv, modifiers)


def tag_config(
    lib: Any,
    argv: StringSequence,
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    tag_list = lib.tag.config(argv)
    if not tag_list:
        print_to_stderr(" No tags defined")
        return
    lines = []
    for tag in tag_list:
        lines.append(tag["tag_id"])
        lines.extend(indent(tag["idref_list"]))
    print("\n".join(lines))


def tag_remove(
    lib: Any,
    argv: StringSequence,
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


def tag_update(
    lib: Any,
    argv: StringSequence,
    modifiers: InputModifiers,
) -> None:
    """
    Options:
      * -f - CIB file
      * --after - place a reference id in a tag after the specified reference
        id in the tag
      * --before - place a reference id in a tag before the specified reference
        id in the tag
    """
    modifiers.ensure_only_supported("-f", "--after", "--before")
    if not argv:
        raise CmdLineInputError()
    tag_id = argv[0]
    parsed_args = group_by_keywords(
        argv[1:],
        ["add", "remove"],
        keyword_repeat_allowed=False,
        only_found_keywords=True,
    )
    no_add_remove_arguments = (
        "add" not in parsed_args and "remove" not in parsed_args
    )
    no_add_id = "add" in parsed_args and not parsed_args["add"]
    no_remove_id = "remove" in parsed_args and not parsed_args["remove"]
    if no_add_remove_arguments or no_add_id or no_remove_id:
        raise CmdLineInputError(
            show_both_usage_and_message=True,
            hint=("Specify at least one id for 'add' or 'remove' arguments."),
        )
    adjacent_idref = None
    after_adjacent = True
    if modifiers.is_specified("--after") and modifiers.is_specified("--before"):
        raise CmdLineInputError("Cannot specify both --before and --after")
    if modifiers.is_specified("--after"):
        adjacent_idref = modifiers.get("--after")
        after_adjacent = True
    elif modifiers.is_specified("--before"):
        adjacent_idref = modifiers.get("--before")
        after_adjacent = False
    lib.tag.update(
        tag_id,
        parsed_args["add"] if "add" in parsed_args else [],
        parsed_args["remove"] if "remove" in parsed_args else [],
        adjacent_idref=adjacent_idref,
        put_after_adjacent=after_adjacent,
    )
