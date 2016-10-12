from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys

from pcs import (
    prop,
    usage,
    utils,
)
from pcs.lib.pacemaker_values import is_true
from pcs.cli.common.console_report import indent
from pcs.cli.common.errors import CmdLineInputError
from pcs.lib.errors import LibraryError

def acl_cmd(lib, argv, modifiers):
    if len(argv) < 1:
        sub_cmd, argv_next = "show", []
    else:
        sub_cmd, argv_next = argv[0], argv[1:]

    try:
        if sub_cmd == "help":
            usage.acl(argv_next)
        elif sub_cmd == "show":
            show_acl_config(lib, argv_next, modifiers)
        elif sub_cmd == "enable":
            acl_enable(argv_next)
        elif sub_cmd == "disable":
            acl_disable(argv_next)
        elif sub_cmd == "role":
            acl_role(lib, argv_next, modifiers)
        elif sub_cmd in ["target", "user"]:
            acl_user(lib, argv_next, modifiers)
        elif sub_cmd == "group":
            acl_group(lib, argv_next, modifiers)
        elif sub_cmd == "permission":
            acl_permission(lib, argv_next, modifiers)
        else:
            raise CmdLineInputError()
    except LibraryError as e:
        utils.process_library_reports(e.args)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "acl", sub_cmd)


def _print_list_of_objects(obj_list, transformation_fn):
    out = []
    for obj in obj_list:
        out += transformation_fn(obj)
    if out:
        print("\n".join(out))


def show_acl_config(lib, argv, modifiers):
    # TODO move to lib once lib supports cluster properties
    # enabled/disabled should be part of the structure returned
    # by lib.acl.get_config
    properties = utils.get_set_properties(defaults=prop.get_default_properties())
    acl_enabled = properties.get("enable-acl", "").lower()
    if is_true(acl_enabled):
        print("ACLs are enabled")
    else:
        print("ACLs are disabled, run 'pcs acl enable' to enable")
    print()

    data = lib.acl.get_config()
    _print_list_of_objects(data.get("target_list", []), target_to_str)
    _print_list_of_objects(data.get("group_list", []), group_to_str)
    _print_list_of_objects(data.get("role_list", []), role_to_str)


def acl_enable(argv):
    # TODO move to lib once lib supports cluster properties
    prop.set_property(["enable-acl=true"])

def acl_disable(argv):
    # TODO move to lib once lib supports cluster properties
    prop.set_property(["enable-acl=false"])


def acl_role(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "create":
            role_create(lib, argv_next, modifiers)
        elif sub_cmd == "delete":
            role_delete(lib, argv_next, modifiers)
        elif sub_cmd == "assign":
            role_assign(lib, argv_next, modifiers)
        elif sub_cmd == "unassign":
            role_unassign(lib, argv_next, modifiers)
        else:
            usage.show("acl", ["role"])
            sys.exit(1)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "acl", "role {0}".format(sub_cmd))


