from typing import Any

from pcs.cli.cluster_property.output import PropertyConfigurationFacade
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import Argv, InputModifiers
from pcs.cli.reports.output import deprecation_warning
from pcs.common.str_tools import indent
from pcs.lib.pacemaker.values import is_true

_autodelete_deprecated = "Flag '--autodelete' is deprecated and might be removed in a future release."


def _print_list_of_objects(obj_list, transformation_fn):
    out = []
    for obj in obj_list:
        out += transformation_fn(obj)
    if out:
        print("\n".join(out))


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
    return list(
        zip(
            [permission.lower() for permission in argv[::3]],
            [scope_type.lower() for scope_type in argv[1::3]],
            argv[2::3],
            strict=False,
        )
    )


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


def role_delete(lib: Any, argv: Argv, modifiers: InputModifiers):
    """
    Options:
      * -f - CIB file
      * --autodelete - autodelete empty targets, groups
    """
    modifiers.ensure_only_supported("-f", "--autodelete")
    if len(argv) != 1:
        raise CmdLineInputError()

    # --autodelete was used in old web ui only, was never used in the new web ui
    # DEPRECATED since 0.12.3, unused since 0.11.1
    if modifiers.is_specified("--autodelete"):
        deprecation_warning(_autodelete_deprecated)

    lib.acl.remove_role(
        argv[0], autodelete_users_groups=modifiers.get("--autodelete")
    )


def _role_assign_unassign(argv, keyword, not_specific_fn, user_fn, group_fn):
    """
    Commandline options: no options
    """
    # DEPRECATED ambiguous syntax in the first 0.12 version
    # it was used in the old web ui, it was never used in the new web ui
    # therefore it is unused since pcs-0.11.1
    # - pcs role assign <role id> [to] [user|group] <username/group>
    # - pcs role unassign <role id> [from] [user|group] <username/group>
    # The problem is, that 'user|group' is optional, therefore pcs guesses
    # which one it is.
    argv_len = len(argv)
    if argv_len < 2:
        raise CmdLineInputError()

    not_specific_fn_deprecated = (
        "Assigning / unassigning a role to a user / group without specifying "
        "'user' or 'group' keyword is deprecated and might be removed in a "
        "future release."
    )

    if argv_len == 2:
        deprecation_warning(not_specific_fn_deprecated)
        not_specific_fn(*argv)
    elif argv_len == 3:
        role_id, something, ug_id = argv
        if something == keyword:
            deprecation_warning(not_specific_fn_deprecated)
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
        # DEPRECATED ambiguous syntax in the first 0.12 version
        # Use assign_role_to_target or assign_role_to_group instead.
        # it was used in the old web ui, it was never used in the new web ui
        # therefore it is unused since pcs-0.11.1
        lib.acl.assign_role_not_specific,
        lib.acl.assign_role_to_target,
        lib.acl.assign_role_to_group,
    )


def role_unassign(lib: Any, argv: Argv, modifiers: InputModifiers):
    """
    Options:
      * -f - CIB file
      * --autodelete - autodelete empty targets, groups
    """
    modifiers.ensure_only_supported("-f", "--autodelete")

    # --autodelete was used in old web ui only, was never used in the new web ui
    # DEPRECATED since 0.12.3, unused since 0.11.1
    if modifiers.is_specified("--autodelete"):
        deprecation_warning(_autodelete_deprecated)

    _role_assign_unassign(
        argv,
        "from",
        # DEPRECATED ambiguous syntax in the first 0.12 version
        # Use unassign_role_from_target or unassign_role_from_group instead.
        # it was used in the old web ui, it was never used in the new web ui
        # therefore it is unused since pcs-0.11.1
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
    return [f"{type_name.title()}: {obj.get('id')}"] + indent(
        [" ".join(["Roles:"] + obj.get("role_list", []))]
    )


def target_to_str(target):
    return _target_group_to_str("user", target)


def group_to_str(group):
    return _target_group_to_str("group", group)


def role_to_str(role):
    out = []
    if role.get("description"):
        out.append(f"Description: {role.get('description')}")
    out += map(_permission_to_str, role.get("permission_list", []))
    return [f"Role: {role.get('id')}"] + indent(out)


def _permission_to_str(permission):
    out = ["Permission:", permission.get("kind")]
    if permission.get("xpath") is not None:
        out += ["xpath", permission.get("xpath")]
    elif permission.get("reference") is not None:
        out += ["id", permission.get("reference")]
    out.append(f"({permission.get('id')})")
    return " ".join(out)
