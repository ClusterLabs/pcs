from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys

import usage
import utils
import prop
from errors import CmdLineInputError
from errors import ReportItem
from errors import ReportItemSeverity
from errors import error_codes
from errors import LibraryError
from library_acl import create_role
from library_acl import provide_role
from library_acl import add_permissions_to_role

def exit_on_cmdline_input_errror(usage_name):
    usage.acl([usage_name])
    sys.exit(1)

def acl_cmd(argv):
    if len(argv) == 0:
        argv = ["show"]

    sub_cmd = argv.pop(0)

    # If we're using help or show we don't upgrade, otherwise upgrade if necessary
    if sub_cmd not in ["help","show"]:
        utils.checkAndUpgradeCIB(2,0,0)

    if (sub_cmd == "help"):
        usage.acl(argv)
    elif (sub_cmd == "show"):
        acl_show(argv)
    elif (sub_cmd == "enable"):
        acl_enable(argv)
    elif (sub_cmd == "disable"):
        acl_disable(argv)
    elif (sub_cmd == "role"):
        acl_role(argv)
    elif (sub_cmd == "target" or sub_cmd == "user"):
        acl_target(argv)
    elif sub_cmd == "group":
        acl_target(argv, True)
    elif sub_cmd == "permission":
        acl_permission(argv)
    else:
        usage.acl()
        sys.exit(1)

def acl_show(argv):
    dom = utils.get_cib_dom()

    properties = prop.get_set_properties(defaults=prop.get_default_properties())
    acl_enabled = properties.get("enable-acl", "").lower()
    if utils.is_cib_true(acl_enabled):
        print("ACLs are enabled")
    else:
        print("ACLs are disabled, run 'pcs acl enable' to enable")
    print()

    print_targets(dom)
    print_groups(dom)
    print_roles(dom)

def acl_enable(argv):
    prop.set_property(["enable-acl=true"])

def acl_disable(argv):
    prop.set_property(["enable-acl=false"])

def acl_role(argv):
    if len(argv) < 2:
        usage.acl(["role"])
        sys.exit(1)

    command = argv.pop(0)
    if command == "create":
        try:
            run_create_role(argv)
        except CmdLineInputError as e:
            exit_on_cmdline_input_errror('role create')
        except LibraryError as e:
            utils.process_library_reports(e.args)


    elif command == "delete":
        run_role_delete(argv)
    elif command == "assign":
        run_role_assign(argv)
    elif command == "unassign":
        run_role_unassign(argv)
    else:
        usage.acl(["role"])
        sys.exit(1)

def acl_target(argv,group=False):
    if len(argv) < 2:
        if group:
            usage.acl(["group"])
            sys.exit(1)
        else:
            usage.acl(["user"])
            sys.exit(1)

    dom = utils.get_cib_dom()
    acls = utils.get_acls(dom)

    command = argv.pop(0)
    tug_id = argv.pop(0)
    if command == "create":
        # pcsd parses the error message in order to determine whether the id is
        # assigned to user/group or some other cib element
        if group and utils.dom_get_element_with_id(dom, "acl_group", tug_id):
            utils.err("group %s already exists" % tug_id)
        if not group and utils.dom_get_element_with_id(dom, "acl_target", tug_id):
            utils.err("user %s already exists" % tug_id)
        if utils.does_id_exist(dom,tug_id):
            utils.err(tug_id + " already exists")

        if group:
            element = dom.createElement("acl_group")
        else:
            element = dom.createElement("acl_target")
        element.setAttribute("id", tug_id)

        acls.appendChild(element)
        for role in argv:
            if not utils.dom_get_element_with_id(acls, "acl_role", role):
                utils.err("cannot find acl role: %s" % role)
            r = dom.createElement("role")
            r.setAttribute("id", role)
            element.appendChild(r)

        utils.replace_cib_configuration(dom)
    elif command == "delete":
        found = False
        if group:
            elist = dom.getElementsByTagName("acl_group")
        else:
            elist = dom.getElementsByTagName("acl_target")

        for elem in elist:
            if elem.getAttribute("id") == tug_id:
                found = True
                elem.parentNode.removeChild(elem)
                break
        if not found:
            if group:
                utils.err("unable to find acl group: %s" % tug_id)
            else:
                utils.err("unable to find acl target/user: %s" % tug_id)
        utils.replace_cib_configuration(dom)
    else:
        if group:
            usage.acl(["group"])
        else:
            usage.acl(["user"])
        sys.exit(1)

def acl_permission(argv):
    if len(argv) < 1:
        usage.acl(["permission"])
        sys.exit(1)

    command = argv.pop(0)
    if command == "add":
        try:
            run_permission_add(argv)
        except CmdLineInputError as e:
            exit_on_cmdline_input_errror('permission add')
        except LibraryError as e:
            utils.process_library_reports(e.args)

    elif command == "delete":
        run_permission_delete(argv)

    else:
        usage.acl(["permission"])
        sys.exit(1)

def print_groups(dom):
    for elem in dom.getElementsByTagName("acl_group"):
        print("Group: " + elem.getAttribute("id"))
        role_list = []
        for role in elem.getElementsByTagName("role"):
            role_list.append(role.getAttribute("id"))
        print(" ".join(["  Roles:"] + role_list))

def print_targets(dom):
    for elem in dom.getElementsByTagName("acl_target"):
        print("User: " + elem.getAttribute("id"))
        role_list = []
        for role in elem.getElementsByTagName("role"):
            role_list.append(role.getAttribute("id"))
        print(" ".join(["  Roles:"] + role_list))