def acl_user(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "create":
            user_create(lib, argv_next, modifiers)
        elif sub_cmd == "delete":
            user_delete(lib, argv_next, modifiers)
        else:
            usage.show("acl", ["user"])
            sys.exit(1)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(e, "acl", "user {0}".format(sub_cmd))


def user_create(lib, argv, dummy_modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()
    user_name, role_list = argv[0], argv[1:]
    lib.acl.create_target(user_name, role_list)


def user_delete(lib, argv, dummy_modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.acl.remove_target(argv[0])


def acl_group(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "create":
            group_create(lib, argv_next, modifiers)
        elif sub_cmd == "delete":
            group_delete(lib, argv_next, modifiers)
        else:
            usage.show("acl", ["group"])
            sys.exit(1)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "acl", "group {0}".format(sub_cmd)
        )


def group_create(lib, argv, dummy_modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()
    group_name, role_list = argv[0], argv[1:]
    lib.acl.create_group(group_name, role_list)


def group_delete(lib, argv, dummy_modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.acl.remove_group(argv[0])


def acl_permission(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()

    sub_cmd, argv_next = argv[0], argv[1:]
    try:
        if sub_cmd == "add":
            permission_add(lib, argv_next, modifiers)
        elif sub_cmd == "delete":
            run_permission_delete(lib, argv_next, modifiers)
        else:
            usage.show("acl", ["permission"])
            sys.exit(1)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_errror(
            e, "acl", "permission {0}".format(sub_cmd)
        )


def argv_to_permission_info_list(argv):
    if len(argv) % 3 != 0:
        raise CmdLineInputError()

    #wrapping by list,
    #because in python3 zip() returns an iterator instead of a list
    #and the loop below makes iteration over it
    permission_info_list = list(zip(
        [permission.lower() for permission in argv[::3]],
        [scope_type.lower() for scope_type in argv[1::3]],
        argv[2::3]
    ))

    for permission, scope_type, dummy_scope in permission_info_list:
        if(
            permission not in ['read', 'write', 'deny']
            or
            scope_type not in ['xpath', 'id']
        ):
            raise CmdLineInputError()

    return permission_info_list


def role_create(lib, argv, modifiers):
    if len(argv) < 1:
        raise CmdLineInputError()

    role_id = argv.pop(0)
    description = ""
    desc_key = 'description='
    if argv and argv[0].startswith(desc_key) and len(argv[0]) > len(desc_key):
        description = argv.pop(0)[len(desc_key):]
    permission_info_list = argv_to_permission_info_list(argv)

    lib.acl.create_role(role_id, permission_info_list, description)


def role_delete(lib, argv, modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()

    lib.acl.remove_role(argv[0], autodelete_users_groups=True)


def _role_assign_unassign(argv, keyword, not_specific_fn, user_fn, group_fn):
    argv_len = len(argv)
    if argv_len < 2:
        raise CmdLineInputError()

    if argv_len == 2:
        not_specific_fn(*argv)
    elif argv_len == 3:
        role_id, something, ug_id = argv
        if something == keyword:
            not_specific_fn(role_id, ug_id)
        elif something == "user":
            user_fn(role_id, ug_id)
        elif something == "group":
            group_fn(role_id, ug_id)
        else:
            raise CmdLineInputError()
    elif argv_len == 4 and argv[1] == keyword and argv[2] in ["group", "user"]:
        role_id, _, user_group, ug_id = argv
        if user_group == "user":
            user_fn(role_id, ug_id)
        else:
            group_fn(role_id, ug_id)
    else:
        raise CmdLineInputError()


def role_assign(lib, argv, dummy_modifiers):
    _role_assign_unassign(
        argv,
        "to",
        lib.acl.assign_role_not_specific,
        lib.acl.assign_role_to_target,
        lib.acl.assign_role_to_group
    )


def role_unassign(lib, argv, modifiers):
    _role_assign_unassign(
        argv,
        "from",
        lambda role_id, ug_id: lib.acl.unassign_role_not_specific(
            role_id, ug_id, modifiers.get("autodelete", False)
        ),
        lambda role_id, ug_id: lib.acl.unassign_role_from_target(
            role_id, ug_id, modifiers.get("autodelete", False)
        ),
        lambda role_id, ug_id: lib.acl.unassign_role_from_group(
            role_id, ug_id, modifiers.get("autodelete", False)
        )
    )


def permission_add(lib, argv, dummy_modifiers):
    if len(argv) < 4:
        raise CmdLineInputError()
    role_id, argv_next = argv[0], argv[1:]
    lib.acl.add_permission(role_id, argv_to_permission_info_list(argv_next))


def run_permission_delete(lib, argv, dummy_modifiers):
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.acl.remove_permission(argv[0])


def _target_group_to_str(type_name, obj):
    return ["{0}: {1}".format(type_name.title(), obj.get("id"))] + indent(
        [" ".join(["Roles:"] + obj.get("role_list", []))]
    )

def target_to_str(target):
    return _target_group_to_str("user", target)


def group_to_str(group):
    return _target_group_to_str("group", group)


def role_to_str(role):
    out = []
    if role.get("description"):
        out.append("Description: {0}".format(role.get("description")))
    out += map(_permission_to_str, role.get("permission_list", []))
    return ["Role: {0}".format(role.get("id"))] + indent(out)


def _permission_to_str(permission):
    out = ["Permission:", permission.get("kind")]
    if permission.get("xpath") is not None:
        out += ["xpath", permission.get("xpath")]
    elif permission.get("reference") is not None:
        out += ["id", permission.get("reference")]
    out.append("({0})".format(permission.get("id")))
    return " ".join(out)

