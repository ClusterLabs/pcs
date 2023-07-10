import shlex
from collections import defaultdict
from typing import (
    Callable,
    Iterable,
)

from pcs.cli.common.output import (
    INDENT_STEP,
    pairs_to_cmd,
)
from pcs.cli.reports.output import warn
from pcs.cli.rule import rule_expression_dto_to_lines
from pcs.common.pacemaker.constraint import (
    CibConstraintLocationAttributesDto,
    CibConstraintLocationDto,
    CibConstraintLocationSetDto,
)
from pcs.common.pacemaker.rule import CibRuleExpressionDto
from pcs.common.pacemaker.tools import (
    abs_score,
    is_negative_score,
)
from pcs.common.str_tools import (
    format_optional,
    indent,
    pairs_to_text,
)

from . import set as _set


def _attributes_to_pairs(
    attributes_dto: CibConstraintLocationAttributesDto,
) -> list[tuple[str, str]]:
    pairs = []
    if attributes_dto.resource_discovery:
        pairs.append(
            ("resource-discovery", str(attributes_dto.resource_discovery))
        )
    return pairs


def _attributes_to_text(
    attributes_dto: CibConstraintLocationAttributesDto,
    with_id: bool,
) -> list[str]:
    result = pairs_to_text(_attributes_to_pairs(attributes_dto))
    if attributes_dto.rules:
        result.append("Rules:")
        for rule_dto in attributes_dto.rules:
            result.extend(
                indent(
                    rule_expression_dto_to_lines(rule_dto, with_ids=with_id),
                    indent_step=INDENT_STEP,
                )
            )

    if attributes_dto.lifetime:
        result.append("Lifetime:")
        for rule_dto in attributes_dto.lifetime:
            result.extend(
                indent(
                    rule_expression_dto_to_lines(rule_dto, with_ids=with_id),
                    indent_step=INDENT_STEP,
                )
            )
    return result


def plain_constraint_to_text(
    constraint_dto: CibConstraintLocationDto,
    with_id: bool,
) -> list[str]:
    prefers_part = ""
    score = constraint_dto.attributes.score or "INFINITY"
    if not constraint_dto.attributes.rules:
        prefers_part = " {prefers} node '{node}' with score {score}".format(
            prefers=("avoids" if is_negative_score(score) else "prefers"),
            node=constraint_dto.attributes.node,
            score=abs_score(score),
        )

    result = [
        "{role}resource{resource_pattern} '{resource}'{prefers_part}".format(
            role=format_optional(constraint_dto.role),
            resource_pattern=("" if constraint_dto.resource_id else " pattern"),
            resource=(
                constraint_dto.resource_id or constraint_dto.resource_pattern
            ),
            prefers_part=prefers_part,
        )
    ]
    if with_id:
        result[0] += f" (id: {constraint_dto.attributes.constraint_id})"
    result.extend(
        indent(
            _attributes_to_text(constraint_dto.attributes, with_id),
            indent_step=INDENT_STEP,
        )
    )

    return result


def set_constraint_to_text(
    constraint_dto: CibConstraintLocationSetDto,
    with_id: bool,
) -> list[str]:
    return _set.set_constraint_to_text(
        constraint_dto.attributes.constraint_id,
        _attributes_to_text(constraint_dto.attributes, with_id),
        constraint_dto.resource_sets,
        with_id,
    )


