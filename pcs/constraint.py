from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import sys
import xml.dom.minidom
from xml.dom.minidom import parseString
from collections import defaultdict

import usage
import utils
import resource
import rule as rule_utils


OPTIONS_ACTION = ("start", "promote", "demote", "stop")
DEFAULT_ACTION = "start"
OPTIONS_ROLE = ("Stopped", "Started", "Master", "Slave")
DEFAULT_ROLE = "Started"
OPTIONS_KIND = ("Optional", "Mandatory", "Serialize")
OPTIONS_SYMMETRICAL = ("true", "false")

def constraint_cmd(argv):
    if len(argv) == 0:
        argv = ["list"]

    sub_cmd = argv.pop(0)
    if (sub_cmd == "help"):
        usage.constraint(argv)
    elif (sub_cmd == "location"):
        if len (argv) == 0:
            sub_cmd2 = "show"
        else:
            sub_cmd2 = argv.pop(0)

        if (sub_cmd2 == "add"):
            location_add(argv)
        elif (sub_cmd2 in ["remove","delete"]):
            location_add(argv,True)
        elif (sub_cmd2 == "show"):
            location_show(argv)
        elif len(argv) >= 2:
            if argv[0] == "rule":
                location_rule([sub_cmd2] + argv)
            else:
                location_prefer([sub_cmd2] + argv)
        else:
            usage.constraint()
            sys.exit(1)
    elif (sub_cmd == "order"):
        if (len(argv) == 0):
            sub_cmd2 = "show"
        else:
            sub_cmd2 = argv.pop(0)

        if (sub_cmd2 == "set"):
            order_set(argv)
        elif (sub_cmd2 in ["remove","delete"]):
            order_rm(argv)
        elif (sub_cmd2 == "show"):
            order_show(argv)
        else:
            order_start([sub_cmd2] + argv)
    elif (sub_cmd == "colocation"):
        if (len(argv) == 0):
            sub_cmd2 = "show"
        else:
            sub_cmd2 = argv.pop(0)

        if (sub_cmd2 == "add"):
            colocation_add(argv)
        elif (sub_cmd2 in ["remove","delete"]):
            colocation_rm(argv)
        elif (sub_cmd2 == "set"):
            colocation_set(argv)
        elif (sub_cmd2 == "show"):
            colocation_show(argv)
        else:
            usage.constraint()
            sys.exit(1)
    elif (sub_cmd in ["remove","delete"]):
        constraint_rm(argv)
    elif (sub_cmd == "show" or sub_cmd == "list"):
        location_show(argv)
        order_show(argv)
        colocation_show(argv)
    elif (sub_cmd == "ref"):
        constraint_ref(argv)
    elif (sub_cmd == "rule"):
        constraint_rule(argv)
    else:
        usage.constraint()
        sys.exit(1)

def colocation_show(argv):
    if "--full" in utils.pcs_options:
        showDetail = True
    else:
        showDetail = False

    (dom,constraintsElement) = getCurrentConstraints()

    resource_colocation_sets = []
    print("Colocation Constraints:")
    for co_loc in constraintsElement.getElementsByTagName('rsc_colocation'):
        if not co_loc.getAttribute("rsc"):
            resource_colocation_sets.append(co_loc)
        else:
            print("  " + colocation_el_to_string(co_loc, showDetail))
    print_sets(resource_colocation_sets, showDetail)

def colocation_el_to_string(co_loc, showDetail=False):
    co_resource1 = co_loc.getAttribute("rsc")
    co_resource2 = co_loc.getAttribute("with-rsc")
    co_id = co_loc.getAttribute("id")
    co_score = co_loc.getAttribute("score")
    score_text = "(score:" + co_score + ")"
    attrs_list = [
        "(%s:%s)" % (attr[0], attr[1])
        for attr in co_loc.attributes.items()
        if attr[0] not in ("rsc", "with-rsc", "id", "score")
    ]
    if showDetail:
        attrs_list.append("(id:%s)" % co_id)
    return " ".join(
        [co_resource1, "with", co_resource2, score_text] + attrs_list
    )

def colocation_rm(argv):
    elementFound = False
    if len(argv) < 2:
        usage.constraint()
        sys.exit(1)

    (dom,constraintsElement) = getCurrentConstraints()

    resource1 = argv[0]
    resource2 = argv[1]

    for co_loc in constraintsElement.getElementsByTagName('rsc_colocation')[:]:
        if co_loc.getAttribute("rsc") == resource1 and co_loc.getAttribute("with-rsc") == resource2:
            constraintsElement.removeChild(co_loc)
            elementFound = True
        if co_loc.getAttribute("rsc") == resource2 and co_loc.getAttribute("with-rsc") == resource1:
            constraintsElement.removeChild(co_loc)
            elementFound = True

    if elementFound == True:
        utils.replace_cib_configuration(dom)
    else:
        print("No matching resources found in ordering list")


# When passed an array of arguments if the first argument doesn't have an '='
# then it's the score, otherwise they're all arguments
# Return a tuple with the score and array of name,value pairs
def parse_score_options(argv):
    if len(argv) == 0:
        return "INFINITY",[]

    arg_array = []
    first = argv[0]
    if first.find('=') != -1:
        score = "INFINITY"
    else:
        score = argv.pop(0)

    for arg in argv:
        args = arg.split('=')
        if (len(args) != 2):
            continue
        arg_array.append(args)
    return (score, arg_array)

