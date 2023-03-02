import sys
import xml.dom.minidom
from collections import defaultdict
from enum import Enum
from os.path import isfile
from xml.dom.minidom import parseString

import pcs.cli.constraint_colocation.command as colocation_command
import pcs.cli.constraint_order.command as order_command
from pcs import rule as rule_utils
from pcs import (
    settings,
    utils,
)
from pcs.cli.common import parse_args
from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.constraint_ticket import command as ticket_command
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.output import (
    deprecation_warning,
    error,
    print_to_stderr,
    warn,
)
from pcs.common import (
    const,
    pacemaker,
    reports,
)
from pcs.common.reports import ReportItem
from pcs.common.reports.constraints import colocation as colocation_format
from pcs.common.reports.constraints import order as order_format
from pcs.common.str_tools import format_list
from pcs.lib.cib.constraint.order import ATTRIB as order_attrib
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.values import (
    SCORE_INFINITY,
    sanitize_id,
)

# pylint: disable=too-many-branches, too-many-statements
# pylint: disable=invalid-name, too-many-nested-blocks
# pylint: disable=too-many-locals, too-many-lines

DEFAULT_ACTION = const.PCMK_ACTION_START
DEFAULT_ROLE = const.PCMK_ROLE_STARTED

OPTIONS_SYMMETRICAL = order_attrib["symmetrical"]

LOCATION_NODE_VALIDATION_SKIP_MSG = (
    "Validation for node existence in the cluster will be skipped"
)
CRM_RULE_MISSING_MSG = (
    "crm_rule is not available, therefore expired constraints may be "
    "shown. Consider upgrading pacemaker."
)

RESOURCE_TYPE_RESOURCE = "resource"
RESOURCE_TYPE_REGEXP = "regexp"

RULE_IN_EFFECT = "in effect"
RULE_EXPIRED = "expired"
RULE_NOT_IN_EFFECT = "not yet in effect"
RULE_UNKNOWN_STATUS = "unknown status"


class CrmRuleReturnCode(Enum):
    IN_EFFECT = 0
    EXPIRED = 110
    TO_BE_IN_EFFECT = 111


def constraint_location_cmd(lib, argv, modifiers):
    if not argv:
        sub_cmd = "config"
    else:
        sub_cmd = argv.pop(0)

    try:
        if sub_cmd == "add":
            location_add(lib, argv, modifiers)
        elif sub_cmd in ["remove", "delete"]:
            location_remove(lib, argv, modifiers)
        elif sub_cmd == "show":
            location_show(lib, argv, modifiers)
        elif sub_cmd == "config":
            location_config_cmd(lib, argv, modifiers)
        elif len(argv) >= 2:
            if argv[0] == "rule":
                location_rule(lib, [sub_cmd] + argv, modifiers)
            else:
                location_prefer(lib, [sub_cmd] + argv, modifiers)
        else:
            raise CmdLineInputError()
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_error(
            e, "constraint", ["location", sub_cmd]
        )


def constraint_order_cmd(lib, argv, modifiers):
    if not argv:
        sub_cmd = "config"
    else:
        sub_cmd = argv.pop(0)

    try:
        if sub_cmd == "set":
            order_command.create_with_set(lib, argv, modifiers)
        elif sub_cmd in ["remove", "delete"]:
            order_rm(lib, argv, modifiers)
        elif sub_cmd == "show":
            order_command.show(lib, argv, modifiers)
        elif sub_cmd == "config":
            order_command.config_cmd(lib, argv, modifiers)
        else:
            order_start(lib, [sub_cmd] + argv, modifiers)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_error(e, "constraint", ["order", sub_cmd])


def constraint_show(lib, argv, modifiers):
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs constraint config' instead."
    )
    return constraint_config_cmd(lib, argv, modifiers)


def constraint_config_cmd(lib, argv, modifiers):
    """
    Options:
      * --all - print expired constraints
      * -f - CIB file
      * --full
    """
    location_config_cmd(lib, argv, modifiers)
    order_command.config_cmd(lib, argv, modifiers.get_subset("--full", "-f"))
    colocation_command.config_cmd(
        lib, argv, modifiers.get_subset("--full", "-f")
    )
    ticket_command.config_cmd(lib, argv, modifiers.get_subset("--full", "-f"))


