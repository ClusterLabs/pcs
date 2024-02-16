import abc
from typing import (
    Collection,
    Mapping,
    Optional,
)

from lxml import etree
from lxml.etree import _Element

from pcs.common import (
    const,
    reports,
)
from pcs.common.pacemaker.constraint import (
    CibConstraintLocationAttributesDto,
    CibConstraintLocationDto,
    CibConstraintLocationSetDto,
)
from pcs.common.pacemaker.role import (
    get_value_for_cib as get_role_value_for_cib,
)
from pcs.common.pacemaker.types import CibResourceDiscovery
from pcs.lib import validate
from pcs.lib.cib import rule
from pcs.lib.cib.const import TAG_CONSTRAINT_LOCATION as TAG
from pcs.lib.cib.const import TAG_RULE
from pcs.lib.cib.tools import (
    IdProvider,
    Version,
    role_constructor,
)
from pcs.lib.pacemaker.values import sanitize_id
from pcs.lib.tools import get_optional_value

from .common import (
    DuplicatesChecker,
    is_set_constraint,
    validate_constrainable_elements,
)
from .resource_set import constraint_element_to_resource_set_dto_list


def is_location_constraint(element: _Element) -> bool:
    return element.tag == TAG


def is_location_constraint_with_rule(element: _Element) -> bool:
    return (
        is_location_constraint(element)
        and element.find(f"./{TAG_RULE}") is not None
    )


def is_location_rule(element: _Element) -> bool:
    parent = element.getparent()
    return parent is not None and element.tag == TAG_RULE and parent.tag == TAG


def _element_to_attributes_dto(
    element: _Element, rule_in_effect_eval: rule.RuleInEffectEval
) -> CibConstraintLocationAttributesDto:
    return CibConstraintLocationAttributesDto(
        constraint_id=str(element.attrib["id"]),
        score=element.get("score"),
        node=element.get("node"),
        rules=[
            rule.rule_element_to_dto(rule_in_effect_eval, rule_el)
            for rule_el in element.findall(f"./{TAG_RULE}")
        ],
        lifetime=[
            rule.rule_element_to_dto(rule_in_effect_eval, rule_el)
            for rule_el in element.findall("./lifetime/rule")
        ],
        resource_discovery=get_optional_value(
            CibResourceDiscovery, element.get("resource-discovery")
        ),
    )


def _plain_constraint_el_to_dto(
    element: _Element, rule_in_effect_eval: rule.RuleInEffectEval
) -> CibConstraintLocationDto:
    return CibConstraintLocationDto(
        resource_id=element.get("rsc"),
        resource_pattern=element.get("rsc-pattern"),
        role=get_optional_value(role_constructor, element.get("role")),
        attributes=_element_to_attributes_dto(element, rule_in_effect_eval),
    )


def _set_constraint_el_to_dto(
    element: _Element, rule_in_effect_eval: rule.RuleInEffectEval
) -> CibConstraintLocationSetDto:
    return CibConstraintLocationSetDto(
        resource_sets=constraint_element_to_resource_set_dto_list(element),
        attributes=_element_to_attributes_dto(element, rule_in_effect_eval),
    )


def get_all_as_dtos(
    constraints_el: _Element, rule_in_effect_eval: rule.RuleInEffectEval
) -> tuple[list[CibConstraintLocationDto], list[CibConstraintLocationSetDto]]:
    plain_list: list[CibConstraintLocationDto] = []
    set_list: list[CibConstraintLocationSetDto] = []
    for constraint_el in constraints_el.findall(f"./{TAG}"):
        if is_set_constraint(constraint_el):
            set_list.append(
                _set_constraint_el_to_dto(constraint_el, rule_in_effect_eval)
            )
        else:
            plain_list.append(
                _plain_constraint_el_to_dto(constraint_el, rule_in_effect_eval)
            )
    return plain_list, set_list


class DuplicatesCheckerLocationRulePlain(DuplicatesChecker):
    """
    Searcher of duplicate plain location constraints with rules
    """

    def __init__(self) -> None:
        super().__init__()
        self._rule_to_str = rule.RuleToStr(normalize=True)
        self._constraint_to_check_rules: Optional[set[str]] = None

    def check(
        self,
        constraint_section: _Element,
        constraint_to_check: _Element,
        force_flags: Collection[reports.types.ForceCode] = (),
    ) -> reports.ReportItemList:
        self._constraint_to_check_rules = None
        return super().check(
            constraint_section, constraint_to_check, force_flags
        )

    def _are_duplicate(
        self,
        constraint_to_check: _Element,
        constraint_el: _Element,
    ) -> bool:
        # simple node-score constraints are not duplicate to rule constraints
        if not is_location_constraint_with_rule(constraint_el):
            return False

        # get the base constraint's rules as strings
        if self._constraint_to_check_rules is None:
            self._constraint_to_check_rules = {
                self._rule_to_str.get_str(rule_el)
                for rule_el in constraint_to_check.iterfind(TAG_RULE)
            }

        # get the tested constraint's rules as strings
        rules = {
            self._rule_to_str.get_str(rule_el)
            for rule_el in constraint_el.iterfind(TAG_RULE)
        }

        # compare the two constraints
        return (
            constraint_to_check.get("rsc") == constraint_el.get("rsc")
            and constraint_to_check.get("rsc-pattern")
            == constraint_el.get("rsc-pattern")
            # From pacemaker explained:
            # A location constraint may contain one or more top-level rules.
            # The cluster will act as if there is a separate location
            # constraint for each rule that evaluates as true.
            and bool(self._constraint_to_check_rules & rules)
        )


