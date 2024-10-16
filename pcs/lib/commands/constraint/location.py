from typing import (
    Collection,
    Mapping,
)

from pcs.common import (
    const,
    reports,
)
from pcs.lib import validate
from pcs.lib.cib.constraint import location
from pcs.lib.cib.rule import (
    RuleParseError,
    has_node_attr_expr_with_type_integer,
    parse_rule,
)
from pcs.lib.cib.tools import (
    ElementNotFound,
    IdProvider,
    get_constraints,
    get_element_by_id,
    get_pacemaker_version_by_which_cib_was_validated,
)
from pcs.lib.env import LibraryEnvironment
from pcs.lib.errors import LibraryError


def create_plain_with_rule(
    env: LibraryEnvironment,
    resource_id_type: const.ResourceIdType,
    resource_id: str,
    rule: str,
    rule_options: Mapping[str, str],
    constraint_options: Mapping[str, str],
    force_flags: Collection[reports.types.ForceCode] = (),
) -> None:
    """
    Create a location constraint with a rule for a resource

    env --
    resource_id_type -- specifies type of resource_id - plain or regexp
    resource_id -- resource or tag ID or resource ID pattern (regexp)
    rule -- constraint's rule - specifies when the constraint is active
    rule_options -- additional options for the rule
    constraint_options -- additional options for the constraint
    force_flags -- list of flags codes
    """
    # pylint: disable=too-many-locals

    # Parse the rule to see if we need to upgrade CIB schema. All errors
    # would be properly reported by a validator called bellow, so we can
    # safely ignore them here.
    nice_to_have_cib_version = None
    try:
        rule_tree = parse_rule(rule)
        if has_node_attr_expr_with_type_integer(rule_tree):
            nice_to_have_cib_version = (
                const.PCMK_RULES_NODE_ATTR_EXPR_WITH_INT_TYPE_CIB_VERSION
            )
    except RuleParseError:
        pass

    cib = env.get_cib(
        nice_to_have_version=nice_to_have_cib_version,
    )
    id_provider = IdProvider(cib)
    constraint_section = get_constraints(cib)

    # validation
    constrained_el = None
    allowed_id_types = [
        const.RESOURCE_ID_TYPE_PLAIN,
        const.RESOURCE_ID_TYPE_REGEXP,
    ]
    if resource_id_type not in allowed_id_types:
        env.report_processor.report(
            reports.ReportItem.error(
                reports.messages.InvalidIdType(
                    resource_id_type, sorted(allowed_id_types)
                )
            )
        )
    elif resource_id_type == const.RESOURCE_ID_TYPE_PLAIN:
        try:
            constrained_el = get_element_by_id(cib, resource_id)
        except ElementNotFound:
            env.report_processor.report(
                reports.ReportItem.error(
                    reports.messages.IdNotFound(resource_id, [])
                )
            )

    rule_options_pairs = validate.values_to_pairs(
        rule_options,
        validate.option_value_normalization(
            {"role": lambda value: value.capitalize()}
        ),
    )
    validator = location.ValidateCreatePlainWithRule(
        id_provider,
        rule,
        rule_options_pairs,
        constraint_options,
        constrained_el,
    )
    env.report_processor.report_list(validator.validate(force_flags))

    if env.report_processor.has_errors:
        raise LibraryError()

    # modify CIB
    new_constraint = location.create_plain_with_rule(
        constraint_section,
        id_provider,
        get_pacemaker_version_by_which_cib_was_validated(cib),
        resource_id_type,
        resource_id,
        validator.get_parsed_rule(),
        validate.pairs_to_values(rule_options_pairs),
        constraint_options,
    )

    # Check whether the created constraint is a duplicate of an existing one
    env.report_processor.report_list(
        location.DuplicatesCheckerLocationRulePlain().check(
            constraint_section, new_constraint, force_flags
        )
    )
    if env.report_processor.has_errors:
        raise LibraryError()

    # push CIB
    env.push_cib()