# There are two acceptable syntaxes
# Deprecated - colocation add <src> <tgt> [score] [options]
# Supported - colocation add [role] <src> with [role] <tgt> [score] [options]
def colocation_add(argv):
    if len(argv) < 2:
        usage.constraint()
        sys.exit(1)

    role1 = ""
    role2 = ""
    if len(argv) > 2:
        if not utils.is_score_or_opt(argv[2]):
            if argv[2] == "with":
                role1 = argv.pop(0).lower().capitalize()
                resource1 = argv.pop(0)
            else:
                resource1 = argv.pop(0)

            argv.pop(0) # Pop 'with'

            if len(argv) == 1:
                resource2 = argv.pop(0)
            else:
                if utils.is_score_or_opt(argv[1]):
                    resource2 = argv.pop(0)
                else:
                    role2 = argv.pop(0).lower().capitalize()
                    resource2 = argv.pop(0)
        else:
            resource1 = argv.pop(0)
            resource2 = argv.pop(0)
    else:
        resource1 = argv.pop(0)
        resource2 = argv.pop(0)

    cib_dom = utils.get_cib_dom()
    resource_valid, resource_error, correct_id \
        = utils.validate_constraint_resource(cib_dom, resource1)
    if "--autocorrect" in utils.pcs_options and correct_id:
        resource1 = correct_id
    elif not resource_valid:
        utils.err(resource_error)
    resource_valid, resource_error, correct_id \
        = utils.validate_constraint_resource(cib_dom, resource2)
    if "--autocorrect" in utils.pcs_options and correct_id:
        resource2 = correct_id
    elif not resource_valid:
        utils.err(resource_error)

    score,nv_pairs = parse_score_options(argv)
    id_in_nvpairs = None
    for name, value in nv_pairs:
        if name == "id":
            id_valid, id_error = utils.validate_xml_id(value, 'constraint id')
            if not id_valid:
                utils.err(id_error)
            if utils.does_id_exist(cib_dom, value):
                utils.err(
                    "id '%s' is already in use, please specify another one"
                    % value
                )
            id_in_nvpairs = True
    if not id_in_nvpairs:
        nv_pairs.append((
            "id",
            utils.find_unique_id(
                cib_dom,
                "colocation-%s-%s-%s" % (resource1, resource2, score)
            )
        ))

    (dom,constraintsElement) = getCurrentConstraints(cib_dom)

# If one role is specified, the other should default to "started"
    if role1 != "" and role2 == "":
        role2 = DEFAULT_ROLE
    if role2 != "" and role1 == "":
        role1 = DEFAULT_ROLE

    element = dom.createElement("rsc_colocation")
    element.setAttribute("rsc",resource1)
    element.setAttribute("with-rsc",resource2)
    element.setAttribute("score",score)
    if role1 != "":
        element.setAttribute("rsc-role", role1)
    if role2 != "":
        element.setAttribute("with-rsc-role", role2)
    for nv_pair in nv_pairs:
        element.setAttribute(nv_pair[0], nv_pair[1])
    if "--force" not in utils.pcs_options:
        duplicates = colocation_find_duplicates(constraintsElement, element)
        if duplicates:
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join([
                    "  " + colocation_el_to_string(dup, True)
                    for dup in duplicates
                ])
            )
    constraintsElement.appendChild(element)
    utils.replace_cib_configuration(dom)

def colocation_find_duplicates(dom, constraint_el):
    def normalize(const_el):
        return (
            const_el.getAttribute("rsc"),
            const_el.getAttribute("with-rsc"),
            const_el.getAttribute("rsc-role").capitalize() or DEFAULT_ROLE,
            const_el.getAttribute("with-rsc-role").capitalize() or DEFAULT_ROLE,
        )

    normalized_el = normalize(constraint_el)
    return [
        other_el
        for other_el in dom.getElementsByTagName("rsc_colocation")
        if not other_el.getElementsByTagName("resource_set")
            and constraint_el is not other_el
            and normalized_el == normalize(other_el)
    ]

def colocation_set(argv):
    setoptions = []
    for i in range(len(argv)):
        if argv[i] == "setoptions":
            setoptions = argv[i+1:]
            argv[i:] = []
            break

    argv.insert(0, "set")
    resource_sets = set_args_into_array(argv)
    if not check_empty_resource_sets(resource_sets):
        usage.constraint(["colocation set"])
        sys.exit(1)
    cib, constraints = getCurrentConstraints(utils.get_cib_dom())

    attributes = []
    score_options = ("score", "score-attribute", "score-attribute-mangle")
    score_specified = False
    id_specified = False
    for opt in setoptions:
        if "=" not in opt:
            utils.err("missing value of '%s' option" % opt)
        name, value = opt.split("=", 1)
        if name == "id":
            id_valid, id_error = utils.validate_xml_id(value, 'constraint id')
            if not id_valid:
                utils.err(id_error)
            if utils.does_id_exist(cib, value):
                utils.err(
                    "id '%s' is already in use, please specify another one"
                    % value
                )
            id_specified = True
            attributes.append((name, value))
        elif name in score_options:
            if score_specified:
                utils.err("you cannot specify multiple score options")
            if name == "score" and not utils.is_score(value):
                utils.err(
                    "invalid score '%s', use integer or INFINITY or -INFINITY"
                    % value
                )
            score_specified = True
            attributes.append((name, value))
        else:
            utils.err(
                "invalid option '%s', allowed options are: %s"
                % (name, ", ".join(score_options + ("id",)))
            )

    if not score_specified:
        attributes.append(("score", "INFINITY"))
    if not id_specified:
        colocation_id = "pcs_rsc_colocation"
        for a in argv:
            if "=" not in a:
                colocation_id += "_" + a
        attributes.append(("id", utils.find_unique_id(cib, colocation_id)))

    rsc_colocation = cib.createElement("rsc_colocation")
    for name, value in attributes:
        rsc_colocation.setAttribute(name, value)
    set_add_resource_sets(rsc_colocation, resource_sets, cib)
    constraints.appendChild(rsc_colocation)
    utils.replace_cib_configuration(cib)