class ValidateWithRuleBase:
    """
    Common tools for validating rule constraints
    """

    def __init__(
        self,
        id_provider: IdProvider,
        rule_str: str,
        rule_options: validate.TypeOptionMap,
    ):
        """
        id_provider -- elements' ids generator
        rule_str -- rule as a string, to be parsed and validated
        rule_options -- additional options for the rule
        """
        self._id_provider = id_provider
        self._rule_str = rule_str
        self._rule_options = rule_options
        self._rule_parsed: Optional[rule.RuleRoot] = None

    @abc.abstractmethod
    def validate(
        self, force_flags: Collection[reports.types.ForceCode] = ()
    ) -> reports.ReportItemList:
        """
        Run validation

        force_flags -- list of flags codes
        """
        raise NotImplementedError()

    def get_parsed_rule(self) -> rule.RuleRoot:
        """
        Return validated and parsed rule for further use
        """
        if not self._rule_parsed:
            raise RuntimeError(
                "There is no valid rule. Were validator results ignored?"
            )
        return self._rule_parsed

    def _validate_rule_options(self) -> reports.ReportItemList:
        validators_rule = [
            validate.NamesIn(
                ("id", "role", "score", "score-attribute"),
                option_type="rule",
            ),
            validate.MutuallyExclusive(
                ("score", "score-attribute"),
                option_type="rule",
            ),
            # with id_provider it validates that the id is available as well
            validate.ValueId(
                "id",
                option_name_for_report="rule id",
                id_provider=self._id_provider,
            ),
            validate.ValueScore("score"),
            validate.ValueIn(
                "role",
                const.PCMK_ROLES_PROMOTED + const.PCMK_ROLES_UNPROMOTED,
            ),
            validate.ValueDeprecated(
                "role",
                {
                    const.PCMK_ROLE_PROMOTED_LEGACY: const.PCMK_ROLE_PROMOTED,
                    const.PCMK_ROLE_UNPROMOTED_LEGACY: const.PCMK_ROLE_UNPROMOTED,
                },
                reports.ReportItemSeverity.deprecation(),
            ),
        ]
        return validate.ValidatorAll(validators_rule).validate(
            self._rule_options
        )

    def _validate_rule(self) -> reports.ReportItemList:
        report_list: reports.ReportItemList = []
        if not self._rule_str.strip():
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.RuleNoExpressionSpecified()
                )
            )
        else:
            try:
                self._rule_parsed = rule.parse_rule(self._rule_str)
                report_list.extend(
                    rule.RuleValidator(
                        self._rule_parsed,
                        allow_node_attr_expr=True,
                    ).get_reports()
                )
            except rule.RuleParseError as e:
                report_list.append(
                    reports.ReportItem.error(
                        reports.messages.RuleExpressionParseError(
                            e.rule_string,
                            e.msg,
                            e.rule_line,
                            e.lineno,
                            e.colno,
                            e.pos,
                        )
                    )
                )
        return report_list


class ValidateCreatePlainWithRule(ValidateWithRuleBase):
    """
    Validator for creating new constraint with a rule and appending it to CIB
    """

    def __init__(
        self,
        id_provider: IdProvider,
        rule_str: str,
        rule_options: validate.TypeOptionMap,
        constraint_options: validate.TypeOptionMap,
        constrained_el: Optional[_Element] = None,
    ):
        """
        constraint_options -- additional options for the constraint
        constrained_el -- an element for which the constraint is being created
        """
        super().__init__(id_provider, rule_str, rule_options)
        self._resource_el = constrained_el
        self._constraint_options = constraint_options

    def validate(
        self, force_flags: Collection[reports.types.ForceCode] = ()
    ) -> reports.ReportItemList:
        force_options = reports.codes.FORCE in force_flags
        allow_in_multiinstance_resources = reports.codes.FORCE in force_flags
        report_list: reports.ReportItemList = []

        # validate resource specification
        if self._resource_el is not None:
            report_list.extend(
                validate_constrainable_elements(
                    [self._resource_el], allow_in_multiinstance_resources
                )
            )

        # validate constraint options
        validators_constraint = [
            validate.NamesIn(
                ("id", "resource-discovery"), option_type="constraint"
            ),
            # with id_provider it validates that the id is available as well
            validate.ValueId(
                "id",
                option_name_for_report="constraint id",
                id_provider=self._id_provider,
            ),
            validate.ValueIn(
                "resource-discovery",
                [
                    CibResourceDiscovery.ALWAYS,
                    CibResourceDiscovery.EXCLUSIVE,
                    CibResourceDiscovery.NEVER,
                ],
                severity=reports.item.get_severity(
                    reports.codes.FORCE, force_options
                ),
            ),
        ]
        report_list.extend(
            validate.ValidatorAll(validators_constraint).validate(
                self._constraint_options
            )
        )

        # validate rule options
        report_list.extend(self._validate_rule_options())
        # parse and validate rule
        report_list.extend(self._validate_rule())

        return report_list


