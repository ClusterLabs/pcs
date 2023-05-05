from pcs.cli.cluster_property.output import PropertyConfigurationFacade
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.reports.output import warn
from pcs.common.str_tools import indent
from pcs.lib.pacemaker.values import is_true


def _print_list_of_objects(obj_list, transformation_fn):
    out = []
    for obj in obj_list:
        out += transformation_fn(obj)
    if out:
        print("\n".join(out))


def show_acl_config(lib, argv, modifiers):
    warn(
        "This command is deprecated and will be removed. "
        "Please use 'pcs acl config' instead.",
        stderr=True,
    )
    return acl_config(lib, argv, modifiers)


def acl_config(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    # TODO move to lib once lib supports cluster properties
    # enabled/disabled should be part of the structure returned
    # by lib.acl.get_config
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()

    properties_facade = PropertyConfigurationFacade.from_properties_dtos(
        lib.cluster_property.get_properties(),
        lib.cluster_property.get_properties_metadata(),
    )
    acl_enabled = properties_facade.get_property_value_or_default(
        "enable-acl", ""
    )
    if is_true(acl_enabled):
        print("ACLs are enabled")
    else:
        print("ACLs are disabled, run 'pcs acl enable' to enable")
    print()

    data = lib.acl.get_config()
    _print_list_of_objects(data.get("target_list", []), target_to_str)
    _print_list_of_objects(data.get("group_list", []), group_to_str)
    _print_list_of_objects(data.get("role_list", []), role_to_str)


def acl_enable(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    lib.cluster_property.set_properties({"enable-acl": "true"})


def acl_disable(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if argv:
        raise CmdLineInputError()
    lib.cluster_property.set_properties({"enable-acl": "false"})


def user_create(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
    user_name, role_list = argv[0], argv[1:]
    lib.acl.create_target(user_name, role_list)


def user_delete(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.acl.remove_target(argv[0])


def group_create(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
    group_name, role_list = argv[0], argv[1:]
    lib.acl.create_group(group_name, role_list)


def group_delete(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) != 1:
        raise CmdLineInputError()
    lib.acl.remove_group(argv[0])


def argv_to_permission_info_list(argv):
    """
    Commandline options: no options
    """
    if len(argv) % 3 != 0:
        raise CmdLineInputError()

    # wrapping by list,
    # because in python3 zip() returns an iterator instead of a list
    # and the loop below makes iteration over it
    permission_info_list = list(
        zip(
            [permission.lower() for permission in argv[::3]],
            [scope_type.lower() for scope_type in argv[1::3]],
            argv[2::3],
        )
    )

    for permission, scope_type, dummy_scope in permission_info_list:
        if permission not in ["read", "write", "deny"] or scope_type not in [
            "xpath",
            "id",
        ]:
            raise CmdLineInputError()

    return permission_info_list


def role_create(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    role_id = argv.pop(0)
    description = ""
    desc_key = "description="
    if argv and argv[0].startswith(desc_key) and len(argv[0]) > len(desc_key):
        description = argv.pop(0)[len(desc_key) :]
    permission_info_list = argv_to_permission_info_list(argv)

    lib.acl.create_role(role_id, permission_info_list, description)


def role_delete(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --autodelete - autodelete empty targets, groups
    """
    modifiers.ensure_only_supported("-f", "--autodelete")
    if len(argv) != 1:
        raise CmdLineInputError()

    lib.acl.remove_role(
        argv[0], autodelete_users_groups=modifiers.get("--autodelete")
    )


def _role_assign_unassign(argv, keyword, not_specific_fn, user_fn, group_fn):
    """
    Commandline options: no options
    """
    # TODO deprecate ambiguous syntax:
    # - pcs role assign <role id> [to] [user|group] <username/group>
    # - pcs role unassign <role id> [from] [user|group] <username/group>
    # The problem is, that 'user|group' is optional, therefore pcs guesses
    # which one it is.
    # We haven't deprecated it yet, as groups don't work in pacemaker,
    # therefore there would be no benefit from deprecating it.
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


def role_assign(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    _role_assign_unassign(
        argv,
        "to",
        # TODO deprecate
        # Use assign_role_to_target or assign_role_to_group instead.
        # We haven't deprecated it yet, as groups don't work in pacemaker,
        # therefore there would be no benefit from deprecating it.
        lib.acl.assign_role_not_specific,
        lib.acl.assign_role_to_target,
        lib.acl.assign_role_to_group,
    )


def role_unassign(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --autodelete - autodelete empty targets, groups
    """
    modifiers.ensure_only_supported("-f", "--autodelete")
    _role_assign_unassign(
        argv,
        "from",
        # TODO deprecate
        # Use unassign_role_from_target or unassign_role_from_group instead.
        # We haven't deprecated it yet, as groups don't work in pacemaker,
        # therefore there would be no benefit from deprecating it.
        lambda role_id, ug_id: lib.acl.unassign_role_not_specific(
            role_id, ug_id, modifiers.get("--autodelete")
        ),
        lambda role_id, ug_id: lib.acl.unassign_role_from_target(
            role_id, ug_id, modifiers.get("--autodelete")
        ),
        lambda role_id, ug_id: lib.acl.unassign_role_from_group(
            role_id, ug_id, modifiers.get("--autodelete")
        ),
    )


def permission_add(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
    if len(argv) < 4:
        raise CmdLineInputError()
    role_id, argv_next = argv[0], argv[1:]
    lib.acl.add_permission(role_id, argv_to_permission_info_list(argv_next))


def run_permission_delete(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f")
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