def order_show(argv):
    if "--full" in utils.pcs_options:
        showDetail = True
    else:
        showDetail = False

    (dom,constraintsElement) = getCurrentConstraints()

    resource_order_sets = []
    print("Ordering Constraints:")
    for ord_loc in constraintsElement.getElementsByTagName('rsc_order'):
        if not ord_loc.getAttribute("first"):
            resource_order_sets.append(ord_loc)
        else:
            print("  " + order_el_to_string(ord_loc, showDetail))
    print_sets(resource_order_sets,showDetail)

def order_el_to_string(ord_loc, showDetail=False):
    oc_resource1 = ord_loc.getAttribute("first")
    oc_resource2 = ord_loc.getAttribute("then")
    first_action = ord_loc.getAttribute("first-action")
    then_action = ord_loc.getAttribute("then-action")
    oc_id = ord_loc.getAttribute("id")
    oc_score = ord_loc.getAttribute("score")
    oc_kind = ord_loc.getAttribute("kind")
    oc_sym = ""
    oc_id_out = ""
    oc_options = ""
    if (
        ord_loc.getAttribute("symmetrical")
        and
        not utils.is_cib_true(ord_loc.getAttribute("symmetrical"))
    ):
        oc_sym = "(non-symmetrical)"
    if oc_kind != "":
        score_text = "(kind:" + oc_kind + ")"
    elif oc_kind == "" and oc_score == "":
        score_text = "(kind:Mandatory)"
    else:
        score_text = "(score:" + oc_score + ")"
    if showDetail:
        oc_id_out = "(id:"+oc_id+")"
    already_processed_attrs = (
        "first", "then", "first-action", "then-action", "id", "score", "kind",
        "symmetrical"
    )
    oc_options = " ".join([
        "{0}={1}".format(name, value)
        for name, value in ord_loc.attributes.items()
        if name not in already_processed_attrs
    ])
    if oc_options:
        oc_options = "(Options: " + oc_options + ")"
    return " ".join([arg for arg in [
        first_action, oc_resource1, "then", then_action, oc_resource2,
        score_text, oc_sym, oc_options, oc_id_out
    ] if arg])

def print_sets(sets,showDetail):
    if len(sets) != 0:
        print("  Resource Sets:")
        for ro in sets:
            print("    " + set_constraint_el_to_string(ro, showDetail))

def set_constraint_el_to_string(constraint_el, showDetail=False):
    set_list = []
    for set_el in constraint_el.getElementsByTagName("resource_set"):
        set_list.append("set " + " ".join(
            [
                res_el.getAttribute("id")
                for res_el in set_el.getElementsByTagName("resource_ref")
            ]
            +
            utils.dom_attrs_to_list(set_el, showDetail)
        ))
    constraint_opts = utils.dom_attrs_to_list(constraint_el, False)
    if constraint_opts:
        constraint_opts.insert(0, "setoptions")
    if showDetail:
        constraint_opts.append("(id:%s)" % constraint_el.getAttribute("id"))
    return " ".join(set_list + constraint_opts)

def set_args_into_array(argv):
    all_sets = []
    current_set = None
    for elem in argv:
        if "set" == elem:
            if current_set is not None:
                all_sets.append(current_set)
            current_set = []
        else:
            current_set.append(elem)
    if current_set is not None:
        all_sets.append(current_set)
    return all_sets

def check_empty_resource_sets(sets):
    if not sets:
        return False
    return all(sets)

def set_add_resource_sets(elem, sets, cib):
    allowed_options = {
        "sequential": ("true", "false"),
        "require-all": ("true", "false"),
        "action" : OPTIONS_ACTION,
        "role" : OPTIONS_ROLE,
    }

    for o_set in sets:
        set_id = "pcs_rsc_set"
        res_set = cib.createElement("resource_set")
        elem.appendChild(res_set)
        for opts in o_set:
            if opts.find("=") != -1:
                key,val = opts.split("=")
                if key not in allowed_options:
                    utils.err(
                        "invalid option '%s', allowed options are: %s"
                        % (key, ", ".join(allowed_options.keys()))
                    )
                if val not in allowed_options[key]:
                    utils.err(
                        "invalid value '%s' of option '%s', allowed values are: %s"
                        % (val, key, ", ".join(allowed_options[key]))
                    )
                res_set.setAttribute(key, val)
            else:
                res_valid, res_error, correct_id \
                    = utils.validate_constraint_resource(cib, opts)
                if "--autocorrect" in utils.pcs_options and correct_id:
                    opts = correct_id
                elif not res_valid:
                    utils.err(res_error)
                se = cib.createElement("resource_ref")
                res_set.appendChild(se)
                se.setAttribute("id", opts)
                set_id = set_id + "_" + opts
        res_set.setAttribute("id", utils.find_unique_id(cib, set_id))
    if "--force" not in utils.pcs_options:
        duplicates = set_constraint_find_duplicates(cib, elem)
        if duplicates:
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join([
                    "  " + set_constraint_el_to_string(dup, True)
                    for dup in duplicates
                ])
            )

def set_constraint_find_duplicates(dom, constraint_el):
    def normalize(constraint_el):
        return [
            [
                ref_el.getAttribute("id")
                for ref_el in set_el.getElementsByTagName("resource_ref")
            ]
            for set_el in constraint_el.getElementsByTagName("resource_set")
        ]

    normalized_el = normalize(constraint_el)
    return [
        other_el
        for other_el in dom.getElementsByTagName(constraint_el.tagName)
        if other_el.getElementsByTagName("resource_set")
            and constraint_el is not other_el
            and normalized_el == normalize(other_el)
    ]

