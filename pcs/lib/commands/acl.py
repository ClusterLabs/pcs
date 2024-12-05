from contextlib import contextmanager
from typing import TYPE_CHECKING

from pcs.lib.cib import acl
from pcs.lib.cib.tools import (
    IdProvider,
    get_acls,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError

if TYPE_CHECKING:
    from pcs.common import reports


@contextmanager
def cib_acl_section(env):
    yield get_acls(env.get_cib())
    env.push_cib()


def create_role(
    lib_env: LibraryEnvironment,
    role_id: str,
    permission_info_list: acl.PermissionInfoList,
    description: str,
) -> None:
    """
    Create new acl role.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of new role which should be created
    permission_info_list -- list of permissions, items of list should be tuples:
        (<read|write|deny>, <xpath|id>, <any string>)
    description -- text description for role
    """
    with cib_acl_section(lib_env) as acl_section:
        id_provider = IdProvider(acl_section)
        report_list = acl.validate_create_role(
            id_provider, role_id, description
        )
        if permission_info_list:
            report_list += acl.validate_permissions(
                acl_section, permission_info_list
            )
        if lib_env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()

        role_el = acl.create_role(acl_section, role_id, description)
        if permission_info_list:
            acl.add_permissions_to_role(
                role_el, permission_info_list, id_provider
            )


def remove_role(lib_env, role_id, autodelete_users_groups=False):
    """
    Remove role with specified id from CIB.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of role which should be deleted
    autodelete_users_groups -- if True targets and groups which are empty after
        removal will be removed
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.remove_role(acl_section, role_id, autodelete_users_groups)


# TODO deprecate
# Use assign_role_to_target or assign_role_to_group instead.
# We haven't deprecated it yet, as groups don't work in pacemaker, therefore
# there would be no benefit from deprecating it.
def assign_role_not_specific(lib_env, role_id, target_or_group_id):
    """
    Assign role with id role_id to target or group with id target_or_group_id.
    Target element has bigger priority so if there are target and group with
    the same id only target element will be affected by this function.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of role which should be assigned to target/group
    target_or_group_id -- id of target/group element
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.assign_role(
            acl_section,
            role_id,
            acl.find_target_or_group(acl_section, target_or_group_id),
        )


def assign_role_to_target(lib_env, role_id, target_id):
    """
    Assign role with id role_id to target with id target_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of acl_role element which should be assigned to target
    target_id -- id of acl_target element to which role should be assigned
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.assign_role(
            acl_section,
            role_id,
            acl.find_target(acl_section, target_id),
        )


def assign_role_to_group(lib_env, role_id, group_id):
    """
    Assign role with id role_id to group with id group_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of acl_role element which should be assigned to group
    group_id -- id of acl_group element to which role should be assigned
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.assign_role(
            acl_section,
            role_id,
            acl.find_group(acl_section, group_id),
        )


# TODO deprecate
# Use unassign_role_from_target or unassign_role_from_group instead.
# We haven't deprecated it yet, as groups don't work in pacemaker, therefore
# there would be no benefit from deprecating it.
def unassign_role_not_specific(
    lib_env, role_id, target_or_group_id, autodelete_target_group=False
):
    """
    Unassign role with role_id from target/group with id target_or_group_id.
    Target element has bigger priority so if there are target and group with
    the same id only target element will be affected by this function.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of role which should be unassigned from target/group
    target_or_group_id -- id of acl_target/acl_group element
    autodelete_target_group -- if True remove target/group element if has no
        more role assigned
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.unassign_role(
            acl.find_target_or_group(acl_section, target_or_group_id),
            role_id,
            autodelete_target_group,
        )


def unassign_role_from_target(
    lib_env, role_id, target_id, autodelete_target=False
):
    """
    Unassign role with role_id from group with id target_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of role which should be unassigned from target
    target_id -- id of acl_target element
    autodelete_target -- if True remove target element if has no more role
        assigned
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.unassign_role(
            acl.find_target(acl_section, target_id), role_id, autodelete_target
        )


def unassign_role_from_group(
    lib_env, role_id, group_id, autodelete_group=False
):
    """
    Unassign role with role_id from group with id group_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of role which should be unassigned from group
    group_id -- id of acl_group element
    autodelete_target -- if True remove group element if has no more role
        assigned
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.unassign_role(
            acl.find_group(acl_section, group_id), role_id, autodelete_group
        )


def create_target(lib_env, target_id, role_list):
    """
    Create new target with id target_id and assign roles role_list to it.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    target_id -- id of new target
    role_list -- list of roles to assign to new target
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.assign_all_roles(
            acl_section, role_list, acl.create_target(acl_section, target_id)
        )


def create_group(lib_env, group_id, role_list):
    """
    Create new group with id group_id and assign roles role_list to it.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    group_id -- id of new group
    role_list -- list of roles to assign to new group
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.assign_all_roles(
            acl_section, role_list, acl.create_group(acl_section, group_id)
        )


def remove_target(lib_env, target_id):
    """
    Remove acl_target element with id target_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    target_id -- id of target which should be removed
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.remove_target(acl_section, target_id)


def remove_group(lib_env, group_id):
    """
    Remove acl_group element with id group_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    group_id -- id of group which should be removed
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.remove_group(acl_section, group_id)


def add_permission(
    lib_env: LibraryEnvironment,
    role_id: str,
    permission_info_list: acl.PermissionInfoList,
) -> None:
    """
    Add permissions to a role with id role_id. If role doesn't exist it will be
    created.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of role
    permission_info_list -- list of permissions, items of list should be tuples:
        (<read|write|deny>, <xpath|id>, <any string>)
    """
    with cib_acl_section(lib_env) as acl_section:
        report_list: reports.ReportItemList = []
        id_provider = IdProvider(acl_section)

        role_el = acl.find_role(acl_section, role_id, none_if_id_unused=True)
        if role_el is None:
            report_list += acl.validate_create_role(id_provider, role_id)
        report_list += acl.validate_permissions(
            acl_section, permission_info_list
        )
        if lib_env.report_processor.report_list(report_list).has_errors:
            raise LibraryError()

        if role_el is None:
            role_el = acl.create_role(acl_section, role_id)
        acl.add_permissions_to_role(role_el, permission_info_list, id_provider)


def remove_permission(lib_env, permission_id):
    """
    Remove permission with id permission_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    permission_id -- id of permission element which should be removed
    """
    with cib_acl_section(lib_env) as acl_section:
        acl.remove_permission(acl_section, permission_id)


def get_config(lib_env):
    """
    Returns ACL configuration in dictionary. Format of output:
        {
            "target_list": <list of targets>,
            "group_list": <list og groups>,
            "role_list": <list of roles>,
        }

    lib_env -- LibraryEnvironment
    """
    acl_section = get_acls(lib_env.get_cib())
    return {
        "target_list": acl.get_target_list(acl_section),
        "group_list": acl.get_group_list(acl_section),
        "role_list": acl.get_role_list(acl_section),
    }
