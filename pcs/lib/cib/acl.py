from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib import reports
from pcs.lib.errors import LibraryError
from pcs.lib.cib.tools import (
    etree_element_attibutes_to_dict,
    check_new_id_applicable,
    does_id_exist,
    find_unique_id,
    get_acls,
)


class AclError(Exception):
    pass


class AclRoleNotFound(AclError):
    # pylint: disable=super-init-not-called
    def __init__(self, role_id):
        self.role_id = role_id


class AclTargetNotFound(AclError):
    # pylint: disable=super-init-not-called
    def __init__(self, target_id):
        self.target_id = target_id


class AclGroupNotFound(AclError):
    # pylint: disable=super-init-not-called
    def __init__(self, group_id):
        self.group_id = group_id


def validate_permissions(tree, permission_info_list):
    """
    Validate given permission list.
    Raise LibraryError if any of permission is not valid.

    tree -- cib tree
    permission_info_list -- list of tuples like this:
        ("read|write|deny", "xpath|id", <id-or-xpath-string>)
    """
    report_items = []
    allowed_permissions = ["read", "write", "deny"]
    allowed_scopes = ["xpath", "id"]
    for permission, scope_type, scope in permission_info_list:
        if not permission in allowed_permissions:
            report_items.append(reports.invalid_option_value(
                "permission",
                permission,
                allowed_permissions
            ))

        if not scope_type in allowed_scopes:
            report_items.append(reports.invalid_option_value(
                "scope type",
                scope_type,
                allowed_scopes
            ))

        if scope_type == 'id' and not does_id_exist(tree, scope):
            report_items.append(reports.id_not_found(scope, "id"))

    if report_items:
        raise LibraryError(*report_items)


def find_role(tree, role_id):
    """
    Returns acl_role element with specified role_id in given tree.
    Raise AclRoleNotFound if role doesn't exist.

    tree -- etree node
    role_id -- id of role
    """
    role = tree.find('.//acl_role[@id="{0}"]'.format(role_id))
    if role is not None:
        return role
    raise AclRoleNotFound(role_id)


def _find_permission(tree, permission_id):
    """
    Returns acl_permission element with specified id.
    Raises LibraryError if that permission doesn't exist.

    tree -- etree node
    permisson_id -- id of permision element
    """
    permission = tree.find(".//acl_permission[@id='{0}']".format(permission_id))
    if permission is not None:
        return permission
    raise LibraryError(reports.id_not_found(permission_id, "permission"))


def create_role(tree, role_id, description=None):
    """
    Create new role element and add it to cib.
    Returns newly created role element.

    role_id id of desired role
    description role description
    """
    check_new_id_applicable(tree, "ACL role", role_id)
    role = etree.SubElement(get_acls(tree), "acl_role", id=role_id)
    if description:
        role.set("description", description)
    return role


def remove_role(tree, role_id, autodelete_users_groups=False):
    """
    Remove role with specified id from CIB and all references to it.

    tree -- etree node
    role_id -- id of role to be removed
    autodelete_users_group -- if True remove targets with no role after removing
    """
    acl_role = find_role(tree, role_id)
    acl_role.getparent().remove(acl_role)
    for role_el in tree.findall(".//role[@id='{0}']".format(role_id)):
        role_parent = role_el.getparent()
        role_parent.remove(role_el)
        if autodelete_users_groups and role_parent.find(".//role") is None:
            role_parent.getparent().remove(role_parent)


def assign_role(target_el, role_el):
    """
    Assign role element to specified target/group element.
    Raise LibraryError if role is already assigned to target/group.

    target_el -- etree element of target/group to which role should be assign
    role_el -- etree element of role
    """
    assigned_role = target_el.find(
        "./role[@id='{0}']".format(role_el.get("id"))
    )
    if assigned_role is not None:
        raise LibraryError(reports.acl_role_is_already_assigned_to_target(
            role_el.get("id"), target_el.get("id")
        ))
    etree.SubElement(target_el, "role", {"id": role_el.get("id")})