def order_set(argv):
    setoptions = []
    for i in range(len(argv)):
        if argv[i] == "setoptions":
            setoptions = argv[i+1:]
            argv[i:] = []
            break

    argv.insert(0, "set")
    resource_sets = set_args_into_array(argv)
    if not check_empty_resource_sets(resource_sets):
        usage.constraint(["order set"])
        sys.exit(1)
    cib, constraints = getCurrentConstraints(utils.get_cib_dom())

    attributes = []
    id_specified = False
    for opt in setoptions:
        if "=" not in opt:
            utils.err("missing value of '%s' option" % opt)
        name, value = opt.split("=", 1)
        if name == "id":
            id_valid, id_error = utils.validate_xml_id(value, 'constraint id')
            if not id_valid:
                utils.err(id_error)
            if utils.does_id_exist(cib, value):
                utils.err(
                    "id '%s' is already in use, please specify another one"
                    % value
                )
            id_specified = True
            attributes.append((name, value))
        elif name == "kind":
            normalized_value = value.lower().capitalize()
            if normalized_value not in OPTIONS_KIND:
                utils.err(
                    "invalid kind value '%s', allowed values are: %s"
                    % (value, ", ".join(OPTIONS_KIND))
                )
            attributes.append((name, normalized_value))
        elif name == "symmetrical":
            if value.lower() not in OPTIONS_SYMMETRICAL:
                utils.err(
                    "invalid symmetrical value '%s', allowed values are: %s"
                    % (value, ", ".join(OPTIONS_SYMMETRICAL))
                )
            attributes.append((name, value.lower()))
        else:
            utils.err(
                "invalid option '%s', allowed options are: %s"
                % (name, "kind, symmetrical, id")
            )

    if not id_specified:
        order_id = "pcs_rsc_order"
        for a in argv:
            if "=" not in a:
                order_id += "_" + a
        attributes.append(("id", utils.find_unique_id(cib, order_id)))

    rsc_order = cib.createElement("rsc_order")
    for name, value in attributes:
        rsc_order.setAttribute(name, value)
    set_add_resource_sets(rsc_order, resource_sets, cib)
    constraints.appendChild(rsc_order)
    utils.replace_cib_configuration(cib)

def order_rm(argv):
    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)

    elementFound = False
    (dom,constraintsElement) = getCurrentConstraints()

    for resource in argv:
        for ord_loc in constraintsElement.getElementsByTagName('rsc_order')[:]:
            if ord_loc.getAttribute("first") == resource or ord_loc.getAttribute("then") == resource:
                constraintsElement.removeChild(ord_loc)
                elementFound = True

        resource_refs_to_remove = []
        for ord_set in constraintsElement.getElementsByTagName('resource_ref'):
            if ord_set.getAttribute("id") == resource:
                resource_refs_to_remove.append(ord_set)
                elementFound = True

        for res_ref in resource_refs_to_remove:
            res_set = res_ref.parentNode
            res_order = res_set.parentNode

            res_ref.parentNode.removeChild(res_ref)
            if len(res_set.getElementsByTagName('resource_ref')) <= 0:
                res_set.parentNode.removeChild(res_set)
                if len(res_order.getElementsByTagName('resource_set')) <= 0:
                    res_order.parentNode.removeChild(res_order)

    if elementFound == True:
        utils.replace_cib_configuration(dom)
    else:
        utils.err("No matching resources found in ordering list")

def order_start(argv):
    if len(argv) < 3:
        usage.constraint()
        sys.exit(1)

    first_action = DEFAULT_ACTION
    then_action = DEFAULT_ACTION
    action = argv[0]
    if action in OPTIONS_ACTION:
            first_action = action
            argv.pop(0)

    resource1 = argv.pop(0)
    if argv.pop(0) != "then":
        usage.constraint()
        sys.exit(1)
    
    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)

    action = argv[0]
    if action in OPTIONS_ACTION:
            then_action = action
            argv.pop(0)

    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)
    resource2 = argv.pop(0)

    order_options = []
    if len(argv) != 0:
        order_options = order_options + argv[:]

    order_options.append("first-action="+first_action)
    order_options.append("then-action="+then_action)
    order_add([resource1, resource2] + order_options)

