import sys
import xml.dom.minidom
from enum import Enum
from typing import (
    Any,
    Iterable,
    Optional,
    Set,
    TypeVar,
    cast,
)
from xml.dom.minidom import parseString

import pcs.cli.constraint_order.command as order_command
from pcs import utils
from pcs.cli.common import parse_args
from pcs.cli.common.errors import (
    CmdLineInputError,
    raise_command_replaced,
)
from pcs.cli.common.output import (
    INDENT_STEP,
    lines_to_str,
)
from pcs.cli.constraint.location.command import (
    RESOURCE_TYPE_REGEXP,
    RESOURCE_TYPE_RESOURCE,
)
from pcs.cli.constraint.output import (
    CibConstraintLocationAnyDto,
    filter_constraints_by_rule_expired_status,
    location,
    print_config,
)
from pcs.cli.reports import process_library_reports
from pcs.cli.reports.output import (
    deprecation_warning,
    print_to_stderr,
    warn,
)
from pcs.common import (
    const,
    pacemaker,
    reports,
)
from pcs.common.pacemaker.constraint import (
    CibConstraintColocationSetDto,
    CibConstraintLocationSetDto,
    CibConstraintOrderSetDto,
    CibConstraintsDto,
    CibConstraintTicketSetDto,
    get_all_constraints_ids,
)
from pcs.common.pacemaker.resource.list import CibResourcesDto
from pcs.common.pacemaker.types import CibResourceDiscovery
from pcs.common.reports import ReportItem
from pcs.common.str_tools import (
    format_list,
    indent,
)
from pcs.common.types import (
    StringCollection,
    StringIterable,
    StringSequence,
)
from pcs.lib.cib.constraint.order import ATTRIB as order_attrib
from pcs.lib.node import get_existing_nodes_names
from pcs.lib.pacemaker.values import (
    SCORE_INFINITY,
    is_true,
    sanitize_id,
)

# pylint: disable=invalid-name
# pylint: disable=too-many-branches
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-statements

DEFAULT_ACTION = const.PCMK_ACTION_START
DEFAULT_ROLE = const.PCMK_ROLE_STARTED

OPTIONS_SYMMETRICAL = order_attrib["symmetrical"]

LOCATION_NODE_VALIDATION_SKIP_MSG = (
    "Validation for node existence in the cluster will be skipped"
)
STANDALONE_SCORE_MSG = (
    "Specifying score as a standalone value is deprecated and "
    "might be removed in a future release, use score=value instead"
)


class CrmRuleReturnCode(Enum):
    IN_EFFECT = 0
    EXPIRED = 110
    TO_BE_IN_EFFECT = 111


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
            raise_command_replaced(
                ["pcs constraint order config"], pcs_version="0.12"
            )
        elif sub_cmd == "config":
            order_command.config_cmd(lib, argv, modifiers)
        else:
            order_start(lib, [sub_cmd] + argv, modifiers)
    except CmdLineInputError as e:
        utils.exit_on_cmdline_input_error(e, "constraint", ["order", sub_cmd])