def constraints_to_text(
    plain_dtos: Iterable[CibConstraintLocationDto],
    set_dtos: Iterable[CibConstraintLocationSetDto],
    with_id: bool,
) -> list[str]:
    result = []
    if plain_dtos:
        result.append("Location Constraints:")
        for constraint_dto in plain_dtos:
            result.extend(
                indent(
                    plain_constraint_to_text(constraint_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )
    if set_dtos:
        result.append("Location Set Constraints:")
        for set_constraint_dto in set_dtos:
            result.extend(
                indent(
                    set_constraint_to_text(set_constraint_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )
    return result


def _plain_constraint_get_resource_for_cmd(
    constraint_dto: CibConstraintLocationDto,
) -> str:
    if constraint_dto.resource_id:
        resource = f"resource%{constraint_dto.resource_id}"
    else:
        resource = f"regexp%{constraint_dto.resource_pattern}"
    return shlex.quote(resource)


def _plain_constraint_to_cmd(
    constraint_dto: CibConstraintLocationDto,
) -> list[str]:
    result = [
        "pcs -- constraint location add {id} {resource} {node} {score}".format(
            id=shlex.quote(constraint_dto.attributes.constraint_id),
            resource=_plain_constraint_get_resource_for_cmd(constraint_dto),
            node=shlex.quote(str(constraint_dto.attributes.node)),
            score=constraint_dto.attributes.score,
        )
    ]
    if constraint_dto.attributes.resource_discovery:
        result.extend(
            indent(
                [pairs_to_cmd(_attributes_to_pairs(constraint_dto.attributes))],
                indent_step=INDENT_STEP,
            )
        )
    return result


def _rule_to_cmd_pairs(rule: CibRuleExpressionDto) -> list[tuple[str, str]]:
    pairs = []
    if rule.options.get("role"):
        pairs.append(("role", rule.options["role"]))
    if rule.options.get("score"):
        pairs.append(("score", rule.options["score"]))
    elif rule.options.get("score-attribute"):
        pairs.append(("score-attribute", rule.options["score-attribute"]))
    return pairs


def _add_rule_cmd(constraint_id: str, rule: CibRuleExpressionDto) -> list[str]:
    result = [f"pcs -- constraint rule add {shlex.quote(constraint_id)}"]
    result.extend(
        indent(
            [
                pairs_to_cmd([("id", rule.id)] + _rule_to_cmd_pairs(rule)),
                shlex.join(shlex.split(rule.as_string)),
            ],
            indent_step=INDENT_STEP,
        )
    )
    return result


def _plain_constraint_rule_to_cmd(
    constraint_dto: CibConstraintLocationDto,
) -> list[list[str]]:
    result = [
        "pcs -- constraint location {resource} rule".format(
            resource=_plain_constraint_get_resource_for_cmd(constraint_dto)
        )
    ]
    first_rule, *rest_rules = constraint_dto.attributes.rules
    result.extend(
        indent(
            [
                pairs_to_cmd(
                    [
                        ("id", first_rule.id),
                        (
                            "constraint-id",
                            constraint_dto.attributes.constraint_id,
                        ),
                    ]
                    + _attributes_to_pairs(constraint_dto.attributes)
                    + _rule_to_cmd_pairs(first_rule)
                ),
                shlex.join(shlex.split(first_rule.as_string)),
            ],
            indent_step=INDENT_STEP,
        )
    )
    return [result] + [
        _add_rule_cmd(constraint_dto.attributes.constraint_id, rule)
        for rule in rest_rules
    ]


def plain_constraint_to_cmd(
    constraint_dto: CibConstraintLocationDto,
) -> list[list[str]]:
    if constraint_dto.attributes.lifetime:
        warn(
            "Lifetime configuration detected in constraint "
            f"'{constraint_dto.attributes.constraint_id}' but not supported by "
            "this command."
        )
    if constraint_dto.role:
        warn(
            f"Resource role '{constraint_dto.role}' detected in constraint "
            f"'{constraint_dto.attributes.constraint_id}' but not supported by "
            "this command."
        )
    if constraint_dto.attributes.rules:
        return _plain_constraint_rule_to_cmd(constraint_dto)
    return [_plain_constraint_to_cmd(constraint_dto)]


def _split_based_on_score(
    constraint_dtos: Iterable[CibConstraintLocationDto],
) -> tuple[list[CibConstraintLocationDto], list[CibConstraintLocationDto]]:
    prefers: list[CibConstraintLocationDto] = []
    avoids: list[CibConstraintLocationDto] = []
    for constraint_dto in constraint_dtos:
        if constraint_dto.attributes.score is not None and is_negative_score(
            constraint_dto.attributes.score
        ):
            avoids.append(constraint_dto)
        else:
            prefers.append(constraint_dto)
    return prefers, avoids


def _per_resource_constraint_to_str(
    constraint_dto: CibConstraintLocationDto, with_ids: bool
) -> str:
    return "node '{node}' with score {score}{id}".format(
        node=constraint_dto.attributes.node,
        score=abs_score(constraint_dto.attributes.score or "0"),
        id=(
            f" (id: {constraint_dto.attributes.constraint_id})"
            if with_ids
            else ""
        ),
    )


def _split_with_rules(
    constraint_dtos: Iterable[CibConstraintLocationDto],
) -> tuple[list[CibConstraintLocationDto], list[CibConstraintLocationDto]]:
    without_rules: list[CibConstraintLocationDto] = []
    with_rules: list[CibConstraintLocationDto] = []
    for constraint_dto in constraint_dtos:
        if constraint_dto.attributes.rules:
            with_rules.append(constraint_dto)
        else:
            without_rules.append(constraint_dto)
    return without_rules, with_rules


def _split_patterns(
    constraint_dtos: Iterable[CibConstraintLocationDto],
) -> tuple[list[CibConstraintLocationDto], list[CibConstraintLocationDto]]:
    ids: list[CibConstraintLocationDto] = []
    patterns: list[CibConstraintLocationDto] = []
    for constraint_dto in constraint_dtos:
        if constraint_dto.resource_pattern:
            patterns.append(constraint_dto)
        else:
            ids.append(constraint_dto)
    return ids, patterns


def _labeled_constraints_list_to_text(
    label: str,
    constraint_dtos: Iterable[CibConstraintLocationDto],
    render_fn: Callable[[CibConstraintLocationDto], str],
) -> list[str]:
    result = []
    if constraint_dtos:
        result.extend(
            [f"{label}:"]
            + indent(
                [
                    render_fn(constraint_dto)
                    for constraint_dto in constraint_dtos
                ],
                indent_step=INDENT_STEP,
            ),
        )
    return result


def _with_rules_to_text(
    constraint: CibConstraintLocationDto, with_ids: bool
) -> list[str]:
    result = [
        "Constraint:{id}".format(
            id=f" {constraint.attributes.constraint_id}" if with_ids else ""
        )
    ]
    rules_lines = []
    for rule_dto in constraint.attributes.rules:
        rules_lines.extend(
            indent(
                rule_expression_dto_to_lines(rule_dto, with_ids),
                indent_step=INDENT_STEP,
            )
        )
    result.extend(indent(["Rules:"] + rules_lines, indent_step=INDENT_STEP))
    return result


def _per_resource_constraints_to_text(
    constraint_dtos: Iterable[CibConstraintLocationDto], with_ids: bool
) -> list[str]:
    def render_fn(constraint: CibConstraintLocationDto) -> str:
        return _per_resource_constraint_to_str(constraint, with_ids)

    result = []
    without_rules, with_rules = _split_with_rules(constraint_dtos)
    prefers, avoids = _split_based_on_score(without_rules)
    result.extend(
        _labeled_constraints_list_to_text("Prefers", prefers, render_fn)
    )
    result.extend(
        _labeled_constraints_list_to_text("Avoids", avoids, render_fn)
    )
    for constraint in with_rules:
        result.extend(_with_rules_to_text(constraint, with_ids))
    return result


def constraints_to_grouped_by_resource_text(
    constraint_dtos: Iterable[CibConstraintLocationDto],
    with_ids: bool,
) -> list[str]:
    result = []
    patterns: dict[str, list[CibConstraintLocationDto]] = defaultdict(list)
    resources: dict[str, list[CibConstraintLocationDto]] = defaultdict(list)
    for constraint_dto in constraint_dtos:
        if constraint_dto.resource_pattern:
            patterns[constraint_dto.resource_pattern].append(constraint_dto)
        else:
            resources[str(constraint_dto.resource_id)].append(constraint_dto)
    for resource_id, constraints in resources.items():
        result.append(f"Resource: {resource_id}")
        result.extend(
            indent(
                _per_resource_constraints_to_text(constraints, with_ids),
                indent_step=INDENT_STEP,
            )
        )
    for resource_pattern, constraints in patterns.items():
        result.append(f"Resource pattern: {resource_pattern}")
        result.extend(
            indent(
                _per_resource_constraints_to_text(constraints, with_ids),
                indent_step=INDENT_STEP,
            )
        )

    return result


def _per_node_constraint_to_str(
    constraint_dto: CibConstraintLocationDto, with_ids: bool
) -> str:
    return "resource{pattern} '{id}' with score {score}{constraint_id}".format(
        pattern=" pattern" if constraint_dto.resource_pattern else "",
        id=constraint_dto.resource_pattern or constraint_dto.resource_id,
        score=abs_score(constraint_dto.attributes.score or "0"),
        constraint_id=(
            f" (id: {constraint_dto.attributes.constraint_id})"
            if with_ids
            else ""
        ),
    )


def constraints_to_grouped_by_node_text(
    constraints_dtos: Iterable[CibConstraintLocationDto],
    with_ids: bool,
) -> list[str]:
    constraint_dtos, with_rules = _split_with_rules(constraints_dtos)
    if with_rules:
        warn("Constraints with rules are not displayed.")
    nodes: dict[str, list[CibConstraintLocationDto]] = defaultdict(list)
    for constraint in constraint_dtos:
        if constraint.attributes.node:
            nodes[constraint.attributes.node].append(constraint)
    result = []

    def _render_fn(constraint: CibConstraintLocationDto) -> str:
        return _per_node_constraint_to_str(constraint, with_ids)

    for node, constraints in nodes.items():
        result.extend([f"Node: {node}"])
        prefers, avoids = _split_based_on_score(constraints)
        result.extend(
            indent(
                _labeled_constraints_list_to_text(
                    "Preferred by", prefers, _render_fn
                ),
                indent_step=INDENT_STEP,
            )
        )
        result.extend(
            indent(
                _labeled_constraints_list_to_text(
                    "Avoided by", avoids, _render_fn
                ),
                indent_step=INDENT_STEP,
            )
        )
    return result
