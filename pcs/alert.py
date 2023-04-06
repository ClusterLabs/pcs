import json
from functools import partial

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    group_by_keywords,
    prepare_options,
)
from pcs.cli.reports.output import deprecation_warning
from pcs.common.str_tools import indent

parse_cmd_sections = partial(group_by_keywords, implicit_first_group_key="main")


def ensure_only_allowed_options(parameter_dict, allowed_list):
    for arg, value in parameter_dict.items():
        if arg not in allowed_list:
            raise CmdLineInputError(
                "Unexpected parameter '{0}={1}'".format(arg, value)
            )


def alert_add(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    sections = parse_cmd_sections(argv, set(["options", "meta"]))
    main_args = prepare_options(sections["main"])
    ensure_only_allowed_options(main_args, ["id", "description", "path"])

    lib.alert.create_alert(
        main_args.get("id", None),
        main_args.get("path", None),
        prepare_options(sections["options"]),
        prepare_options(sections["meta"]),
        main_args.get("description", None),
    )


def alert_update(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    alert_id = argv[0]

    sections = parse_cmd_sections(argv[1:], set(["options", "meta"]))
    main_args = prepare_options(sections["main"])
    ensure_only_allowed_options(main_args, ["description", "path"])

    lib.alert.update_alert(
        alert_id,
        main_args.get("path", None),
        prepare_options(sections["options"]),
        prepare_options(sections["meta"]),
        main_args.get("description", None),
    )


def alert_remove(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    lib.alert.remove_alert(argv)


def recipient_add(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file (in lib wrapper)
      * --force - allows not unique recipient values
    """
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) < 2:
        raise CmdLineInputError()

    alert_id = argv[0]

    sections = parse_cmd_sections(argv[1:], set(["options", "meta"]))
    main_args = prepare_options(sections["main"])
    ensure_only_allowed_options(main_args, ["description", "id", "value"])

    lib.alert.add_recipient(
        alert_id,
        main_args.get("value", None),
        prepare_options(sections["options"]),
        prepare_options(sections["meta"]),
        recipient_id=main_args.get("id", None),
        description=main_args.get("description", None),
        allow_same_value=modifiers.get("--force"),
    )


def recipient_update(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file (in lib wrapper)
      * --force - allows not unique recipient values
    """
    modifiers.ensure_only_supported("-f", "--force")
    if not argv:
        raise CmdLineInputError()

    recipient_id = argv[0]

    sections = parse_cmd_sections(argv[1:], set(["options", "meta"]))
    main_args = prepare_options(sections["main"])
    ensure_only_allowed_options(main_args, ["description", "value"])

    lib.alert.update_recipient(
        recipient_id,
        prepare_options(sections["options"]),
        prepare_options(sections["meta"]),
        recipient_value=main_args.get("value", None),
        description=main_args.get("description", None),
        allow_same_value=modifiers.get("--force"),
    )


def recipient_remove(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    lib.alert.remove_recipient(argv)


def _nvset_to_str(nvset_obj):
    # TODO duplicite to pcs.resource._nvpairs_strings
    key_val = {
        nvpair_obj["name"]: nvpair_obj["value"] for nvpair_obj in nvset_obj
    }
    output = []
    for name, value in sorted(key_val.items()):
        if " " in value:
            value = f'"{value}"'
        output.append(f"{name}={value}")
    return " ".join(output)


def __description_attributes_to_str(obj):
    output = []
    if obj.get("description"):
        output.append("Description: {desc}".format(desc=obj["description"]))
    if obj.get("instance_attributes"):
        output.append(
            "Options: {attributes}".format(
                attributes=_nvset_to_str(obj["instance_attributes"])
            )
        )
    if obj.get("meta_attributes"):
        output.append(
            "Meta options: {attributes}".format(
                attributes=_nvset_to_str(obj["meta_attributes"])
            )
        )
    return output


def _alert_to_str(alert):
    content = []
    content.extend(__description_attributes_to_str(alert))

    recipients = []
    for recipient in alert.get("recipient_list", []):
        recipients.extend(_recipient_to_str(recipient))

    if recipients:
        content.append("Recipients:")
        content.extend(indent(recipients, 1))

    return [
        "Alert: {alert_id} (path={path})".format(
            alert_id=alert["id"], path=alert["path"]
        )
    ] + indent(content, 1)


def _recipient_to_str(recipient):
    return [
        "Recipient: {id} (value={value})".format(
            value=recipient["value"], id=recipient["id"]
        )
    ] + indent(__description_attributes_to_str(recipient), 1)


def print_alert_show(lib, argv, modifiers):
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs alert config' instead."
    )
    return print_alert_config(lib, argv, modifiers)


def print_alert_config(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    lines = alert_config_lines(lib)
    if lines:
        print("\n".join(lines))


def alert_config_lines(lib):
    lines = []
    alert_list = lib.alert.get_all_alerts()
    if alert_list:
        lines.append("Alerts:")
        for alert in alert_list:
            lines.extend(indent(_alert_to_str(alert), 1))
    return lines


def print_alerts_in_json(lib, argv, modifiers):
    """
    This is used only by pcsd, will be removed in new architecture

    Options:
      * -f - CIB file (in lib wrapper)
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()

    print(json.dumps(lib.alert.get_all_alerts()))