def order_add(argv,returnElementOnly=False):
    if len(argv) < 2:
        usage.constraint()
        sys.exit(1)

    resource1 = argv.pop(0)
    resource2 = argv.pop(0)

    cib_dom = utils.get_cib_dom()
    resource_valid, resource_error, correct_id \
        = utils.validate_constraint_resource(cib_dom, resource1)
    if "--autocorrect" in utils.pcs_options and correct_id:
        resource1 = correct_id
    elif not resource_valid:
        utils.err(resource_error)
    resource_valid, resource_error, correct_id \
        = utils.validate_constraint_resource(cib_dom, resource2)
    if "--autocorrect" in utils.pcs_options and correct_id:
        resource2 = correct_id
    elif not resource_valid:
        utils.err(resource_error)

    order_options = []
    id_specified = False
    sym = None
    for arg in argv:
        if arg == "symmetrical":
            sym = "true"
        elif arg == "nonsymmetrical":
            sym = "false"
        elif "=" in arg:
            name, value = arg.split("=", 1)
            if name == "id":
                id_valid, id_error = utils.validate_xml_id(value, 'constraint id')
                if not id_valid:
                    utils.err(id_error)
                if utils.does_id_exist(cib_dom, value):
                    utils.err(
                        "id '%s' is already in use, please specify another one"
                        % value
                    )
                id_specified = True
                order_options.append((name, value))
            elif name == "symmetrical":
                if value.lower() in OPTIONS_SYMMETRICAL:
                    sym = value.lower()
                else:
                    utils.err(
                        "invalid symmetrical value '%s', allowed values are: %s"
                        % (value, ", ".join(OPTIONS_SYMMETRICAL))
                    )
            else:
                order_options.append((name, value))
    if sym:
        order_options.append(("symmetrical", sym))

    options = ""
    if order_options:
        options = " (Options: %s)" % " ".join([
            "%s=%s" % (name, value)
                for name, value in order_options
                    if name not in ("kind", "score")
        ])

    scorekind = "kind: Mandatory"
    id_suffix = "mandatory"
    for opt in order_options:
        if opt[0] == "score":
            scorekind = "score: " + opt[1]
            id_suffix = opt[1]
            break
        if opt[0] == "kind":
            scorekind = "kind: " + opt[1]
            id_suffix = opt[1]
            break

    if not id_specified:
        order_id = "order-" + resource1 + "-" + resource2 + "-" + id_suffix
        order_id = utils.find_unique_id(cib_dom, order_id)
        order_options.append(("id", order_id))

    (dom,constraintsElement) = getCurrentConstraints()
    element = dom.createElement("rsc_order")
    element.setAttribute("first",resource1)
    element.setAttribute("then",resource2)
    for order_opt in order_options:
        element.setAttribute(order_opt[0], order_opt[1])
    constraintsElement.appendChild(element)
    if "--force" not in utils.pcs_options:
        duplicates = order_find_duplicates(constraintsElement, element)
        if duplicates:
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join([
                    "  " + order_el_to_string(dup, True) for dup in duplicates
                ])
            )
    print(
        "Adding " + resource1 + " " + resource2 + " ("+scorekind+")" + options
    )

    if returnElementOnly == False:
        utils.replace_cib_configuration(dom)
    else:
        return element.toxml()

def order_find_duplicates(dom, constraint_el):
    def normalize(constraint_el):
        return (
            constraint_el.getAttribute("first"),
            constraint_el.getAttribute("then"),
            constraint_el.getAttribute("first-action").lower() or DEFAULT_ACTION,
            constraint_el.getAttribute("then-action").lower() or DEFAULT_ACTION,
        )

    normalized_el = normalize(constraint_el)
    return [
        other_el
        for other_el in dom.getElementsByTagName("rsc_order")
        if not other_el.getElementsByTagName("resource_set")
            and constraint_el is not other_el
            and normalized_el == normalize(other_el)
    ]

# Show the currently configured location constraints by node or resource
def location_show(argv):
    if (len(argv) != 0 and argv[0] == "nodes"):
        byNode = True
        showDetail = False
    elif "--full" in utils.pcs_options:
        byNode = False
        showDetail = True
    else:
        byNode = False
        showDetail = False

    if len(argv) > 1:
        valid_noderes = argv[1:]
    else:
        valid_noderes = []

    (dom,constraintsElement) = getCurrentConstraints()
    nodehashon = {}
    nodehashoff = {}
    rschashon = {}
    rschashoff = {}
    ruleshash = defaultdict(list)
    all_loc_constraints = constraintsElement.getElementsByTagName('rsc_location')

    print("Location Constraints:")
    for rsc_loc in all_loc_constraints:
        lc_node = rsc_loc.getAttribute("node")
        lc_rsc = rsc_loc.getAttribute("rsc")
        lc_id = rsc_loc.getAttribute("id")
        lc_score = rsc_loc.getAttribute("score")
        lc_role = rsc_loc.getAttribute("role")
        lc_name = "Resource: " + lc_rsc
        lc_resource_discovery = rsc_loc.getAttribute("resource-discovery")

        for child in rsc_loc.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "rule":
                ruleshash[lc_name].append(child)

# NEED TO FIX FOR GROUP LOCATION CONSTRAINTS (where there are children of
# rsc_location)
        if lc_score == "":
            lc_score = "0";

        if lc_score == "INFINITY":
            positive = True
        elif lc_score == "-INFINITY":
            positive = False
        elif int(lc_score) >= 0:
            positive = True
        else:
            positive = False

        if positive == True:
            nodeshash = nodehashon
            rschash = rschashon
        else:
            nodeshash = nodehashoff
            rschash = rschashoff

        if lc_node in nodeshash:
            nodeshash[lc_node].append((lc_id,lc_rsc,lc_score, lc_role, lc_resource_discovery))
        else:
            nodeshash[lc_node] = [(lc_id, lc_rsc,lc_score, lc_role, lc_resource_discovery)]

        if lc_rsc in rschash:
            rschash[lc_rsc].append((lc_id,lc_node,lc_score, lc_role, lc_resource_discovery))
        else:
            rschash[lc_rsc] = [(lc_id,lc_node,lc_score, lc_role, lc_resource_discovery)]

    nodelist = list(set(list(nodehashon.keys()) + list(nodehashoff.keys())))
    rsclist = list(set(list(rschashon.keys()) + list(rschashoff.keys())))

    if byNode == True:
        for node in nodelist:
            if len(valid_noderes) != 0:
                if node not in valid_noderes:
                    continue
            print("  Node: " + node)

            nodehash_label = (
                (nodehashon, "    Allowed to run:")
                (nodehashoff, "    Not allowed to run:")
            )
            for nodehash, label in nodehash_label:
                if node in nodehash:
                    print(label)
                    for options in nodehash[node]:
                        line_parts = [
                            "      " + options[1] + " (" + options[0] + ")",
                        ]
                        if options[3]:
                            line_parts.append("(role: {0})".format(options[3]))
                        if options[4]:
                            line_parts.append(
                                "(resource-discovery={0})".format(options[4])
                            )
                        line_parts.append("Score: " + options[2])
                        print(" ".join(line_parts))
        show_location_rules(ruleshash,showDetail)
    else:
        rsclist.sort()
        for rsc in rsclist:
            if len(valid_noderes) != 0:
                if rsc not in valid_noderes:
                    continue
            print("  Resource: " + rsc)
            rschash_label = (
                (rschashon, "    Enabled on:"),
                (rschashoff, "    Disabled on:"),
            )
            for rschash, label in rschash_label:
                if rsc in rschash:
                    for options in rschash[rsc]:
                        if not options[1]:
                            continue
                        line_parts = [
                            label,
                            options[1],
                            "(score:{0})".format(options[2]),
                        ]
                        if options[3]:
                            line_parts.append("(role: {0})".format(options[3]))
                        if options[4]:
                            line_parts.append(
                                "(resource-discovery={0})".format(options[4])
                            )
                        if showDetail:
                            line_parts.append("(id:{0})".format(options[0]))
                        print(" ".join(line_parts))
            miniruleshash={}
            miniruleshash["Resource: " + rsc] = ruleshash["Resource: " + rsc]
            show_location_rules(miniruleshash,showDetail, True)