def print_roles(dom):
    for elem in dom.getElementsByTagName("acl_role"):
        print("Role: " + elem.getAttribute("id"))
        if elem.getAttribute("description"):
            print("  Description: " + elem.getAttribute("description"))
        for perm in elem.getElementsByTagName("acl_permission"):
            perm_name = "  Permission: " + perm.getAttribute("kind")
            if "xpath" in perm.attributes.keys():
                perm_name += " xpath " + perm.getAttribute("xpath")
            elif "reference" in perm.attributes.keys():
                perm_name += " id " + perm.getAttribute("reference")
            perm_name += " (" + perm.getAttribute("id") + ")"
            print(perm_name)

def argv_to_permission_info_list(argv):
    if len(argv) % 3 != 0:
        raise CmdLineInputError()

    permission_info_list = zip(
        [permission.lower() for permission in argv[::3]],
        [scope_type.lower() for scope_type in argv[1::3]],
        argv[2::3]
    )

    for permission, scope_type, scope in permission_info_list:
        if(
            permission not in ['read', 'write', 'deny']
            or
            scope_type not in ['xpath', 'id']
        ):
            raise CmdLineInputError()

    return permission_info_list

def run_create_role(argv):
    if len(argv) < 1:
        raise CmdLineInputError()
    role_id = argv.pop(0)
    description = ""
    desc_key = 'description='
    if argv and argv[0].startswith(desc_key) and len(argv[0]) > len(desc_key):
        description = argv.pop(0)[len(desc_key):]
    permission_info_list = argv_to_permission_info_list(argv)

    dom = utils.get_cib_dom()
    create_role(dom, role_id, description)
    add_permissions_to_role(dom, role_id, permission_info_list)
    utils.replace_cib_configuration(dom)

def run_role_delete(argv):
    if len(argv) < 1:
        usage.acl(["role delete"])
        sys.exit(1)

    role_id = argv.pop(0)
    dom = utils.get_cib_dom()
    found = False
    for elem in dom.getElementsByTagName("acl_role"):
        if elem.getAttribute("id") == role_id:
            found = True
            elem.parentNode.removeChild(elem)
            break
    if not found:
        utils.err("unable to find acl role: %s" % role_id)

    # Remove any references to this role in acl_target or acl_group
    for elem in dom.getElementsByTagName("role"):
        if elem.getAttribute("id") == role_id:
            user_group = elem.parentNode
            user_group.removeChild(elem)
            if "--autodelete" in utils.pcs_options:
                if not user_group.getElementsByTagName("role"):
                    user_group.parentNode.removeChild(user_group)

    utils.replace_cib_configuration(dom)

def run_role_assign(argv):
    if len(argv) < 2:
        usage.acl(["role assign"])
        sys.exit(1)

    if len(argv) == 2:
        role_id = argv[0]
        ug_id = argv[1]
    elif len(argv) > 2 and argv[1] == "to":
        role_id = argv[0]
        ug_id = argv[2]
    else:
        usage.acl(["role assign"])
        sys.exit(1)

    dom = utils.get_cib_dom()
    found = False
    for role in dom.getElementsByTagName("acl_role"):
        if role.getAttribute("id") == role_id:
            found = True
            break

    if not found:
        utils.err("cannot find role: %s" % role_id)

    found = False
    for ug in dom.getElementsByTagName("acl_target") + dom.getElementsByTagName("acl_group"):
        if ug.getAttribute("id") == ug_id:
            found = True
            break

    if not found:
        utils.err("cannot find user or group: %s" % ug_id)

    for current_role in ug.getElementsByTagName("role"):
        if current_role.getAttribute("id") == role_id:
            utils.err(role_id + " is already assigned to " + ug_id)

    new_role = dom.createElement("role")
    new_role.setAttribute("id", role_id)
    ug.appendChild(new_role)
    utils.replace_cib_configuration(dom)

def run_role_unassign(argv):
    if len(argv) < 2:
        usage.acl(["role unassign"])
        sys.exit(1)

    role_id = argv.pop(0)
    if len(argv) > 1 and argv[0] == "from":
        ug_id = argv[1]
    else:
        ug_id = argv[0]

    dom = utils.get_cib_dom()
    found = False
    for ug in dom.getElementsByTagName("acl_target") + dom.getElementsByTagName("acl_group"):
        if ug.getAttribute("id") == ug_id:
            found = True
            break

    if not found:
        utils.err("cannot find user or group: %s" % ug_id)

    found = False
    for current_role in ug.getElementsByTagName("role"):
        if current_role.getAttribute("id") == role_id:
            found = True
            current_role.parentNode.removeChild(current_role)
            break

    if not found:
        utils.err("cannot find role: %s, assigned to user/group: %s" % (role_id, ug_id))

    if "--autodelete" in utils.pcs_options:
        if not ug.getElementsByTagName("role"):
            ug.parentNode.removeChild(ug)

    utils.replace_cib_configuration(dom)

def run_permission_add(argv):
    if len(argv) < 4:
        raise CmdLineInputError()
    role_id = argv.pop(0)
    permission_info_list = argv_to_permission_info_list(argv)

    dom = utils.get_cib_dom()
    provide_role(dom, role_id)
    add_permissions_to_role(dom, role_id, permission_info_list)
    utils.replace_cib_configuration(dom)

def run_permission_delete(argv):
    dom = utils.get_cib_dom()
    if len(argv) < 1:
        usage.acl(["permission delete"])
        sys.exit(1)

    perm_id = argv.pop(0)
    found = False
    for elem in dom.getElementsByTagName("acl_permission"):
        if elem.getAttribute("id") == perm_id:
            elem.parentNode.removeChild(elem)
            found = True
    if not found:
        utils.err("Unable to find permission with id: %s" % perm_id)

    utils.replace_cib_configuration(dom)
