import json
from typing import Any, Iterable, Mapping

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    KeyValueParser,
    group_by_keywords,
)
from pcs.common.str_tools import indent


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


def _nvset_to_str(nvset_obj: Iterable[Mapping[str, str]]) -> str:
    # TODO duplicite to pcs.resource._nvpairs_strings
    key_val = {
        nvpair_obj["name"]: nvpair_obj["value"] for nvpair_obj in nvset_obj
    }
    output = []
    for name, value in sorted(key_val.items()):
        safe_value = f'"{value}"' if " " in value else value
        output.append(f"{name}={safe_value}")
    return " ".join(output)


def _old__description_attributes_to_str(obj: Mapping[str, Any]) -> list[str]:
    output = []
    if obj.get("description"):
        output.append(f"Description: {obj['description']}")
    if obj.get("instance_attributes"):
        attributes = _nvset_to_str(obj["instance_attributes"])
        output.append(f"Options: {attributes}")
    if obj.get("meta_attributes"):
        attributes = _nvset_to_str(obj["meta_attributes"])
        output.append(f"Meta options: {attributes}")
    return output


def _old_alert_to_str(alert: Mapping[str, Any]) -> list[str]:
    content: list[str] = []
    content.extend(_old__description_attributes_to_str(alert))

    recipients: list[str] = []
    for recipient in alert.get("recipient_list", []):
        recipients.extend(_old_recipient_to_str(recipient))

    if recipients:
        content.append("Recipients:")
        content.extend(indent(recipients, 1))

    return [f"Alert: {alert['id']} (path={alert['path']})"] + indent(content, 1)


def _old_recipient_to_str(recipient: Mapping[str, Any]) -> list[str]:
    return [
        f"Recipient: {recipient['id']} (value={recipient['value']})"
    ] + indent(_old__description_attributes_to_str(recipient), 1)


def old_print_alert_config(
    lib: Any, argv: Argv, modifiers: InputModifiers
) -> None:
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    lines = old_alert_config_lines(lib)
    if lines:
        print("\n".join(lines))


def old_alert_config_lines(lib: Any) -> list[str]:
    lines = []
    alert_list = lib.alert.get_all_alerts()
    if alert_list:
        lines.append("Alerts:")
        for alert in alert_list:
            lines.extend(indent(_old_alert_to_str(alert), 1))
    return lines


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