def unassign_role(target_el, role_id, autodelete_target=False):
    """
    Unassign role with role_id from specified target/user target_el.
    Raise LibraryError if role is not assigned to target/group.

    target_el -- etree element of target/group from which role should be
        unassign
    role_id -- id of role
    autodelete_target -- if True remove target_el if there is no role assigned
    """
    assigned_role = target_el.find("./role[@id='{0}']".format(role_id))
    if assigned_role is None:
        raise LibraryError(reports.acl_role_is_not_assigned_to_target(
            role_id, target_el.get("id")
        ))
    target_el.remove(assigned_role)
    if autodelete_target and target_el.find("./role") is None:
        target_el.getparent().remove(target_el)


def find_target(tree, target_id):
    """
    Return acl_target etree element with specified id.
    Raise AclTargetNotFound if target with specified id doesn't exist.

    tree -- etree node
    target_id -- if of target to find
    """
    role = get_acls(tree).find('./acl_target[@id="{0}"]'.format(target_id))
    if role is None:
        raise AclTargetNotFound(target_id)
    return role


def find_group(tree, group_id):
    """
    Returns acl_group etree element with specified id.
    Raise AclGroupNotFound if group with group_id doesn't exist.

    tree -- etree node
    group_id -- id of group to find
    """
    role = get_acls(tree).find('./acl_group[@id="{0}"]'.format(group_id))
    if role is None:
        raise AclGroupNotFound(group_id)
    return role


def provide_role(tree, role_id):
    """
    Returns role with id role_id. If doesn't exist, it will be created.
    role_id id of desired role
    """
    try:
        return find_role(tree, role_id)
    except AclRoleNotFound:
        return create_role(tree, role_id)


def create_target(tree, target_id):
    """
    Creates new acl_target element with id target_id.
    Raises LibraryError if target with wpecified id aleready exists.

    tree -- etree node
    target_id -- id of new target
    """
    acl_el = get_acls(tree)
    # id of element acl_target is not type ID in CIB ACL schema so we don't need
    # to check if it is unique ID in whole CIB
    if acl_el.find("./acl_target[@id='{0}']".format(target_id)) is not None:
        raise LibraryError(reports.acl_target_already_exists(target_id))
    return etree.SubElement(get_acls(tree), "acl_target", id=target_id)


def create_group(tree, group_id):
    """
    Creates new acl_group element with specified id.
    Raises LibraryError if tree contains element with id group_id.

    tree -- etree node
    group_id -- id of new group
    """
    check_new_id_applicable(tree, "ACL group", group_id)
    return etree.SubElement(get_acls(tree), "acl_group", id=group_id)


def remove_target(tree, target_id):
    """
    Removes acl_target element from tree with specified id.
    Raises LibraryError if target with id target_id doesn't exist.

    tree -- etree node
    target_id -- id of target element to remove
    """
    try:
        target = find_target(tree, target_id)
        target.getparent().remove(target)
    except AclTargetNotFound:
        raise LibraryError(reports.id_not_found(target_id, "user"))


def remove_group(tree, group_id):
    """
    Removes acl_group element from tree with specified id.
    Raises LibraryError if group with id group_id doesn't exist.

    tree -- etree node
    group_id -- id of group element to remove
    """
    try:
        group = find_group(tree, group_id)
        group.getparent().remove(group)
    except AclGroupNotFound:
        raise LibraryError(reports.id_not_found(group_id, "group"))