def show_location_rules(ruleshash,showDetail,noheader=False):
    constraint_options = {}
    for rsc in ruleshash:
        constrainthash= defaultdict(list)
        if not noheader:
            print("  " + rsc)
        for rule in ruleshash[rsc]:
            constraint_id = rule.parentNode.getAttribute("id")
            constrainthash[constraint_id].append(rule)
            constraint_options[constraint_id] = []
            if rule.parentNode.getAttribute("resource-discovery"):
                constraint_options[constraint_id].append("resource-discovery=%s" % rule.parentNode.getAttribute("resource-discovery"))

        for constraint_id in constrainthash.keys():
            if constraint_id in constraint_options and len(constraint_options[constraint_id]) > 0:
                constraint_option_info = " (" + " ".join(constraint_options[constraint_id]) + ")"
            else:
                constraint_option_info = ""

            print("    Constraint: " + constraint_id + constraint_option_info)
            for rule in constrainthash[constraint_id]:
                print(rule_utils.ExportDetailed().get_string(
                    rule, showDetail, "      "
                ))

def location_prefer(argv):
    rsc = argv.pop(0)
    prefer_option = argv.pop(0)

    if prefer_option == "prefers":
        prefer = True
    elif prefer_option == "avoids":
        prefer = False
    else:
        usage.constraint()
        sys.exit(1)


    for nodeconf in argv:
        nodeconf_a = nodeconf.split("=",1)
        if len(nodeconf_a) == 1:
            node = nodeconf_a[0]
            if prefer:
                score = "INFINITY"
            else:
                score = "-INFINITY"
        else:
            score = nodeconf_a[1]
            if not utils.is_score(score):
                utils.err("invalid score '%s', use integer or INFINITY or -INFINITY" % score)
            if not prefer:
                if score[0] == "-":
                    score = score[1:]
                else:
                    score = "-" + score
            node = nodeconf_a[0]
        location_add(["location-" +rsc+"-"+node+"-"+score,rsc,node,score])
        

def location_add(argv,rm=False):
    if len(argv) < 4 and (rm == False or len(argv) < 1): 
        usage.constraint()
        sys.exit(1)

    constraint_id = argv.pop(0)

    # If we're removing, we only care about the id
    if (rm == True):
        resource_name = ""
        node = ""
        score = ""
    else:
        id_valid, id_error = utils.validate_xml_id(constraint_id, 'constraint id')
        if not id_valid:
            utils.err(id_error)
        resource_name = argv.pop(0)
        node = argv.pop(0)
        score = argv.pop(0)
        options = []
        # For now we only allow setting resource-discovery
        if len(argv) > 0:
            for arg in argv:
                if '=' in arg:
                    options.append(arg.split('=',1))
                else:
                    print("Error: bad option '%s'" % arg)
                    usage.constraint(["location add"])
                    sys.exit(1)
                if options[-1][0] != "resource-discovery" and "--force" not in utils.pcs_options:
                    utils.err("bad option '%s', use --force to override" % options[-1][0])


        resource_valid, resource_error, correct_id \
            = utils.validate_constraint_resource(
                utils.get_cib_dom(), resource_name
            )
        if "--autocorrect" in utils.pcs_options and correct_id:
            resource_name = correct_id
        elif not resource_valid:
            utils.err(resource_error)
        if not utils.is_score(score):
            utils.err("invalid score '%s', use integer or INFINITY or -INFINITY" % score)

    # Verify current constraint doesn't already exist
    # If it does we replace it with the new constraint
    (dom,constraintsElement) = getCurrentConstraints()
    elementsToRemove = []

    # If the id matches, or the rsc & node match, then we replace/remove
    for rsc_loc in constraintsElement.getElementsByTagName('rsc_location'):
        if (constraint_id == rsc_loc.getAttribute("id")) or \
                (rsc_loc.getAttribute("rsc") == resource_name and \
                rsc_loc.getAttribute("node") == node and not rm):
            elementsToRemove.append(rsc_loc)

    for etr in elementsToRemove:
        constraintsElement.removeChild(etr)

    if (rm == True and len(elementsToRemove) == 0):
        utils.err("resource location id: " + constraint_id + " not found.")

    if (not rm):
        element = dom.createElement("rsc_location")
        element.setAttribute("id",constraint_id)
        element.setAttribute("rsc",resource_name)
        element.setAttribute("node",node)
        element.setAttribute("score",score)
        for option in options:
            element.setAttribute(option[0], option[1])
        constraintsElement.appendChild(element)

    utils.replace_cib_configuration(dom)