def colocation_rm(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    elementFound = False
    if len(argv) < 2:
        raise CmdLineInputError()

    (dom, constraintsElement) = getCurrentConstraints()

    resource1 = argv[0]
    resource2 = argv[1]

    for co_loc in constraintsElement.getElementsByTagName("rsc_colocation")[:]:
        if (
            co_loc.getAttribute("rsc") == resource1
            and co_loc.getAttribute("with-rsc") == resource2
        ):
            constraintsElement.removeChild(co_loc)
            elementFound = True
        if (
            co_loc.getAttribute("rsc") == resource2
            and co_loc.getAttribute("with-rsc") == resource1
        ):
            constraintsElement.removeChild(co_loc)
            elementFound = True

    if elementFound:
        utils.replace_cib_configuration(dom)
    else:
        raise error("No matching resources found in ordering list")


def _validate_constraint_resource(cib_dom, resource_id):
    (
        resource_valid,
        resource_error,
        dummy_correct_id,
    ) = utils.validate_constraint_resource(cib_dom, resource_id)
    if not resource_valid:
        utils.err(resource_error)


def _validate_resources_not_in_same_group(cib_dom, resource1, resource2):
    if not utils.validate_resources_not_in_same_group(
        cib_dom, resource1, resource2
    ):
        utils.err(
            "Cannot create an order constraint for resources in the same group"
        )


# Syntax: colocation add [role] <src> with [role] <tgt> [score] [options]
# possible commands:
#        <src> with        <tgt> [score] [options]
#        <src> with <role> <tgt> [score] [options]
# <role> <src> with        <tgt> [score] [options]
# <role> <src> with <role> <tgt> [score] [options]
def colocation_add(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - allow constraint on any resource, allow duplicate constraints
    """

    def _parse_score_options(argv):
        # When passed an array of arguments if the first argument doesn't have
        # an '=' then it's the score, otherwise they're all arguments. Return a
        # tuple with the score and array of name,value pairs
        """
        Commandline options: no options
        """
        if not argv:
            return SCORE_INFINITY, []
        score = SCORE_INFINITY if "=" in argv[0] else argv.pop(0)
        # create a list of 2-tuples (name, value)
        arg_array = [
            parse_args.split_option(arg, allow_empty_value=False)
            for arg in argv
        ]
        return score, arg_array

    del lib
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) < 3:
        raise CmdLineInputError()

    role1 = ""
    role2 = ""

    cib_dom = utils.get_cib_dom()
    new_roles_supported = utils.isCibVersionSatisfied(
        cib_dom, const.PCMK_NEW_ROLES_CIB_VERSION
    )

    def _validate_and_prepare_role(role):
        role_cleaned = role.lower().capitalize()
        if role_cleaned not in const.PCMK_ROLES:
            utils.err(
                "invalid role value '{0}', allowed values are: {1}".format(
                    role, format_list(const.PCMK_ROLES)
                )
            )
        utils.print_depracation_warning_for_legacy_roles(role)
        return pacemaker.role.get_value_for_cib(
            role_cleaned, new_roles_supported
        )

    if argv[2] == "with":
        role1 = _validate_and_prepare_role(argv.pop(0))
        resource1 = argv.pop(0)
    elif argv[1] == "with":
        resource1 = argv.pop(0)
    else:
        raise CmdLineInputError()

    if argv.pop(0) != "with":
        raise CmdLineInputError()
    if "with" in argv:
        raise CmdLineInputError(
            message="Multiple 'with's cannot be specified.",
            hint=(
                "Use the 'pcs constraint colocation set' command if you want "
                "to create a constraint for more than two resources."
            ),
            show_both_usage_and_message=True,
        )

    if not argv:
        raise CmdLineInputError()
    if len(argv) == 1:
        resource2 = argv.pop(0)
    else:
        if utils.is_score_or_opt(argv[1]):
            resource2 = argv.pop(0)
        else:
            role2 = _validate_and_prepare_role(argv.pop(0))
            resource2 = argv.pop(0)

    score, nv_pairs = _parse_score_options(argv)

    _validate_constraint_resource(cib_dom, resource1)
    _validate_constraint_resource(cib_dom, resource2)

    id_in_nvpairs = None
    for name, value in nv_pairs:
        if name == "id":
            id_valid, id_error = utils.validate_xml_id(value, "constraint id")
            if not id_valid:
                utils.err(id_error)
            if utils.does_id_exist(cib_dom, value):
                utils.err(
                    "id '%s' is already in use, please specify another one"
                    % value
                )
            id_in_nvpairs = True
    if not id_in_nvpairs:
        nv_pairs.append(
            (
                "id",
                utils.find_unique_id(
                    cib_dom,
                    "colocation-%s-%s-%s" % (resource1, resource2, score),
                ),
            )
        )

    (dom, constraintsElement) = getCurrentConstraints(cib_dom)

    # If one role is specified, the other should default to "started"
    if role1 != "" and role2 == "":
        role2 = DEFAULT_ROLE
    if role2 != "" and role1 == "":
        role1 = DEFAULT_ROLE
    element = dom.createElement("rsc_colocation")
    element.setAttribute("rsc", resource1)
    element.setAttribute("with-rsc", resource2)
    element.setAttribute("score", score)
    if role1 != "":
        element.setAttribute("rsc-role", role1)
    if role2 != "":
        element.setAttribute("with-rsc-role", role2)
    for nv_pair in nv_pairs:
        element.setAttribute(nv_pair[0], nv_pair[1])
    if not modifiers.get("--force"):
        duplicates = colocation_find_duplicates(constraintsElement, element)
        if duplicates:
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join(
                    [
                        "  "
                        + colocation_format.constraint_plain(
                            {"options": dict(dup.attributes.items())}, True
                        )
                        for dup in duplicates
                    ]
                )
            )
    constraintsElement.appendChild(element)
    utils.replace_cib_configuration(dom)


def colocation_find_duplicates(dom, constraint_el):
    """
    Commandline options: no options
    """
    new_roles_supported = utils.isCibVersionSatisfied(
        dom, const.PCMK_NEW_ROLES_CIB_VERSION
    )

    def normalize(const_el):
        return (
            const_el.getAttribute("rsc"),
            const_el.getAttribute("with-rsc"),
            pacemaker.role.get_value_for_cib(
                const_el.getAttribute("rsc-role").capitalize() or DEFAULT_ROLE,
                new_roles_supported,
            ),
            pacemaker.role.get_value_for_cib(
                const_el.getAttribute("with-rsc-role").capitalize()
                or DEFAULT_ROLE,
                new_roles_supported,
            ),
        )

    normalized_el = normalize(constraint_el)
    return [
        other_el
        for other_el in dom.getElementsByTagName("rsc_colocation")
        if not other_el.getElementsByTagName("resource_set")
        and constraint_el is not other_el
        and normalized_el == normalize(other_el)
    ]


def order_rm(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    elementFound = False
    (dom, constraintsElement) = getCurrentConstraints()

    for resource in argv:
        for ord_loc in constraintsElement.getElementsByTagName("rsc_order")[:]:
            if (
                ord_loc.getAttribute("first") == resource
                or ord_loc.getAttribute("then") == resource
            ):
                constraintsElement.removeChild(ord_loc)
                elementFound = True

        resource_refs_to_remove = []
        for ord_set in constraintsElement.getElementsByTagName("resource_ref"):
            if ord_set.getAttribute("id") == resource:
                resource_refs_to_remove.append(ord_set)
                elementFound = True

        for res_ref in resource_refs_to_remove:
            res_set = res_ref.parentNode
            res_order = res_set.parentNode

            res_ref.parentNode.removeChild(res_ref)
            if not res_set.getElementsByTagName("resource_ref"):
                res_set.parentNode.removeChild(res_set)
                if not res_order.getElementsByTagName("resource_set"):
                    res_order.parentNode.removeChild(res_order)

    if elementFound:
        utils.replace_cib_configuration(dom)
    else:
        utils.err("No matching resources found in ordering list")


def order_start(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - allow constraint for any resource, allow duplicate constraints
    """
    del lib
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) < 3:
        raise CmdLineInputError()

    first_action = DEFAULT_ACTION
    then_action = DEFAULT_ACTION
    action = argv[0]
    if action in const.PCMK_ACTIONS:
        first_action = action
        argv.pop(0)

    resource1 = argv.pop(0)
    if argv.pop(0) != "then":
        raise CmdLineInputError()

    if not argv:
        raise CmdLineInputError()

    action = argv[0]
    if action in const.PCMK_ACTIONS:
        then_action = action
        argv.pop(0)

    if not argv:
        raise CmdLineInputError()
    resource2 = argv.pop(0)

    order_options = []
    if argv:
        order_options = order_options + argv[:]
    if "then" in order_options:
        raise CmdLineInputError(
            message="Multiple 'then's cannot be specified.",
            hint=(
                "Use the 'pcs constraint order set' command if you want to "
                "create a constraint for more than two resources."
            ),
            show_both_usage_and_message=True,
        )

    order_options.append("first-action=" + first_action)
    order_options.append("then-action=" + then_action)
    _order_add(resource1, resource2, order_options, modifiers)


def _order_add(resource1, resource2, options_list, modifiers):
    """
    Commandline options:
      * -f - CIB file
      * --force - allow constraint for any resource, allow duplicate constraints
    """
    cib_dom = utils.get_cib_dom()
    _validate_constraint_resource(cib_dom, resource1)
    _validate_constraint_resource(cib_dom, resource2)

    _validate_resources_not_in_same_group(cib_dom, resource1, resource2)

    order_options = []
    id_specified = False
    sym = None
    for arg in options_list:
        if arg == "symmetrical":
            sym = "true"
        elif arg == "nonsymmetrical":
            sym = "false"
        else:
            name, value = parse_args.split_option(arg, allow_empty_value=False)
            if name == "id":
                id_valid, id_error = utils.validate_xml_id(
                    value, "constraint id"
                )
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
        options = " (Options: %s)" % " ".join(
            [
                "%s=%s" % (name, value)
                for name, value in order_options
                if name not in ("kind", "score")
            ]
        )

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

    (dom, constraintsElement) = getCurrentConstraints()
    element = dom.createElement("rsc_order")
    element.setAttribute("first", resource1)
    element.setAttribute("then", resource2)
    for order_opt in order_options:
        element.setAttribute(order_opt[0], order_opt[1])
    constraintsElement.appendChild(element)
    if not modifiers.get("--force"):
        duplicates = order_find_duplicates(constraintsElement, element)
        if duplicates:
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join(
                    [
                        "  "
                        + order_format.constraint_plain(
                            {"options": dict(dup.attributes.items())}, True
                        )
                        for dup in duplicates
                    ]
                )
            )
    print_to_stderr(f"Adding {resource1} {resource2} ({scorekind}){options}")
    utils.replace_cib_configuration(dom)