def add_permissions_to_role(role_el, permission_info_list):
    """
    Add permissions from permission_info_list to role_el.

    role_el -- acl_role element to which permissions should be added
    permission_info_list -- list of tuples,
        each contains (permission, scope_type, scope)
    """
    area_type_attribute_map = {
        'xpath': 'xpath',
        'id': 'reference',
    }
    for permission, scope_type, scope in permission_info_list:
        perm = etree.SubElement(role_el, "acl_permission")
        perm.set(
            "id",
            find_unique_id(
                role_el,
                "{0}-{1}".format(role_el.get("id", "role"), permission)
            )
        )
        perm.set("kind", permission)
        perm.set(area_type_attribute_map[scope_type], scope)


def remove_permission(tree, permission_id):
    """
    Remove permission with id permission_id from tree.

    tree -- etree node
    permission_id -- id of permission element to be removed
    """
    permission = _find_permission(tree, permission_id)
    permission.getparent().remove(permission)


def get_role_list(tree):
    """
    Returns list of all acl_role elements from tree.
    Format of items of output list:
        {
            "id": <role-id>,
            "description": <role-description>,
            "permission_list": [<see function _get_all_permission_list>, ...]
        }

    tree -- etree node
    """
    output_list = []
    for role_el in get_acls(tree).findall("./acl_role"):
        role = etree_element_attibutes_to_dict(
            role_el, ["id", "description"]
        )
        role["permission_list"] = _get_permission_list(role_el)
        output_list.append(role)
    return output_list


def _get_permission_list(role_el):
    """
    Return list of all permissions of role element role_el.
    Format of item of output list (if attribute is misssing in element under its
    key there is None):
        {
            "id": <id of permission element>,
            "description": <permission description>,
            "kind": <read|write|deny>,
            "xpath": <xpath string>,
            "reference": <cib element id>,
            "object-type": <>,
            "attribute": <>,
        }

    role_el -- acl_role etree element of which permissions whould be returned
    """
    output_list = []
    for permission in role_el.findall("./acl_permission"):
        output_list.append(etree_element_attibutes_to_dict(
            permission,
            [
                "id", "description", "kind", "xpath", "reference",
                "object-type", "attribute"
            ]
        ))
    return output_list


def get_target_list(tree):
    """
    Returns list of acl_target elements in format:
        {
            "id": <target id>,
            "role_list": [<assign role_id as string>, ...]
        }

    tree -- etree node
    """
    return _get_target_like_list_with_tag(tree, "acl_target")


def get_group_list(tree):
    """
    Returns list of acl_group elements in format:
        {
            "id": <group id>,
            "role_list": [<assign role_id as string>, ...]
        }

    tree -- etree node
    """
    return _get_target_like_list_with_tag(tree, "acl_group")


def _get_target_like_list_with_tag(tree, tag):
    output_list = []
    for target_el in get_acls(tree).findall("./{0}".format(tag)):
        output_list.append({
            "id": target_el.get("id"),
            "role_list": _get_role_list_of_target(target_el),
        })
    return output_list


def _get_role_list_of_target(target):
    """
    Returns all roles assigned to target element as list of strings.

    target -- etree acl_target/acl_group element of which roles should be
        returned
    """
    return [
        role.get("id") for role in target.findall("./role") if role.get("id")
    ]


def remove_permissions_referencing(tree, reference):
    """
    Removes all permission with specified reference.

    tree -- etree node
    reference -- reference identifier
    """
    xpath = './/acl_permission[@reference="{0}"]'.format(reference)
    for permission in tree.findall(xpath):
        permission.getparent().remove(permission)


def dom_remove_permissions_referencing(dom, reference):
    # TODO: remove once we go fully lxml
    for permission in dom.getElementsByTagName("acl_permission"):
        if permission.getAttribute("reference") == reference:
            permission.parentNode.removeChild(permission)


def acl_error_to_report_item(e):
    if e.__class__ == AclTargetNotFound:
        return reports.id_not_found(e.target_id, "user")
    elif e.__class__ == AclGroupNotFound:
        return reports.id_not_found(e.group_id, "group")
    elif e.__class__ == AclRoleNotFound:
        return reports.id_not_found(e.role_id, "role")
    raise e
