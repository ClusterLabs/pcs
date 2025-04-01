from shlex import quote
from typing import (
    Iterable,
    Optional,
)

from pcs.cli.common.output import (
    INDENT_STEP,
    pairs_to_cmd,
)
from pcs.cli.reports.output import warn
from pcs.cli.rule import rule_expression_dto_to_lines
from pcs.common.pacemaker.constraint import (
    CibConstraintColocationAttributesDto,
    CibConstraintColocationDto,
    CibConstraintColocationSetDto,
)
from pcs.common.str_tools import (
    format_name_value_list,
    format_optional,
    indent,
)
from pcs.common.types import StringCollection

from . import set as _set


def _attributes_to_pairs(
    attributes_dto: CibConstraintColocationAttributesDto,
) -> list[tuple[str, str]]:
    pairs = []
    if attributes_dto.score:
        pairs.append(("score", attributes_dto.score))
    if attributes_dto.influence:
        pairs.append(("influence", attributes_dto.influence))
    return pairs


def _attributes_to_text(
    attributes_dto: CibConstraintColocationAttributesDto,
    with_id: bool,
    extra_attributes: Iterable[tuple[str, str]] = (),
) -> list[str]:
    result = [
        " ".join(
            format_name_value_list(
                _attributes_to_pairs(attributes_dto) + list(extra_attributes)
            )
        )
    ]
    if attributes_dto.lifetime:
        result.append("Lifetime:")
        for rule_dto in attributes_dto.lifetime:
            result.extend(
                indent(
                    rule_expression_dto_to_lines(rule_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )

    return result


def plain_constraint_to_text(
    constraint_dto: CibConstraintColocationDto,
    with_id: bool,
) -> list[str]:
    result = [
        "{resource_role}resource '{resource_id}' with {with_resource_role}resource '{with_resource_id}'".format(
            resource_role=format_optional(constraint_dto.resource_role),
            resource_id=constraint_dto.resource_id,
            with_resource_role=format_optional(
                constraint_dto.with_resource_role
            ),
            with_resource_id=constraint_dto.with_resource_id,
        )
    ]
    if with_id:
        result[0] += f" (id: {constraint_dto.attributes.constraint_id})"
    extra_attributes = []
    if constraint_dto.node_attribute:
        extra_attributes += [
            ("node-attribute", constraint_dto.node_attribute),
        ]
    result.extend(
        indent(
            _attributes_to_text(
                constraint_dto.attributes, with_id, extra_attributes
            ),
            indent_step=INDENT_STEP,
        )
    )
    return result


def set_constraint_to_text(
    constraint_dto: CibConstraintColocationSetDto,
    with_id: bool,
) -> list[str]:
    return _set.set_constraint_to_text(
        constraint_dto.attributes.constraint_id,
        _attributes_to_text(constraint_dto.attributes, with_id),
        constraint_dto.resource_sets,
        with_id,
    )


def constraints_to_text(
    plain_dtos: Iterable[CibConstraintColocationDto],
    set_dtos: Iterable[CibConstraintColocationSetDto],
    with_id: bool,
) -> list[str]:
    result = []
    if plain_dtos:
        result.append("Colocation Constraints:")
        for constraint_dto in plain_dtos:
            result.extend(
                indent(
                    plain_constraint_to_text(constraint_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )
    if set_dtos:
        result.append("Colocation Set Constraints:")
        for set_constraint_dto in set_dtos:
            result.extend(
                indent(
                    set_constraint_to_text(set_constraint_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )
    return result


def _attributes_to_cmd_pairs(
    attributes_dto: CibConstraintColocationAttributesDto,
    filter_out: StringCollection = tuple(),
) -> Optional[list[tuple[str, str]]]:
    if attributes_dto.lifetime:
        warn(
            "Lifetime configuration detected in constraint "
            f"'{attributes_dto.constraint_id}' but not supported by this "
            "command."
            " Command for creating the constraint is omitted."
        )
        return None
    unsupported_options = {"influence"}
    result = []
    for pair in [("id", attributes_dto.constraint_id)] + _attributes_to_pairs(
        attributes_dto
    ):
        if pair[0] in unsupported_options:
            warn(
                f"Option '{pair[0]}' detected in constraint "
                f"'{attributes_dto.constraint_id}' but not supported by this "
                "command."
                " Command for creating the constraint is omitted."
            )
            return None
        if pair[0] in filter_out:
            continue
        result.append(pair)
    return result


def plain_constraint_to_cmd(
    constraint_dto: CibConstraintColocationDto,
) -> list[str]:
    if (
        constraint_dto.resource_instance is not None
        or constraint_dto.with_resource_instance is not None
    ):
        warn(
            "Resource instance(s) detected in constraint "
            f"'{constraint_dto.attributes.constraint_id}' but not supported by "
            "this command."
            " Command for creating the constraint is omitted."
        )
        return []
    if constraint_dto.node_attribute is not None:
        warn(
            "Option 'node-attribute' detected in constraint "
            f"'{constraint_dto.attributes.constraint_id}' but not supported by "
            "this command."
            " Command for creating the constraint is omitted."
        )
        return []
    result = [
        "pcs -- constraint colocation add {resource_role}{resource_id} with {with_resource_role}{with_resource_id}".format(
            resource_role=format_optional(constraint_dto.resource_role),
            resource_id=quote(constraint_dto.resource_id),
            with_resource_role=format_optional(
                constraint_dto.with_resource_role
            ),
            with_resource_id=quote(constraint_dto.with_resource_id),
        )
    ]
    pairs = _attributes_to_cmd_pairs(constraint_dto.attributes)
    if pairs is None:
        return []
    params = pairs_to_cmd(pairs)
    if params:
        result.extend(indent([params], indent_step=INDENT_STEP))
    return result


def set_constraint_to_cmd(
    constraint_dto: CibConstraintColocationSetDto,
) -> list[str]:
    result = ["pcs -- constraint colocation"]
    for resource_set in constraint_dto.resource_sets:
        set_cmd_part = _set.resource_set_to_cmd(resource_set)
        if not set_cmd_part:
            return []
        result.extend(indent(set_cmd_part, indent_step=INDENT_STEP))
    pairs = _attributes_to_cmd_pairs(constraint_dto.attributes)
    if pairs is None:
        return []
    params = pairs_to_cmd(pairs)
    if params:
        result.extend(indent([f"setoptions {params}"], indent_step=INDENT_STEP))
    return result
