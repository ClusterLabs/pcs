import json
from typing import Any

from pcs.cli.alert.output import config_dto_to_lines
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import lines_to_str
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    KeyValueParser,
    group_by_keywords,
)
from pcs.cli.reports.output import deprecation_warning


def alert_add(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    sections = group_by_keywords(
        argv, {"options", "meta"}, implicit_first_keyword="main"
    )
    parser = KeyValueParser(sections.get_args_flat("main"))
    parser.check_allowed_keys(["id", "description", "path"])
    main_args = parser.get_unique()

    lib.alert.create_alert(
        main_args.get("id", None),
        main_args.get("path", None),
        KeyValueParser(sections.get_args_flat("options")).get_unique(),
        KeyValueParser(sections.get_args_flat("meta")).get_unique(),
        main_args.get("description", None),
    )


def alert_update(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    alert_id = argv[0]

    sections = group_by_keywords(
        argv[1:], {"options", "meta"}, implicit_first_keyword="main"
    )
    parser = KeyValueParser(sections.get_args_flat("main"))
    parser.check_allowed_keys(["description", "path"])
    main_args = parser.get_unique()

    lib.alert.update_alert(
        alert_id,
        main_args.get("path", None),
        KeyValueParser(sections.get_args_flat("options")).get_unique(),
        KeyValueParser(sections.get_args_flat("meta")).get_unique(),
        main_args.get("description", None),
    )


def alert_remove(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    lib.alert.remove_alert(argv)


def recipient_add(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
      * --force - allows not unique recipient values
    """
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) < 2:
        raise CmdLineInputError()

    alert_id = argv[0]

    sections = group_by_keywords(
        argv[1:], {"options", "meta"}, implicit_first_keyword="main"
    )
    parser = KeyValueParser(sections.get_args_flat("main"))
    parser.check_allowed_keys(["description", "id", "value"])
    main_args = parser.get_unique()

    lib.alert.add_recipient(
        alert_id,
        main_args.get("value", None),
        KeyValueParser(sections.get_args_flat("options")).get_unique(),
        KeyValueParser(sections.get_args_flat("meta")).get_unique(),
        recipient_id=main_args.get("id", None),
        description=main_args.get("description", None),
        allow_same_value=modifiers.get("--force"),
    )


def recipient_update(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
      * --force - allows not unique recipient values
    """
    modifiers.ensure_only_supported("-f", "--force")
    if not argv:
        raise CmdLineInputError()

    recipient_id = argv[0]

    sections = group_by_keywords(
        argv[1:], {"options", "meta"}, implicit_first_keyword="main"
    )
    parser = KeyValueParser(sections.get_args_flat("main"))
    parser.check_allowed_keys(["description", "value"])
    main_args = parser.get_unique()

    lib.alert.update_recipient(
        recipient_id,
        KeyValueParser(sections.get_args_flat("options")).get_unique(),
        KeyValueParser(sections.get_args_flat("meta")).get_unique(),
        recipient_value=main_args.get("value", None),
        description=main_args.get("description", None),
        allow_same_value=modifiers.get("--force"),
    )


def recipient_remove(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    lib.alert.remove_recipient(argv)


def print_alert_show(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs alert config' instead."
    )
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    result_text = lines_to_str(config_dto_to_lines(lib.alert.get_config_dto()))
    if result_text:
        print(result_text)


def print_alerts_in_json(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    This is used only by pcsd, will be removed in new architecture

    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()

    print(json.dumps(lib.alert.get_all_alerts()))