def location_rule(argv):
    if len(argv) < 3:
        usage.constraint(["location", "rule"])
        sys.exit(1)
    
    res_name = argv.pop(0)
    resource_valid, resource_error, correct_id \
        = utils.validate_constraint_resource(utils.get_cib_dom(), res_name)
    if "--autocorrect" in utils.pcs_options and correct_id:
        res_name = correct_id
    elif not resource_valid:
        utils.err(resource_error)

    argv.pop(0) # pop "rule"

    options, rule_argv = rule_utils.parse_argv(argv, {"constraint-id": None, "resource-discovery": None,})

    # If resource-discovery is specified, we use it with the rsc_location
    # element not the rule
    if "resource-discovery" in options and options["resource-discovery"]:
        utils.checkAndUpgradeCIB(2,2,0)
        cib, constraints = getCurrentConstraints(utils.get_cib_dom())
        lc = cib.createElement("rsc_location")
        lc.setAttribute("resource-discovery", options.pop("resource-discovery"))
    else:
        cib, constraints = getCurrentConstraints(utils.get_cib_dom())
        lc = cib.createElement("rsc_location")


    constraints.appendChild(lc)
    if options.get("constraint-id"):
        id_valid, id_error = utils.validate_xml_id(
            options["constraint-id"], 'constraint id'
        )
        if not id_valid:
            utils.err(id_error)
        if utils.does_id_exist(cib, options["constraint-id"]):
            utils.err(
                "id '%s' is already in use, please specify another one"
                % options["constraint-id"]
            )
        lc.setAttribute("id", options["constraint-id"])
        del options["constraint-id"]
    else:
        lc.setAttribute("id", utils.find_unique_id(cib, "location-" + res_name))
    lc.setAttribute("rsc", res_name)

    rule_utils.dom_rule_add(lc, options, rule_argv)
    location_rule_check_duplicates(constraints, lc)
    utils.replace_cib_configuration(cib)

def location_rule_check_duplicates(dom, constraint_el):
    if "--force" not in utils.pcs_options:
        duplicates = location_rule_find_duplicates(dom, constraint_el)
        if duplicates:
            lines = []
            for dup in duplicates:
                lines.append("  Constraint: %s" % dup.getAttribute("id"))
                for dup_rule in utils.dom_get_children_by_tag_name(dup, "rule"):
                    lines.append(rule_utils.ExportDetailed().get_string(
                        dup_rule, True, "    "
                    ))
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join(lines)
            )

def location_rule_find_duplicates(dom, constraint_el):
    def normalize(constraint_el):
        return (
            constraint_el.getAttribute("rsc"),
            [
                rule_utils.ExportAsExpression().get_string(rule_el, True)
                for rule_el in constraint_el.getElementsByTagName("rule")
            ]
        )

    normalized_el = normalize(constraint_el)
    return [
        other_el
        for other_el in dom.getElementsByTagName("rsc_location")
        if other_el.getElementsByTagName("rule")
            and constraint_el is not other_el
            and normalized_el == normalize(other_el)
    ]

# Grabs the current constraints and returns the dom and constraint element
def getCurrentConstraints(passed_dom=None):
    if passed_dom:
        dom = passed_dom
    else:
        current_constraints_xml = utils.get_cib_xpath('//constraints')
        if current_constraints_xml == "":
            utils.err("unable to process cib")
        # Verify current constraint doesn't already exist
        # If it does we replace it with the new constraint
        dom = parseString(current_constraints_xml)

    constraintsElement = dom.getElementsByTagName('constraints')[0]
    return (dom, constraintsElement)

# If returnStatus is set, then we don't error out, we just print the error
# and return false
def constraint_rm(argv,returnStatus=False, constraintsElement=None, passed_dom=None):
    if len(argv) < 1:
        usage.constraint()
        sys.exit(1)

    bad_constraint = False
    if len(argv) != 1:
        for arg in argv:
            if not constraint_rm([arg],True, passed_dom=passed_dom):
                bad_constraint = True
        if bad_constraint:
            sys.exit(1)
        return
    else:
        c_id = argv.pop(0)

    elementFound = False

    if not constraintsElement:
        (dom, constraintsElement) = getCurrentConstraints(passed_dom)
        use_cibadmin = True
    else:
        use_cibadmin = False
        
    for co in constraintsElement.childNodes[:]:
        if co.nodeType != xml.dom.Node.ELEMENT_NODE:
            continue
        if co.getAttribute("id") == c_id:
            constraintsElement.removeChild(co)
            elementFound = True

    if not elementFound:
        for rule in constraintsElement.getElementsByTagName("rule")[:]:
            if rule.getAttribute("id") == c_id:
                elementFound = True
                parent = rule.parentNode
                parent.removeChild(rule)
                if len(parent.getElementsByTagName("rule")) == 0:
                    parent.parentNode.removeChild(parent)

    if elementFound == True:
        if passed_dom:
            return dom
        if use_cibadmin:
            utils.replace_cib_configuration(dom)
        if returnStatus:
            return True
    else:
        utils.err("Unable to find constraint - '%s'" % c_id, False)
        if returnStatus:
            return False
        sys.exit(1)


def constraint_ref(argv):
    if len(argv) == 0:
        usage.constraint()
        sys.exit(1)

    for arg in argv:
        print("Resource: %s" % arg)
        constraints,set_constraints = find_constraints_containing(arg)
        if len(constraints) == 0 and len(set_constraints) == 0:
            print("  No Matches.")
        else:
            for constraint in constraints:
                print("  " + constraint)
            for constraint in set_constraints:
                print("  " + constraint)