def order_find_duplicates(dom, constraint_el):
    """
    Commandline options: no options
    """

    def normalize(constraint_el):
        return (
            constraint_el.getAttribute("first"),
            constraint_el.getAttribute("then"),
            constraint_el.getAttribute("first-action").lower()
            or DEFAULT_ACTION,
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


def location_show(lib, argv, modifiers):
    deprecation_warning(
        "This command is deprecated and will be removed. "
        "Please use 'pcs constraint location config' instead."
    )
    return location_config_cmd(lib, argv, modifiers)


# Show the currently configured location constraints by node or resource
def location_config_cmd(lib, argv, modifiers):
    """
    Options:
      * --all - print expired constraints
      * --full - print all details
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f", "--full", "--all")
    by_node = False

    if argv and argv[0] == "nodes":
        by_node = True

    if len(argv) > 1:
        if by_node:
            valid_noderes = argv[1:]
        else:
            valid_noderes = [
                parse_args.parse_typed_arg(
                    arg,
                    [RESOURCE_TYPE_RESOURCE, RESOURCE_TYPE_REGEXP],
                    RESOURCE_TYPE_RESOURCE,
                )
                for arg in argv[1:]
            ]
    else:
        valid_noderes = []

    (dummy_dom, constraintsElement) = getCurrentConstraints()
    print(
        "\n".join(
            location_lines(
                constraintsElement,
                showDetail=modifiers.get("--full"),
                byNode=by_node,
                valid_noderes=valid_noderes,
                show_expired=modifiers.get("--all"),
            )
        )
    )


def location_lines(
    constraintsElement,
    showDetail=False,
    byNode=False,
    valid_noderes=None,
    show_expired=False,
    verify_expiration=True,
):
    """
    Commandline options: no options
    """
    all_lines = []
    nodehashon = {}
    nodehashoff = {}
    rschashon = {}
    rschashoff = {}
    ruleshash = defaultdict(list)
    all_loc_constraints = constraintsElement.getElementsByTagName(
        "rsc_location"
    )
    cib = utils.get_cib()

    if not isfile(settings.crm_rule):
        if verify_expiration:
            warn(CRM_RULE_MISSING_MSG)
        verify_expiration = False

    all_lines.append("Location Constraints:")
    for rsc_loc in all_loc_constraints:
        if rsc_loc.hasAttribute("rsc-pattern"):
            lc_rsc_type = RESOURCE_TYPE_REGEXP
            lc_rsc_value = rsc_loc.getAttribute("rsc-pattern")
            lc_name = "Resource pattern: {0}".format(lc_rsc_value)
        else:
            lc_rsc_type = RESOURCE_TYPE_RESOURCE
            lc_rsc_value = rsc_loc.getAttribute("rsc")
            lc_name = "Resource: {0}".format(lc_rsc_value)
        lc_rsc = lc_rsc_type, lc_rsc_value, lc_name
        lc_id = rsc_loc.getAttribute("id")
        lc_node = rsc_loc.getAttribute("node")
        lc_score = rsc_loc.getAttribute("score")
        lc_role = pacemaker.role.get_value_primary(
            rsc_loc.getAttribute("role").capitalize()
        )
        lc_resource_discovery = rsc_loc.getAttribute("resource-discovery")

        for child in rsc_loc.childNodes:
            if child.nodeType == child.ELEMENT_NODE and child.tagName == "rule":
                ruleshash[lc_rsc].append(child)

        # NEED TO FIX FOR GROUP LOCATION CONSTRAINTS (where there are children
        # of # rsc_location)
        if lc_score == "":
            lc_score = "0"

        if lc_score == "INFINITY":
            positive = True
        elif lc_score == "-INFINITY":
            positive = False
        elif int(lc_score) >= 0:
            positive = True
        else:
            positive = False

        if positive:
            nodeshash = nodehashon
            rschash = rschashon
        else:
            nodeshash = nodehashoff
            rschash = rschashoff

        hash_element = {
            "id": lc_id,
            "rsc_type": lc_rsc_type,
            "rsc_value": lc_rsc_value,
            "rsc_label": lc_name,
            "node": lc_node,
            "score": lc_score,
            "role": lc_role,
            "resource-discovery": lc_resource_discovery,
        }
        if lc_node in nodeshash:
            nodeshash[lc_node].append(hash_element)
        else:
            nodeshash[lc_node] = [hash_element]
        if lc_rsc in rschash:
            rschash[lc_rsc].append(hash_element)
        else:
            rschash[lc_rsc] = [hash_element]

    nodelist = sorted(set(list(nodehashon.keys()) + list(nodehashoff.keys())))
    rsclist = sorted(
        set(list(rschashon.keys()) + list(rschashoff.keys())),
        key=lambda item: (
            {
                RESOURCE_TYPE_RESOURCE: 1,
                RESOURCE_TYPE_REGEXP: 0,
            }[item[0]],
            item[1],
        ),
    )

    if byNode:
        for node in nodelist:
            if not node:
                continue

            if valid_noderes:
                if node not in valid_noderes:
                    continue
            all_lines.append("  Node: " + node)

            nodehash_label = (
                (nodehashon, "    Allowed to run:"),
                (nodehashoff, "    Not allowed to run:"),
            )
            all_lines += _hashtable_to_lines(
                nodehash_label, "rsc_label", node, showDetail
            )
        all_lines += _show_location_rules(
            ruleshash,
            cib,
            show_detail=showDetail,
            show_expired=show_expired,
            verify_expiration=verify_expiration,
        )
    else:
        for rsc in rsclist:
            rsc_lines = []
            if valid_noderes:
                if rsc[0:2] not in valid_noderes:
                    continue
            rsc_lines.append("  {0}".format(rsc[2]))
            rschash_label = (
                (rschashon, "    Enabled on:"),
                (rschashoff, "    Disabled on:"),
            )
            rsc_lines += _hashtable_to_lines(
                rschash_label, "node", rsc, showDetail
            )
            miniruleshash = {}
            miniruleshash[rsc] = ruleshash[rsc]
            rsc_lines += _show_location_rules(
                miniruleshash,
                cib,
                show_detail=showDetail,
                show_expired=show_expired,
                verify_expiration=verify_expiration,
                noheader=True,
            )
            # Append to all_lines only if the resource has any constraints
            if len(rsc_lines) > 2:
                all_lines += rsc_lines
    return all_lines


def _hashtable_to_lines(hash_label, hash_type, hash_key, show_detail):
    hash_lines = []
    for hashtable, label in hash_label:
        if hash_key in hashtable:
            labeled_lines = []
            for options in hashtable[hash_key]:
                # Skips nodeless constraints and prints nodes/resources
                if not options[hash_type]:
                    continue
                line_parts = [
                    "      {0}{1}".format(
                        "Node: " if hash_type == "node" else "",
                        options[hash_type],
                    )
                ]
                line_parts.append(f"(score:{options['score']})")
                if options["role"]:
                    line_parts.append(
                        "(role:{})".format(
                            pacemaker.role.get_value_primary(options["role"])
                        )
                    )
                if options["resource-discovery"]:
                    line_parts.append(
                        "(resource-discovery={0})".format(
                            options["resource-discovery"]
                        )
                    )
                if show_detail:
                    line_parts.append(f"(id:{options['id']})")
                labeled_lines.append(" ".join(line_parts))
            if labeled_lines:
                labeled_lines.insert(0, label)
            hash_lines += labeled_lines
    return hash_lines


def _show_location_rules(
    ruleshash,
    cib,
    show_detail,
    show_expired=False,
    verify_expiration=True,
    noheader=False,
):
    """
    Commandline options: no options
    """
    all_lines = []
    constraint_options = {}
    for rsc in sorted(
        ruleshash.keys(),
        key=lambda item: (
            {
                RESOURCE_TYPE_RESOURCE: 1,
                RESOURCE_TYPE_REGEXP: 0,
            }[item[0]],
            item[1],
        ),
    ):
        constrainthash = defaultdict(list)
        if not noheader:
            all_lines.append("  {0}".format(rsc[2]))
        for rule in ruleshash[rsc]:
            constraint_id = rule.parentNode.getAttribute("id")
            constrainthash[constraint_id].append(rule)
            constraint_options[constraint_id] = []
            if rule.parentNode.getAttribute("resource-discovery"):
                constraint_options[constraint_id].append(
                    "resource-discovery=%s"
                    % rule.parentNode.getAttribute("resource-discovery")
                )

        for constraint_id in sorted(constrainthash.keys()):
            if (
                constraint_id in constraint_options
                and constraint_options[constraint_id]
            ):
                constraint_option_info = (
                    " (" + " ".join(constraint_options[constraint_id]) + ")"
                )
            else:
                constraint_option_info = ""

            rule_lines = []
            # When expiration check is needed, starting value should be True and
            # when it's not, check is skipped so the initial value must be False
            # to print the constraint
            is_constraint_expired = verify_expiration
            for rule in constrainthash[constraint_id]:
                rule_status = RULE_UNKNOWN_STATUS
                if verify_expiration:
                    rule_status = _get_rule_status(rule.getAttribute("id"), cib)
                    if rule_status != RULE_EXPIRED:
                        is_constraint_expired = False

                rule_lines.append(
                    rule_utils.ExportDetailed().get_string(
                        rule,
                        rule_status == RULE_EXPIRED and show_expired,
                        show_detail,
                        indent="      ",
                    )
                )

            if not show_expired and is_constraint_expired:
                continue

            all_lines.append(
                "    Constraint{0}: {1}{2}".format(
                    " (expired)" if is_constraint_expired else "",
                    constraint_id,
                    constraint_option_info,
                )
            )
            all_lines += rule_lines
    return all_lines


def _verify_node_name(node, existing_nodes):
    report_list = []
    if node not in existing_nodes:
        report_list.append(
            ReportItem.error(
                reports.messages.NodeNotFound(node),
                force_code=reports.codes.FORCE,
            )
        )
    return report_list


def _verify_score(score):
    if not utils.is_score(score):
        utils.err(
            "invalid score '%s', use integer or INFINITY or -INFINITY" % score
        )


def _get_rule_status(rule_id, cib):
    _, _, retval = utils.cmd_runner().run(
        [settings.crm_rule, "--check", "--rule", rule_id, "--xml-text", "-"],
        cib,
    )
    translation_map = {
        CrmRuleReturnCode.IN_EFFECT.value: RULE_IN_EFFECT,
        CrmRuleReturnCode.EXPIRED.value: RULE_EXPIRED,
        CrmRuleReturnCode.TO_BE_IN_EFFECT.value: RULE_NOT_IN_EFFECT,
    }
    return translation_map.get(retval, RULE_UNKNOWN_STATUS)


def location_prefer(lib, argv, modifiers):
    """
    Options:
      * --force - allow unknown options, allow constraint for any resource type
      * -f - CIB file
    """
    modifiers.ensure_only_supported("--force", "-f")
    rsc = argv.pop(0)
    prefer_option = argv.pop(0)

    dummy_rsc_type, rsc_value = parse_args.parse_typed_arg(
        rsc,
        [RESOURCE_TYPE_RESOURCE, RESOURCE_TYPE_REGEXP],
        RESOURCE_TYPE_RESOURCE,
    )

    if prefer_option == "prefers":
        prefer = True
    elif prefer_option == "avoids":
        prefer = False
    else:
        raise CmdLineInputError()

    skip_node_check = False
    if modifiers.is_specified("-f") or modifiers.get("--force"):
        skip_node_check = True
        warn(LOCATION_NODE_VALIDATION_SKIP_MSG)
    else:
        lib_env = utils.get_lib_env()
        existing_nodes, report_list = get_existing_nodes_names(
            corosync_conf=lib_env.get_corosync_conf(),
            cib=lib_env.get_cib(),
        )
        if report_list:
            process_library_reports(report_list)

    report_list = []
    parameters_list = []
    for nodeconf in argv:
        nodeconf_a = nodeconf.split("=", 1)
        node = nodeconf_a[0]
        if not skip_node_check:
            report_list += _verify_node_name(node, existing_nodes)
        if len(nodeconf_a) == 1:
            if prefer:
                score = "INFINITY"
            else:
                score = "-INFINITY"
        else:
            score = nodeconf_a[1]
            _verify_score(score)
            if not prefer:
                if score[0] == "-":
                    score = score[1:]
                else:
                    score = "-" + score

        parameters_list.append(
            [
                sanitize_id(f"location-{rsc_value}-{node}-{score}"),
                rsc,
                node,
                score,
            ]
        )

    if report_list:
        process_library_reports(report_list)

    modifiers = modifiers.get_subset("--force", "-f")

    for parameters in parameters_list:
        location_add(lib, parameters, modifiers, skip_score_and_node_check=True)


def location_add(lib, argv, modifiers, skip_score_and_node_check=False):
    """
    Options:
      * --force - allow unknown options, allow constraint for any resource type
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("--force", "-f")
    if len(argv) < 4:
        raise CmdLineInputError()

    constraint_id = argv.pop(0)
    rsc_type, rsc_value = parse_args.parse_typed_arg(
        argv.pop(0),
        [RESOURCE_TYPE_RESOURCE, RESOURCE_TYPE_REGEXP],
        RESOURCE_TYPE_RESOURCE,
    )
    node = argv.pop(0)
    score = argv.pop(0)
    options = []
    # For now we only allow setting resource-discovery
    if argv:
        for arg in argv:
            if "=" in arg:
                options.append(arg.split("=", 1))
            else:
                raise CmdLineInputError(f"bad option '{arg}'")
            if options[-1][0] != "resource-discovery" and not modifiers.get(
                "--force"
            ):
                utils.err(
                    "bad option '%s', use --force to override" % options[-1][0]
                )

    # Verify that specified node exists in the cluster and score is valid
    if not skip_score_and_node_check:
        if modifiers.is_specified("-f") or modifiers.get("--force"):
            warn(LOCATION_NODE_VALIDATION_SKIP_MSG)
        else:
            lib_env = utils.get_lib_env()
            existing_nodes, report_list = get_existing_nodes_names(
                corosync_conf=lib_env.get_corosync_conf(),
                cib=lib_env.get_cib(),
            )
            report_list += _verify_node_name(node, existing_nodes)
            if report_list:
                process_library_reports(report_list)
        _verify_score(score)

    id_valid, id_error = utils.validate_xml_id(constraint_id, "constraint id")
    if not id_valid:
        utils.err(id_error)

    dom = utils.get_cib_dom()

    if rsc_type == RESOURCE_TYPE_RESOURCE:
        (
            rsc_valid,
            rsc_error,
            dummy_correct_id,
        ) = utils.validate_constraint_resource(dom, rsc_value)
        if not rsc_valid:
            utils.err(rsc_error)

    # Verify current constraint doesn't already exist
    # If it does we replace it with the new constraint
    dummy_dom, constraintsElement = getCurrentConstraints(dom)
    elementsToRemove = []
    # If the id matches, or the rsc & node match, then we replace/remove
    for rsc_loc in constraintsElement.getElementsByTagName("rsc_location"):
        # pylint: disable=too-many-boolean-expressions
        if rsc_loc.getAttribute("id") == constraint_id or (
            rsc_loc.getAttribute("node") == node
            and (
                (
                    RESOURCE_TYPE_RESOURCE == rsc_type
                    and rsc_loc.getAttribute("rsc") == rsc_value
                )
                or (
                    RESOURCE_TYPE_REGEXP == rsc_type
                    and rsc_loc.getAttribute("rsc-pattern") == rsc_value
                )
            )
        ):
            elementsToRemove.append(rsc_loc)
    for etr in elementsToRemove:
        constraintsElement.removeChild(etr)

    element = dom.createElement("rsc_location")
    element.setAttribute("id", constraint_id)
    if rsc_type == RESOURCE_TYPE_RESOURCE:
        element.setAttribute("rsc", rsc_value)
    elif rsc_type == RESOURCE_TYPE_REGEXP:
        element.setAttribute("rsc-pattern", rsc_value)
    element.setAttribute("node", node)
    element.setAttribute("score", score)
    for option in options:
        element.setAttribute(option[0], option[1])
    constraintsElement.appendChild(element)

    utils.replace_cib_configuration(dom)


def location_remove(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    # This code was originally merged in the location_add function and was
    # documented to take 1 or 4 arguments:
    # location remove <id> [<resource id> <node> <score>]
    # However it has always ignored all arguments but constraint id. Therefore
    # this command / function has no use as it can be fully replaced by "pcs
    # constraint remove" which also removes constraints by id. For now I keep
    # things as they are but we should solve this when moving these functions
    # to pcs.lib.
    del lib
    modifiers.ensure_only_supported("-f")
    if len(argv) != 1:
        raise CmdLineInputError()

    constraint_id = argv.pop(0)
    dom, constraintsElement = getCurrentConstraints()

    elementsToRemove = []
    for rsc_loc in constraintsElement.getElementsByTagName("rsc_location"):
        if constraint_id == rsc_loc.getAttribute("id"):
            elementsToRemove.append(rsc_loc)

    if not elementsToRemove:
        utils.err("resource location id: " + constraint_id + " not found.")
    for etr in elementsToRemove:
        constraintsElement.removeChild(etr)

    utils.replace_cib_configuration(dom)


def location_rule(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - allow constraint on any resource type, allow duplicate
        constraints
    """
    del lib
    modifiers.ensure_only_supported("-f", "--force")
    if len(argv) < 3:
        raise CmdLineInputError()

    rsc_type, rsc_value = parse_args.parse_typed_arg(
        argv.pop(0),
        [RESOURCE_TYPE_RESOURCE, RESOURCE_TYPE_REGEXP],
        RESOURCE_TYPE_RESOURCE,
    )
    argv.pop(0)  # pop "rule"
    options, rule_argv = rule_utils.parse_argv(
        argv,
        {
            "constraint-id": None,
            "resource-discovery": None,
        },
    )
    resource_discovery = (
        "resource-discovery" in options and options["resource-discovery"]
    )

    try:
        # Parse the rule to see if we need to upgrade CIB schema. All errors
        # would be properly reported by a validator called bellow, so we can
        # safely ignore them here.
        parsed_rule = rule_utils.RuleParser().parse(
            rule_utils.TokenPreprocessor().run(rule_argv)
        )
        if rule_utils.has_node_attr_expr_with_type_integer(parsed_rule):
            utils.checkAndUpgradeCIB(
                const.PCMK_RULES_NODE_ATTR_EXPR_WITH_INT_TYPE_CIB_VERSION
            )
    except (rule_utils.ParserException, rule_utils.CibBuilderException):
        pass

    dom = utils.get_cib_dom()

    if rsc_type == RESOURCE_TYPE_RESOURCE:
        (
            rsc_valid,
            rsc_error,
            dummy_correct_id,
        ) = utils.validate_constraint_resource(dom, rsc_value)
        if not rsc_valid:
            utils.err(rsc_error)

    cib, constraints = getCurrentConstraints(dom)
    lc = cib.createElement("rsc_location")

    # If resource-discovery is specified, we use it with the rsc_location
    # element not the rule
    if resource_discovery:
        lc.setAttribute("resource-discovery", options.pop("resource-discovery"))

    constraints.appendChild(lc)
    if options.get("constraint-id"):
        id_valid, id_error = utils.validate_xml_id(
            options["constraint-id"], "constraint id"
        )
        if not id_valid:
            utils.err(id_error)
        if utils.does_id_exist(dom, options["constraint-id"]):
            utils.err(
                "id '%s' is already in use, please specify another one"
                % options["constraint-id"]
            )
        lc.setAttribute("id", options["constraint-id"])
        del options["constraint-id"]
    else:
        lc.setAttribute(
            "id",
            utils.find_unique_id(dom, sanitize_id("location-" + rsc_value)),
        )
    if rsc_type == RESOURCE_TYPE_RESOURCE:
        lc.setAttribute("rsc", rsc_value)
    elif rsc_type == RESOURCE_TYPE_REGEXP:
        lc.setAttribute("rsc-pattern", rsc_value)

    rule_utils.dom_rule_add(
        lc, options, rule_argv, utils.getValidateWithVersion(cib)
    )
    location_rule_check_duplicates(constraints, lc, modifiers.get("--force"))
    utils.replace_cib_configuration(cib)


def location_rule_check_duplicates(dom, constraint_el, force):
    """
    Commandline options: no options
    """
    if not force:
        duplicates = location_rule_find_duplicates(dom, constraint_el)
        if duplicates:
            lines = []
            for dup in duplicates:
                lines.append("  Constraint: %s" % dup.getAttribute("id"))
                for dup_rule in utils.dom_get_children_by_tag_name(dup, "rule"):
                    lines.append(
                        rule_utils.ExportDetailed().get_string(
                            dup_rule, False, True, indent="    "
                        )
                    )
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join(lines)
            )


def location_rule_find_duplicates(dom, constraint_el):
    """
    Commandline options: no options
    """

    def normalize(constraint_el):
        if constraint_el.hasAttribute("rsc-pattern"):
            rsc = (
                RESOURCE_TYPE_REGEXP,
                constraint_el.getAttribute("rsc-pattern"),
            )
        else:
            rsc = (RESOURCE_TYPE_RESOURCE, constraint_el.getAttribute("rsc"))
        return (
            rsc,
            [
                rule_utils.ExportAsExpression().get_string(rule_el, True)
                for rule_el in constraint_el.getElementsByTagName("rule")
            ],
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
    """
    Commandline options:
      * -f - CIB file, only if passed_dom is None
    """
    if passed_dom:
        dom = passed_dom
    else:
        current_constraints_xml = utils.get_cib_xpath("//constraints")
        if current_constraints_xml == "":
            utils.err("unable to process cib")
        # Verify current constraint doesn't already exist
        # If it does we replace it with the new constraint
        dom = parseString(current_constraints_xml)

    constraintsElement = dom.getElementsByTagName("constraints")[0]
    return (dom, constraintsElement)


# If returnStatus is set, then we don't error out, we just print the error
# and return false
def constraint_rm(
    lib,
    argv,
    modifiers,
    returnStatus=False,
    constraintsElement=None,
    passed_dom=None,
):
    """
    Options:
      * -f - CIB file, effective only if passed_dom is None
    """
    if passed_dom is None:
        modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    bad_constraint = False
    if len(argv) != 1:
        for arg in argv:
            if not constraint_rm(
                lib, [arg], modifiers, returnStatus=True, passed_dom=passed_dom
            ):
                bad_constraint = True
        if bad_constraint:
            sys.exit(1)
        return None

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
                if not parent.getElementsByTagName("rule"):
                    parent.parentNode.removeChild(parent)

    if elementFound:
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
    return None


def constraint_ref(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
    """
    del lib
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    for arg in argv:
        print("Resource: %s" % arg)
        constraints, set_constraints = find_constraints_containing(arg)
        if not constraints and not set_constraints:
            print("  No Matches.")
        else:
            for constraint in constraints:
                print("  " + constraint)
            for constraint in sorted(set_constraints):
                print("  " + constraint)


def remove_constraints_containing(
    resource_id, output=False, constraints_element=None, passed_dom=None
):
    """
    Commandline options:
      * -f - CIB file, effective only if passed_dom is None
    """
    lib = utils.get_library_wrapper()
    modifiers = utils.get_input_modifiers()
    constraints, set_constraints = find_constraints_containing(
        resource_id, passed_dom
    )
    for c in constraints:
        if output:
            print_to_stderr(f"Removing Constraint - {c}")
        if constraints_element is not None:
            constraint_rm(
                lib,
                [c],
                modifiers,
                True,
                constraints_element,
                passed_dom=passed_dom,
            )
        else:
            constraint_rm(lib, [c], modifiers, passed_dom=passed_dom)

    if set_constraints:
        (dom, constraintsElement) = getCurrentConstraints(passed_dom)
        for c in constraintsElement.getElementsByTagName("resource_ref")[:]:
            # If resource id is in a set, remove it from the set, if the set
            # is empty, then we remove the set, if the parent of the set
            # is empty then we remove it
            if c.getAttribute("id") == resource_id:
                pn = c.parentNode
                pn.removeChild(c)
                if output:
                    print_to_stderr(
                        "Removing {} from set {}".format(
                            resource_id, pn.getAttribute("id")
                        )
                    )
                if pn.getElementsByTagName("resource_ref").length == 0:
                    print_to_stderr(
                        "Removing set {}".format(pn.getAttribute("id"))
                    )
                    pn2 = pn.parentNode
                    pn2.removeChild(pn)
                    if pn2.getElementsByTagName("resource_set").length == 0:
                        pn2.parentNode.removeChild(pn2)
                        print_to_stderr(
                            "Removing constraint {}".format(
                                pn2.getAttribute("id")
                            )
                        )
        if passed_dom:
            return dom
        utils.replace_cib_configuration(dom)
    return None


def find_constraints_containing(resource_id, passed_dom=None):
    """
    Commandline options:
      * -f - CIB file, effective only if passed_dom is None
    """
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
        if resource_match.parentNode.tagName in ("master", "clone"):
            constraints_found, set_constraints = find_constraints_containing(
                resource_match.parentNode.getAttribute("id"), dom
            )

    constraints = dom.getElementsByTagName("constraints")
    if not constraints:
        return [], []

    constraints = constraints[0]
    myConstraints = constraints.getElementsByTagName("rsc_colocation")
    myConstraints += constraints.getElementsByTagName("rsc_location")
    myConstraints += constraints.getElementsByTagName("rsc_order")
    myConstraints += constraints.getElementsByTagName("rsc_ticket")
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
    return constraints_found, set_constraints


def remove_constraints_containing_node(dom, node, output=False):
    """
    Commandline options: no options
    """
    for constraint in find_constraints_containing_node(dom, node):
        if output:
            print_to_stderr(
                "Removing Constraint - {}".format(constraint.getAttribute("id"))
            )
        constraint.parentNode.removeChild(constraint)
    return dom


def find_constraints_containing_node(dom, node):
    """
    Commandline options: no options
    """
    return [
        constraint
        for constraint in dom.getElementsByTagName("rsc_location")
        if constraint.getAttribute("node") == node
    ]


# Re-assign any constraints referencing a resource to its parent (a clone
# or master)
def constraint_resource_update(old_id, dom):
    """
    Commandline options: no options
    """
    new_id = None
    clone_ms_parent = utils.dom_get_resource_clone_ms_parent(dom, old_id)
    if clone_ms_parent:
        new_id = clone_ms_parent.getAttribute("id")

    if new_id:
        constraints = dom.getElementsByTagName("rsc_location")
        constraints += dom.getElementsByTagName("rsc_order")
        constraints += dom.getElementsByTagName("rsc_colocation")
        attrs_to_update = ["rsc", "first", "then", "with-rsc"]
        for constraint in constraints:
            for attr in attrs_to_update:
                if constraint.getAttribute(attr) == old_id:
                    constraint.setAttribute(attr, new_id)
    return dom


def constraint_rule(lib, argv, modifiers):
    """
    Options:
      * -f - CIB file
      * --force - allow duplicate constraints, only for add command

    NOTE: modifiers check is in subcommand
    """
    del lib
    if len(argv) < 2:
        raise CmdLineInputError()

    found = False
    command = argv.pop(0)

    constraint_id = None

    if command == "add":
        modifiers.ensure_only_supported("-f", "--force")
        constraint_id = argv.pop(0)
        options, rule_argv = rule_utils.parse_argv(argv)
        try:
            # Parse the rule to see if we need to upgrade CIB schema. All errors
            # would be properly reported by a validator called bellow, so we can
            # safely ignore them here.
            parsed_rule = rule_utils.RuleParser().parse(
                rule_utils.TokenPreprocessor().run(rule_argv)
            )
            if rule_utils.has_node_attr_expr_with_type_integer(parsed_rule):
                utils.checkAndUpgradeCIB(
                    const.PCMK_RULES_NODE_ATTR_EXPR_WITH_INT_TYPE_CIB_VERSION
                )
        except (rule_utils.ParserException, rule_utils.CibBuilderException):
            pass
        cib = utils.get_cib_dom()
        constraint = utils.dom_get_element_with_id(
            cib.getElementsByTagName("constraints")[0],
            "rsc_location",
            constraint_id,
        )
        if not constraint:
            utils.err("Unable to find constraint: " + constraint_id)
        rule_utils.dom_rule_add(
            constraint,
            options,
            rule_argv,
            utils.getValidateWithVersion(cib),
        )
        location_rule_check_duplicates(
            cib, constraint, modifiers.get("--force")
        )
        utils.replace_cib_configuration(cib)

    elif command in ["remove", "delete"]:
        modifiers.ensure_only_supported("-f")
        cib = utils.get_cib_etree()
        temp_id = argv.pop(0)
        constraints = cib.find(".//constraints")
        loc_cons = cib.findall(str(".//rsc_location"))

        for loc_con in loc_cons:
            for rule in loc_con:
                if rule.get("id") == temp_id:
                    if len(loc_con) > 1:
                        print_to_stderr(
                            "Removing Rule: {0}".format(rule.get("id"))
                        )
                        loc_con.remove(rule)
                        found = True
                    else:
                        print_to_stderr(
                            "Removing Constraint: {0}".format(loc_con.get("id"))
                        )
                        constraints.remove(loc_con)
                        found = True
                    break

            if found:
                break

        if found:
            utils.replace_cib_configuration(cib)
        else:
            utils.err("unable to find rule with id: %s" % temp_id)
    else:
        raise CmdLineInputError()