class ValidateAddRuleToConstraint(ValidateWithRuleBase):
    """
    Validator for adding new rule to an existing location constraint
    """

    def __init__(
        self,
        id_provider: IdProvider,
        rule_str: str,
        rule_options: validate.TypeOptionMap,
        constraint_el: _Element,
    ):
        """
        constraint_el -- location constraint to be modified
        """
        super().__init__(id_provider, rule_str, rule_options)
        self._constraint_el = constraint_el

    def validate(
        self, force_flags: Collection[reports.types.ForceCode] = ()
    ) -> reports.ReportItemList:
        del force_flags
        report_list: reports.ReportItemList = []
        # To keep backwards compatibility, adding rules to simple node-score
        # location constraints is allowed. The rule replaces node-score
        # preference.
        if not is_location_constraint(self._constraint_el):
            report_list.append(
                reports.ReportItem.error(
                    reports.messages.CannotAddRuleToConstraintWrongType(
                        self._constraint_el.get("id", ""),
                        self._constraint_el.tag,
                    )
                )
            )
        # validate rule options
        report_list.extend(self._validate_rule_options())
        # parse and validate rule
        report_list.extend(self._validate_rule())
        return report_list


def create_plain_with_rule(
    parent_element: _Element,
    id_provider: IdProvider,
    cib_schema_version: Version,
    resource_id_type: const.ResourceIdType,
    resource_id: str,
    rule_tree: rule.RuleRoot,
    rule_options: Mapping[str, str],
    constraint_options: Mapping[str, str],
) -> _Element:
    """
    Create a location constraint with a rule for a resource

    parent_element -- where to place the constraint
    id_provider -- elements' ids generator
    cib_schema_version -- current CIB schema version
    resource_id_type -- specifies type of resource_id - plain or regexp
    resource_id -- resource ID or resource ID pattern (regexp)
    rule_tree -- parsed rule - specifies when the constraint is active
    rule_options -- additional options for the rule
    constraint_options -- additional options for the constraint
    """
    constraint_options = dict(constraint_options)  # make a modifiable copy

    # create a constraint element
    constraint_el = etree.SubElement(parent_element, TAG)

    # set constraint attributes
    if "id" not in constraint_options or not constraint_options["id"]:
        constraint_options["id"] = id_provider.allocate_id(
            sanitize_id(f"location-{resource_id}")
        )
    constraint_options[
        "rsc-pattern"
        if resource_id_type == const.RESOURCE_ID_TYPE_REGEXP
        else "rsc"
    ] = resource_id
    for name, value in constraint_options.items():
        if value != "":
            constraint_el.attrib[name] = value

    # create a rule element
    add_rule_to_constraint(
        constraint_el, id_provider, cib_schema_version, rule_tree, rule_options
    )

    return constraint_el


def add_rule_to_constraint(
    constraint_el: _Element,
    id_provider: IdProvider,
    cib_schema_version: Version,
    rule_tree: rule.RuleRoot,
    rule_options: Mapping[str, str],
) -> _Element:
    """
    Add a rule to an existing constraint, remove its simple node-score settings

    constraint_el -- location constraint to be modified
    id_provider -- elements' ids generator
    cib_schema_version -- current CIB schema version
    rule_tree -- parsed rule - specifies when the constraint is active
    rule_options -- additional options for the rule
    """
    rule_options = dict(rule_options)  # make a modifiable copy

    # add the rule to CIB
    rule_el = rule.rule_to_cib(
        constraint_el,
        id_provider,
        cib_schema_version,
        rule_tree,
        rule_options.get("id"),
    )

    # set rule attributes
    if not rule_options.get("score") and not rule_options.get(
        "score-attribute"
    ):
        rule_options["score"] = "INFINITY"
    if rule_options.get("role"):
        rule_options["role"] = get_role_value_for_cib(
            const.PcmkRoleType(rule_options["role"]),
            cib_schema_version >= const.PCMK_NEW_ROLES_CIB_VERSION,
        )
    for name, value in rule_options.items():
        if value != "":
            rule_el.attrib[name] = value

    # If the rule is being added to a location constraint which didn't have
    # rules previously, we need to remove the constraint's node and score
    # attributes to keep CIB valid. The rule basically replaces previous
    # node-score preference.
    for name in ("node", "score"):
        if name in constraint_el.attrib:
            del constraint_el.attrib[name]

    return rule_el