def remove_constraints_containing(resource_id,output=False,constraints_element = None, passed_dom=None):
    constraints,set_constraints = find_constraints_containing(resource_id, passed_dom)
    for c in constraints:
        if output == True:
            print("Removing Constraint - " + c)
        if constraints_element != None:
            constraint_rm([c], True, constraints_element, passed_dom=passed_dom)
        else:
            constraint_rm([c], passed_dom=passed_dom)

    if len(set_constraints) != 0:
        (dom, constraintsElement) = getCurrentConstraints(passed_dom)
        for c in constraintsElement.getElementsByTagName("resource_ref")[:]:
            # If resource id is in a set, remove it from the set, if the set
            # is empty, then we remove the set, if the parent of the set
            # is empty then we remove it
            if c.getAttribute("id") == resource_id:
                pn = c.parentNode
                pn.removeChild(c)
                if output == True:
                    print("Removing %s from set %s" % (resource_id,pn.getAttribute("id")))
                if pn.getElementsByTagName("resource_ref").length == 0:
                    print("Removing set %s" % pn.getAttribute("id"))
                    pn2 = pn.parentNode
                    pn2.removeChild(pn)
                    if pn2.getElementsByTagName("resource_set").length == 0:
                        pn2.parentNode.removeChild(pn2)
                        print("Removing constraint %s" % pn2.getAttribute("id"))
        if passed_dom:
            return dom
        utils.replace_cib_configuration(dom)

def find_constraints_containing(resource_id, passed_dom=None):
    if passed_dom:
        dom = passed_dom
    else:
        dom = utils.get_cib_dom()
    constraints_found = []
    set_constraints = []

    resources = dom.getElementsByTagName("primitive")
    resource_match = None
    for res in resources:
        if res.getAttribute("id") == resource_id:
            resource_match = res
            break

    if resource_match:
        if resource_match.parentNode.tagName == "master" or resource_match.parentNode.tagName == "clone":
            constraints_found,set_constraints = find_constraints_containing(resource_match.parentNode.getAttribute("id"), dom)

    constraints = dom.getElementsByTagName("constraints")
    if len(constraints) == 0:
        return [],[]
    else:
        constraints = constraints[0]

    myConstraints = constraints.getElementsByTagName("rsc_colocation")
    myConstraints += constraints.getElementsByTagName("rsc_location")
    myConstraints += constraints.getElementsByTagName("rsc_order")
    attr_to_match = ["rsc", "first", "then", "with-rsc", "first", "then"]
    for c in myConstraints:
        for attr in attr_to_match:
            if c.getAttribute(attr) == resource_id:
                constraints_found.append(c.getAttribute("id"))
                break

    setConstraints = constraints.getElementsByTagName("resource_ref")
    for c in setConstraints:
        if c.getAttribute("id") == resource_id:
            set_constraints.append(c.parentNode.parentNode.getAttribute("id"))

    # Remove duplicates
    set_constraints = list(set(set_constraints))
    return constraints_found,set_constraints

def remove_constraints_containing_node(dom, node, output=False):
    for constraint in find_constraints_containing_node(dom, node):
        if output:
            print("Removing Constraint - %s" % constraint.getAttribute("id"))
        constraint.parentNode.removeChild(constraint)
    return dom

def find_constraints_containing_node(dom, node):
    return [
        constraint
        for constraint in dom.getElementsByTagName("rsc_location")
            if constraint.getAttribute("node") == node
    ]

# Re-assign any constraints referencing a resource to its parent (a clone
# or master)
def constraint_resource_update(old_id, passed_dom=None):
    dom = utils.get_cib_dom() if passed_dom is None else passed_dom

    new_id = None
    clone_ms_parent = utils.dom_get_resource_clone_ms_parent(dom, old_id)
    if clone_ms_parent:
        new_id = clone_ms_parent.getAttribute("id")

    if new_id:
        constraints = dom.getElementsByTagName("rsc_location")
        constraints += dom.getElementsByTagName("rsc_order")
        constraints += dom.getElementsByTagName("rsc_colocation")
        attrs_to_update=["rsc","first","then", "with-rsc"]
        for constraint in constraints:
            for attr in attrs_to_update:
                if constraint.getAttribute(attr) == old_id:
                    constraint.setAttribute(attr, new_id)

        if passed_dom is None:
            utils.replace_cib_configuration(dom)

    if passed_dom:
        return dom

def constraint_rule(argv):
    if len(argv) < 2:
        usage.constraint("rule")
        sys.exit(1)

    found = False
    command = argv.pop(0)


    constraint_id = None
    rule_id = None

    if command == "add":
        constraint_id = argv.pop(0)
        cib = utils.get_cib_dom()
        constraint = utils.dom_get_element_with_id(
            cib.getElementsByTagName("constraints")[0],
            "rsc_location",
            constraint_id
        )
        if not constraint:
            utils.err("Unable to find constraint: " + constraint_id)
        options, rule_argv = rule_utils.parse_argv(argv)
        rule_utils.dom_rule_add(constraint, options, rule_argv)
        location_rule_check_duplicates(cib, constraint)
        utils.replace_cib_configuration(cib)

    elif command in ["remove","delete"]:
        cib = utils.get_cib_etree()
        temp_id = argv.pop(0)
        constraints = cib.find('.//constraints')
        loc_cons = cib.findall(str('.//rsc_location'))

        rules = cib.findall(str('.//rule'))
        for loc_con in loc_cons:
            for rule in loc_con:
                if rule.get("id") == temp_id:
                    if len(loc_con) > 1:
                        print("Removing Rule: {0}".format(rule.get("id")))
                        loc_con.remove(rule)
                        found = True
                        break
                    else:
                        print(
                            "Removing Constraint: {0}".format(loc_con.get("id"))
                        )
                        constraints.remove(loc_con)
                        found = True
                        break

            if found == True:
                break

        if found:
            utils.replace_cib_configuration(cib)
        else:
            utils.err("unable to find rule with id: %s" % temp_id)
    else:
        usage.constraint("rule")
        sys.exit(1)