def config_cmd(
    lib: Any, argv: list[str], modifiers: parse_args.InputModifiers
) -> None:
    modifiers.ensure_only_supported("-f", "--output-format", "--full", "--all")
    if argv:
        raise CmdLineInputError()

    print_config(
        cast(
            CibConstraintsDto,
            lib.constraint.get_config(evaluate_rules=True),
        ),
        modifiers,
    )


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
# Specifying score as a single argument is deprecated, though. The correct way
# is score=value in options.
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
            return None, []
        score = None
        if "=" not in argv[0]:
            score = argv.pop(0)
            # TODO added to pcs in the first 0.12.x version
            deprecation_warning(STANDALONE_SCORE_MSG)

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
        elif name == "score":
            score = value
    if score is None:
        score = SCORE_INFINITY
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

        def _constraint_export(constraint_info):
            options_dict = constraint_info["options"]
            co_resource1 = options_dict.get("rsc", "")
            co_resource2 = options_dict.get("with-rsc", "")
            co_id = options_dict.get("id", "")
            co_score = options_dict.get("score", "")
            score_text = "(score:" + co_score + ")"
            console_option_list = [
                f"({option[0]}:{option[1]})"
                for option in sorted(options_dict.items())
                if option[0] not in ("rsc", "with-rsc", "id", "score")
            ]
            console_option_list.append(f"(id:{co_id})")
            return " ".join(
                [co_resource1, "with", co_resource2, score_text]
                + console_option_list
            )

        duplicates = colocation_find_duplicates(constraintsElement, element)
        if duplicates:
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join(
                    [
                        "  "
                        + _constraint_export(
                            {"options": dict(dup.attributes.items())}
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
            # TODO deprecated in pacemaker 2, to be removed in pacemaker 3
            # added to pcs after 0.11.7
            deprecation_warning(
                reports.messages.DeprecatedOption(opt[0], []).message
            )
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

        def _constraint_export(constraint_info):
            options = constraint_info["options"]
            oc_resource1 = options.get("first", "")
            oc_resource2 = options.get("then", "")
            first_action = options.get("first-action", "")
            then_action = options.get("then-action", "")
            oc_id = options.get("id", "")
            oc_score = options.get("score", "")
            oc_kind = options.get("kind", "")
            oc_sym = ""
            oc_id_out = ""
            oc_options = ""
            if "symmetrical" in options and not is_true(
                options.get("symmetrical", "false")
            ):
                oc_sym = "(non-symmetrical)"
            if oc_kind != "":
                score_text = "(kind:" + oc_kind + ")"
            elif oc_kind == "" and oc_score == "":
                score_text = "(kind:Mandatory)"
            else:
                score_text = "(score:" + oc_score + ")"
            oc_id_out = "(id:" + oc_id + ")"
            already_processed_options = (
                "first",
                "then",
                "first-action",
                "then-action",
                "id",
                "score",
                "kind",
                "symmetrical",
            )
            oc_options = " ".join(
                [
                    f"{name}={value}"
                    for name, value in options.items()
                    if name not in already_processed_options
                ]
            )
            if oc_options:
                oc_options = "(Options: " + oc_options + ")"
            return " ".join(
                [
                    arg
                    for arg in [
                        first_action,
                        oc_resource1,
                        "then",
                        then_action,
                        oc_resource2,
                        score_text,
                        oc_sym,
                        oc_options,
                        oc_id_out,
                    ]
                    if arg
                ]
            )

        duplicates = order_find_duplicates(constraintsElement, element)
        if duplicates:
            utils.err(
                "duplicate constraint already exists, use --force to override\n"
                + "\n".join(
                    [
                        "  "
                        + _constraint_export(
                            {"options": dict(dup.attributes.items())}
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


_SetConstraint = TypeVar(
    "_SetConstraint",
    CibConstraintLocationSetDto,
    CibConstraintColocationSetDto,
    CibConstraintOrderSetDto,
    CibConstraintTicketSetDto,
)


def _filter_set_constraints_by_resources(
    constraints_dto: Iterable[_SetConstraint], resources: Set[str]
) -> list[_SetConstraint]:
    return [
        constraint_set_dto
        for constraint_set_dto in constraints_dto
        if any(
            set(resource_set.resources_ids) & resources
            for resource_set in constraint_set_dto.resource_sets
        )
    ]


def _filter_constraints_by_resources(
    constraints_dto: CibConstraintsDto,
    resources: StringIterable,
    patterns: StringIterable,
) -> CibConstraintsDto:
    required_resources_set = set(resources)
    required_patterns_set = set(patterns)
    return CibConstraintsDto(
        location=[
            constraint_dto
            for constraint_dto in constraints_dto.location
            if (
                constraint_dto.resource_id is not None
                and constraint_dto.resource_id in required_resources_set
            )
            or (
                constraint_dto.resource_pattern is not None
                and constraint_dto.resource_pattern in required_patterns_set
            )
        ],
        location_set=_filter_set_constraints_by_resources(
            constraints_dto.location_set, required_resources_set
        ),
        colocation=[
            constraint_dto
            for constraint_dto in constraints_dto.colocation
            if {constraint_dto.resource_id, constraint_dto.with_resource_id}
            & required_resources_set
        ],
        colocation_set=_filter_set_constraints_by_resources(
            constraints_dto.colocation_set, required_resources_set
        ),
        order=[
            constraint_dto
            for constraint_dto in constraints_dto.order
            if {
                constraint_dto.first_resource_id,
                constraint_dto.then_resource_id,
            }
            & required_resources_set
        ],
        order_set=_filter_set_constraints_by_resources(
            constraints_dto.order_set, required_resources_set
        ),
        ticket=[
            constraint_dto
            for constraint_dto in constraints_dto.ticket
            if constraint_dto.resource_id in required_resources_set
        ],
        ticket_set=_filter_set_constraints_by_resources(
            constraints_dto.ticket_set, required_resources_set
        ),
    )


def _filter_location_by_node_base(
    constraint_dtos: Iterable[CibConstraintLocationAnyDto],
    nodes: StringCollection,
) -> list[CibConstraintLocationAnyDto]:
    return [
        constraint_dto
        for constraint_dto in constraint_dtos
        if constraint_dto.attributes.node is not None
        and constraint_dto.attributes.node in nodes
    ]


def location_config_cmd(
    lib: Any, argv: parse_args.Argv, modifiers: parse_args.InputModifiers
) -> None:
    """
    Options:
      * --all - print expired constraints
      * --full - print all details
      * -f - CIB file
    """
    modifiers.ensure_only_supported("-f", "--output-format", "--full", "--all")
    filter_type: Optional[str] = None
    if argv:
        filter_type, *filter_items = argv
        allowed_types = ("resources", "nodes")
        if filter_type not in allowed_types:
            raise CmdLineInputError(
                f"Unknown keyword '{filter_type}'. Allowed keywords: "
                f"{format_list(allowed_types)}"
            )
        if modifiers.get_output_format() != parse_args.OUTPUT_FORMAT_VALUE_TEXT:
            raise CmdLineInputError(
                "Output formats other than 'text' are not supported together "
                "with grouping and filtering by nodes or resources"
            )

    constraints_dto = filter_constraints_by_rule_expired_status(
        lib.constraint.get_config(evaluate_rules=True),
        modifiers.is_specified("--all"),
    )

    constraints_dto = CibConstraintsDto(
        location=constraints_dto.location,
        location_set=constraints_dto.location_set,
    )

    def _print_lines(lines: StringSequence) -> None:
        if lines:
            print("Location Constraints:")
            print(lines_to_str(indent(lines, indent_step=INDENT_STEP)))

    if filter_type == "resources":
        if filter_items:
            resources = []
            patterns = []
            for item in filter_items:
                item_type, item_value = parse_args.parse_typed_arg(
                    item,
                    [RESOURCE_TYPE_RESOURCE, RESOURCE_TYPE_REGEXP],
                    RESOURCE_TYPE_RESOURCE,
                )
                if item_type == RESOURCE_TYPE_RESOURCE:
                    resources.append(item_value)
                elif item_type == RESOURCE_TYPE_REGEXP:
                    patterns.append(item_value)
            constraints_dto = _filter_constraints_by_resources(
                constraints_dto, resources, patterns
            )
        _print_lines(
            location.constraints_to_grouped_by_resource_text(
                constraints_dto.location,
                modifiers.is_specified("--full"),
            )
        )
        return
    if filter_type == "nodes":
        if filter_items:
            constraints_dto = CibConstraintsDto(
                location=_filter_location_by_node_base(
                    constraints_dto.location, filter_items
                ),
                location_set=_filter_location_by_node_base(
                    constraints_dto.location_set, filter_items
                ),
            )
        _print_lines(
            location.constraints_to_grouped_by_node_text(
                constraints_dto.location,
                modifiers.is_specified("--full"),
            )
        )
        return

    print_config(constraints_dto, modifiers)


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


def location_prefer(
    lib: Any, argv: parse_args.Argv, modifiers: parse_args.InputModifiers
) -> None:
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
                f"score={score}",
            ]
        )

    if report_list:
        process_library_reports(report_list)

    modifiers = modifiers.get_subset("--force", "-f")

    for parameters in parameters_list:
        location_add(lib, parameters, modifiers, skip_score_and_node_check=True)


def location_add(
    lib: Any,
    argv: parse_args.Argv,
    modifiers: parse_args.InputModifiers,
    skip_score_and_node_check: bool = False,
) -> None:
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
    score = None
    if "=" not in argv[0]:
        score = argv.pop(0)
        # TODO added to pcs in the first 0.12.x version
        deprecation_warning(STANDALONE_SCORE_MSG)
    options = []
    # For now we only allow setting resource-discovery and score
    for arg in argv:
        name, value = parse_args.split_option(arg, allow_empty_value=False)
        if name == "score":
            score = value
        elif name == "resource-discovery":
            if not modifiers.get("--force"):
                allowed_discovery = list(
                    map(
                        str,
                        [
                            CibResourceDiscovery.ALWAYS,
                            CibResourceDiscovery.EXCLUSIVE,
                            CibResourceDiscovery.NEVER,
                        ],
                    )
                )
                if value not in allowed_discovery:
                    utils.err(
                        (
                            "invalid {0} value '{1}', allowed values are: {2}"
                            ", use --force to override"
                        ).format(name, value, format_list(allowed_discovery))
                    )
            options.append([name, value])
        elif modifiers.get("--force"):
            options.append([name, value])
        else:
            utils.err("bad option '%s', use --force to override" % name)
    if score is None:
        score = "INFINITY"

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


def _split_set_constraints(
    constraints_dto: CibConstraintsDto,
) -> tuple[CibConstraintsDto, CibConstraintsDto]:
    return (
        CibConstraintsDto(
            location=constraints_dto.location,
            colocation=constraints_dto.colocation,
            order=constraints_dto.order,
            ticket=constraints_dto.ticket,
        ),
        CibConstraintsDto(
            location_set=constraints_dto.location_set,
            colocation_set=constraints_dto.colocation_set,
            order_set=constraints_dto.order_set,
            ticket_set=constraints_dto.ticket_set,
        ),
    )


def _find_constraints_containing_resource(
    resources_dto: CibResourcesDto,
    constraints_dto: CibConstraintsDto,
    resource_id: str,
) -> CibConstraintsDto:
    resources_filter = [resource_id]
    # Original implementation only included parent resource only if resource_id
    # was referring to a primitive resource, ignoring groups. This may change in
    # the future if necessary.
    if any(
        primitive_dto.id == resource_id
        for primitive_dto in resources_dto.primitives
    ):
        for clone_dto in resources_dto.clones:
            if clone_dto.member_id == resource_id:
                resources_filter.append(clone_dto.id)
                break
    return _filter_constraints_by_resources(
        constraints_dto, resources_filter, []
    )


def ref(
    lib: Any, argv: list[str], modifiers: parse_args.InputModifiers
) -> None:
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()

    resources_dto = cast(
        CibResourcesDto, lib.resource.get_configured_resources()
    )

    constraints_dto = cast(
        CibConstraintsDto,
        lib.constraint.get_config(evaluate_rules=False),
    )

    for resource_id in sorted(set(argv)):
        constraint_ids = get_all_constraints_ids(
            _find_constraints_containing_resource(
                resources_dto, constraints_dto, resource_id
            )
        )
        print(f"Resource: {resource_id}")
        if constraint_ids:
            print(
                "\n".join(
                    indent(
                        sorted(constraint_ids),
                        indent_step=INDENT_STEP,
                    )
                )
            )
        else:
            print("  No Matches")


def remove_constraints_containing(
    resource_id: str, output=False, constraints_element=None, passed_dom=None
):
    """
    Commandline options:
      * -f - CIB file, effective only if passed_dom is None
    """
    lib = utils.get_library_wrapper()
    modifiers = utils.get_input_modifiers()
    resources_dto = cast(
        CibResourcesDto, lib.resource.get_configured_resources()
    )

    constraints_dto, set_constraints_dto = _split_set_constraints(
        cast(
            CibConstraintsDto,
            lib.constraint.get_config(evaluate_rules=False),
        )
    )
    constraints = sorted(
        get_all_constraints_ids(
            _find_constraints_containing_resource(
                resources_dto, constraints_dto, resource_id
            )
        )
    )
    set_constraints = sorted(
        get_all_constraints_ids(
            _find_constraints_containing_resource(
                resources_dto, set_constraints_dto, resource_id
            )
        )
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
        for set_c in constraintsElement.getElementsByTagName("resource_ref")[:]:
            # If resource id is in a set, remove it from the set, if the set
            # is empty, then we remove the set, if the parent of the set
            # is empty then we remove it
            if set_c.getAttribute("id") == resource_id:
                pn = set_c.parentNode
                pn.removeChild(set_c)
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
