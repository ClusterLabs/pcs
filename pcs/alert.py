from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

from pcs import (
    usage,
    utils,
)
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import prepare_options
from pcs.cli.common.console_report import indent
from pcs.lib.errors import LibraryError


def alert_cmd(*args):
    argv = args[1]
    if not argv:
        sub_cmd = "config"
    else:
        sub_cmd = argv.pop(0)
    try:
        if sub_cmd == "help":
            usage.alert(argv)
        elif sub_cmd == "create":
            alert_add(*args)
        elif sub_cmd == "update":
            alert_update(*args)
        elif sub_cmd == "remove":
            alert_remove(*args)
        elif sub_cmd == "config" or sub_cmd == "show":
            print_alert_config(*args)
        elif sub_cmd == "recipient":
            recipient_cmd(*args)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "alert", sub_cmd)


def recipient_cmd(*args):
    argv = args[1]

    if not argv:
        usage.alert(["recipient"])
        sys.exit(1)

    sub_cmd = argv.pop(0)
    try:
        if sub_cmd == "help":
            usage.alert(["recipient"])
        elif sub_cmd == "add":
            recipient_add(*args)
        elif sub_cmd == "update":
            recipient_update(*args)
        elif sub_cmd == "remove":
            recipient_remove(*args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "alert", "recipient {0}".format(sub_cmd)
        )


def parse_cmd_sections(arg_list, section_list):
    output = dict([(section, []) for section in section_list + ["main"]])
    cur_section = "main"
    for arg in arg_list:
        if arg in section_list:
            cur_section = arg
            continue
        output[cur_section].append(arg)

    return output


def ensure_only_allowed_options(parameter_dict, allowed_list):
    for arg, value in parameter_dict.items():
        if arg not in allowed_list:
            raise CmdLineInputError(
                "Unexpected parameter '{0}={1}'".format(arg, value)
            )


def alert_add(lib, argv, modifiers):
    if not argv:
        raise CmdLineInputError()

    sections = parse_cmd_sections(argv, ["options", "meta"])
    main_args = prepare_options(sections["main"])
    ensure_only_allowed_options(main_args, ["id", "description", "path"])

    lib.alert.create_alert(
        main_args.get("id", None),
        main_args.get("path", None),
        prepare_options(sections["options"]),
        prepare_options(sections["meta"]),
        main_args.get("description", None)
    )


def alert_update(lib, argv, modifiers):
    if not argv:
        raise CmdLineInputError()

    alert_id = argv[0]

    sections = parse_cmd_sections(argv[1:], ["options", "meta"])
    main_args = prepare_options(sections["main"])
    ensure_only_allowed_options(main_args, ["description", "path"])

    lib.alert.update_alert(
        alert_id,
        main_args.get("path", None),
        prepare_options(sections["options"]),
        prepare_options(sections["meta"]),
        main_args.get("description", None)
    )


def alert_remove(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()

    lib.alert.remove_alert(argv[0])


def recipient_add(lib, argv, modifiers):
    if len(argv) < 2:
        raise CmdLineInputError()

    alert_id = argv[0]
    recipient_value = argv[1]

    sections = parse_cmd_sections(argv[2:], ["options", "meta"])
    main_args = prepare_options(sections["main"])
    ensure_only_allowed_options(main_args, ["description"])

    lib.alert.add_recipient(
        alert_id,
        recipient_value,
        prepare_options(sections["options"]),
        prepare_options(sections["meta"]),
        main_args.get("description", None)
    )


def recipient_update(lib, argv, modifiers):
    if len(argv) < 2:
        raise CmdLineInputError()

    alert_id = argv[0]
    recipient_value = argv[1]

    sections = parse_cmd_sections(argv[2:], ["options", "meta"])
    main_args = prepare_options(sections["main"])
    ensure_only_allowed_options(main_args, ["description"])

    lib.alert.update_recipient(
        alert_id,
        recipient_value,
        prepare_options(sections["options"]),
        prepare_options(sections["meta"]),
        main_args.get("description", None)
    )


def recipient_remove(lib, argv, modifiers):
    if len(argv) != 2:
        raise CmdLineInputError()

    lib.alert.remove_recipient(argv[0], argv[1])


def _nvset_to_str(nvset_obj):
    output = []
    for nvpair_obj in nvset_obj:
        output.append("{key}={value}".format(
            key=nvpair_obj["name"], value=nvpair_obj["value"]
        ))
    return " ".join(output)


def __description_attributes_to_str(obj):
    output = []
    if obj.get("description"):
        output.append("Description: {desc}".format(desc=obj["description"]))
    if obj.get("instance_attributes"):
        output.append("Options: {attributes}".format(
            attributes=_nvset_to_str(obj["instance_attributes"])
        ))
    if obj.get("meta_attributes"):
        output.append("Meta options: {attributes}".format(
            attributes=_nvset_to_str(obj["meta_attributes"])
        ))
    return output


def _alert_to_str(alert):
    content = []
    content.extend(__description_attributes_to_str(alert))

    recipients = []
    for recipient in alert.get("recipient_list", []):
        recipients.extend( _recipient_to_str(recipient))

    if recipients:
        content.append("Recipients:")
        content.extend(indent(recipients, 1))

    return ["Alert: {alert_id} (path={path})".format(
        alert_id=alert["id"], path=alert["path"]
    )] + indent(content, 1)


def _recipient_to_str(recipient):
    return ["Recipient: {value}".format(value=recipient["value"])] + indent(
        __description_attributes_to_str(recipient), 1
    )


def print_alert_config(lib, argv, modifiers):
    if argv:
        raise CmdLineInputError()

    print("Alerts:")
    alert_list = lib.alert.get_all_alerts()
    if alert_list:
        for alert in alert_list:
            print("\n".join(indent(_alert_to_str(alert), 1)))
    else:
        print(" No alerts defined")
