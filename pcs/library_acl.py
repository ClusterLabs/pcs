from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import utils
from errors import ReportItem
from errors import ReportItemSeverity
from errors import error_codes
from errors import LibraryError

class AclRoleNotFound(LibraryError):
    pass

def __validate_role_id_for_create(dom, role_id):
    id_valid, message = utils.validate_xml_id(role_id, 'ACL role')
    if not id_valid:
        raise LibraryError(ReportItem.error(
            error_codes.ID_IS_NOT_VALID,
            message,
            info={'id': role_id}
        ))
    if utils.dom_get_element_with_id(dom, "acl_role", role_id):
        raise LibraryError(ReportItem.error(
            error_codes.ACL_ROLE_ALREADY_EXISTS,
            'role {id} already exists',
            info={'id': role_id}
        ))
    if utils.does_id_exist(dom, role_id):
        raise LibraryError(ReportItem.error(
            error_codes.ID_ALREADY_EXISTS,
            '{id} already exists',
            info={'id': role_id}
        ))

def __validate_permissions(dom, permission_info_list):
    report = []
    allowed_permissions = ["read", "write", "deny"]
    allowed_scopes = ["xpath", "id"]
    for permission, scope_type, scope in permission_info_list:
        if not permission in allowed_permissions:
            report.append(ReportItem.error(
                error_codes.BAD_ACL_PERMISSION,
                'bad permission "{permission}, expected {allowed_values}',
                info={
                    'permission': permission,
                    'allowed_values_raw': allowed_permissions,
                    'allowed_values': ' or '.join(allowed_permissions)
                },
            ))

        if not scope_type in allowed_scopes:
            report.append(ReportItem.error(
                error_codes.BAD_ACL_SCOPE_TYPE,
                'bad scope type "{scope_type}, expected {allowed_values}',
                info={
                    'scope_type': scope_type,
                    'allowed_values_raw': allowed_scopes,
                    'allowed_values': ' or '.join(allowed_scopes)
                },
            ))

        if scope_type == 'id' and not utils.does_id_exist(dom, scope):
            report.append(ReportItem.error(
                error_codes.ID_NOT_FOUND,
                'id "{id}" does not exist.',
                info={'id': scope },
            ))

    if report:
        raise LibraryError(*report)

def __find_role(dom, role_id):
    for role in dom.getElementsByTagName("acl_role"):
        if role.getAttribute("id") == role_id:
            return role

    raise AclRoleNotFound(ReportItem.error(
        error_codes.ACL_ROLE_NOT_FOUND,
        'role id "{role_id}" does not exist.',
        info={'role_id': role_id},
    ))

def create_role(dom, role_id, description=''):
    """
    role_id id of desired role
    description role description
    """
    __validate_role_id_for_create(dom, role_id)
    role = dom.createElement("acl_role")
    role.setAttribute("id",role_id)
    if description != "":
        role.setAttribute("description", description)
    acls = utils.get_acls(dom)
    acls.appendChild(role)

def provide_role(dom, role_id):
    """
    role_id id of desired role
    description role description
    """
    try:
        __find_role(dom, role_id)
    except AclRoleNotFound:
        create_role(dom, role_id)

def add_permissions_to_role(dom, role_id, permission_info_list):
    """
    dom document node
    role_id value of atribute id, which exists in dom
    permission_info_list list of tuples,
        each contains (permission, scope_type, scope)
    """
    __validate_permissions(dom, permission_info_list)

    area_type_attribute_map = {
        'xpath': 'xpath',
        'id': 'reference',
    }
    for permission, scope_type, scope in permission_info_list:
        se = dom.createElement("acl_permission")
        se.setAttribute(
            "id",
            utils.find_unique_id(dom, role_id + "-" + permission)
        )
        se.setAttribute("kind", permission)
        se.setAttribute(area_type_attribute_map[scope_type], scope)
        __find_role(dom, role_id).appendChild(se)

def remove_permissions_referencing(dom, reference):
    for permission in dom.getElementsByTagName("acl_permission"):
        if permission.getAttribute("reference") == reference:
            permission.parentNode.removeChild(permission)
