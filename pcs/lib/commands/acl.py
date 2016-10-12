from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import reports
from pcs.lib.cib import acl
from pcs.lib.errors import LibraryError


REQUIRED_CIB_VERSION = (2, 0, 0)


def create_role(lib_env, role_id, permission_info_list, description):
    """
    Create new acl role.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvirnoment
    role_id -- id of new role which should be created
    permission_info_list -- list of permissons, items of list should be tuples:
        (<read|write|deny>, <xpath|id>, <any string>)
    description -- text description for role
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)

    if permission_info_list:
        acl.validate_permissions(cib, permission_info_list)
    role_el = acl.create_role(cib, role_id, description)
    if permission_info_list:
        acl.add_permissions_to_role(role_el, permission_info_list)

    lib_env.push_cib(cib)


def remove_role(lib_env, role_id, autodelete_users_groups=False):
    """
    Remove role with specified id from CIB.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of role which should be deleted
    autodelete_users_groups -- if True targets and groups which are empty after
        removal will be removed
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    try:
        acl.remove_role(cib, role_id, autodelete_users_groups)
    except acl.AclRoleNotFound as e:
        raise LibraryError(acl.acl_error_to_report_item(e))
    lib_env.push_cib(cib)


def assign_role_not_specific(lib_env, role_id, target_or_group_id):
    """
    Assign role wth id role_id to target or group with id target_or_group_id.
    Target element has bigger pririty so if there are target and group with same
    id only target element will be affected by this function.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnviroment
    role_id -- id of role which should be assigne to target/group
    target_or_group_id -- id of target/group element
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    try:
        acl.assign_role(
            _get_target_or_group(cib, target_or_group_id),
            acl.find_role(cib, role_id)
        )
    except acl.AclError as e:
        raise LibraryError(acl.acl_error_to_report_item(e))
    lib_env.push_cib(cib)


def _get_target_or_group(cib, target_or_group_id):
    """
    Returns acl_target or acl_group element with id target_or_group_id. Target
    element has bigger pririty so if there are target and group with same id
    only target element will be affected by this function.
    Raises LibraryError if there is no target or group element with
    specified id.

    cib -- cib etree node
    target_or_group_id -- id of target/group element which should be returned
    """
    try:
        return acl.find_target(cib, target_or_group_id)
    except acl.AclTargetNotFound:
        try:
            return acl.find_group(cib, target_or_group_id)
        except acl.AclGroupNotFound:
            raise LibraryError(
                reports.id_not_found(target_or_group_id, "user/group")
            )

def assign_role_to_target(lib_env, role_id, target_id):
    """
    Assign role with id role_id to target with id target_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of acl_role element which should be assigned to target
    target_id -- id of acl_target element to which role should be assigned
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    try:
        acl.assign_role(
            acl.find_target(cib, target_id), acl.find_role(cib, role_id)
        )
    except acl.AclError as e:
        raise LibraryError(acl.acl_error_to_report_item(e))
    lib_env.push_cib(cib)


def assign_role_to_group(lib_env, role_id, group_id):
    """
    Assign role with id role_id to group with id group_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of acl_role element which should be assigned to group
    group_id -- id of acl_group element to which role should be assigned
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    try:
        acl.assign_role(
            acl.find_group(cib, group_id), acl.find_role(cib, role_id)
        )
    except acl.AclError as e:
        raise LibraryError(acl.acl_error_to_report_item(e))
    lib_env.push_cib(cib)


def unassign_role_not_specific(
    lib_env, role_id, target_or_group_id, autodelete_target_group=False
):
    """
    Unassign role with role_id from target/group with id target_or_group_id.
    Target element has bigger pririty so if there are target and group with same
    id only target element will be affected by this function.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    role_id -- id of role which should be unassigned from target/group
    target_or_group_id -- id of acl_target/acl_group element
    autodelete_target_group -- if True remove target/group element if has no
        more role assigned
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    acl.unassign_role(
        _get_target_or_group(cib, target_or_group_id),
        role_id,
        autodelete_target_group
    )
    lib_env.push_cib(cib)


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
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    try:
        acl.unassign_role(
            acl.find_target(cib, target_id),
            role_id,
            autodelete_target
        )
    except acl.AclError as e:
        raise LibraryError(acl.acl_error_to_report_item(e))
    lib_env.push_cib(cib)


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
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    try:
        acl.unassign_role(
            acl.find_group(cib, group_id),
            role_id,
            autodelete_group
        )
    except acl.AclError as e:
        raise LibraryError(acl.acl_error_to_report_item(e))
    lib_env.push_cib(cib)


def _assign_roles_to_element(cib, element, role_id_list):
    """
    Assign roles from role_id_list to element.
    Raises LibraryError on any failure.

    cib -- cib etree node
    element -- element to which specified roles should be assigned
    role_id_list -- list of role id
    """
    report_list = []
    for role_id in role_id_list:
        try:
            acl.assign_role(element, acl.find_role(cib, role_id))
        except acl.AclError as e:
            report_list.append(acl.acl_error_to_report_item(e))
    if report_list:
        raise LibraryError(*report_list)


def create_target(lib_env, target_id, role_list):
    """
    Create new target with id target_id and assign roles role_list to it.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    target_id -- id of new target
    role_list -- list of roles to assign to new target
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    _assign_roles_to_element(cib, acl.create_target(cib, target_id), role_list)
    lib_env.push_cib(cib)


def create_group(lib_env, group_id, role_list):
    """
    Create new group with id group_id and assign roles role_list to it.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    group_id -- id of new group
    role_list -- list of roles to assign to new group
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    _assign_roles_to_element(cib, acl.create_group(cib, group_id), role_list)
    lib_env.push_cib(cib)


def remove_target(lib_env, target_id):
    """
    Remove acl_target element with id target_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    target_id -- id of taget which should be removed
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    acl.remove_target(cib, target_id)
    lib_env.push_cib(cib)


def remove_group(lib_env, group_id):
    """
    Remove acl_group element with id group_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    group_id -- id of group which should be removed
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    acl.remove_group(cib, group_id)
    lib_env.push_cib(cib)


def add_permission(lib_env, role_id, permission_info_list):
    """
    Add permissions do role with id role_id. If role doesn't exist it will be
    created.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvirnoment
    role_id -- id of role
    permission_info_list -- list of permissons, items of list should be tuples:
        (<read|write|deny>, <xpath|id>, <any string>)
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    acl.validate_permissions(cib, permission_info_list)
    acl.add_permissions_to_role(
        acl.provide_role(cib, role_id), permission_info_list
    )
    lib_env.push_cib(cib)


def remove_permission(lib_env, permission_id):
    """
    Remove permission with id permission_id.
    Raises LibraryError on any failure.

    lib_env -- LibraryEnvironment
    permission_id -- id of permission element which should be removed
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    acl.remove_permission(cib, permission_id)
    lib_env.push_cib(cib)


def get_config(lib_env):
    """
    Returns ACL configuration in disctionary. Fromat of output:
        {
            "target_list": <list of targets>,
            "group_list": <list og groups>,
            "role_list": <list of roles>,
        }

    lib_env -- LibraryEnvironment
    """
    cib = lib_env.get_cib(REQUIRED_CIB_VERSION)
    return {
        "target_list": acl.get_target_list(cib),
        "group_list": acl.get_group_list(cib),
        "role_list": acl.get_role_list(cib),
    }

