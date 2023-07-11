from shlex import quote
from typing import Iterable

from pcs.cli.common.output import (
    INDENT_STEP,
    bool_to_cli_value,
    pairs_to_cmd,
)
from pcs.cli.reports.output import warn
from pcs.common.pacemaker.constraint import (
    CibConstraintOrderAttributesDto,
    CibConstraintOrderDto,
    CibConstraintOrderSetDto,
)
from pcs.common.str_tools import (
    format_optional,
    indent,
    pairs_to_text,
)

from . import set as _set


def _attributes_to_pairs(
    attributes_dto: CibConstraintOrderAttributesDto,
) -> list[tuple[str, str]]:
    pairs = []
    if attributes_dto.symmetrical is not None:
        pairs.append(
            ("symmetrical", bool_to_cli_value(attributes_dto.symmetrical))
        )
    if attributes_dto.require_all is not None:
        pairs.append(
            ("require-all", bool_to_cli_value(attributes_dto.require_all))
        )
    if attributes_dto.score:
        pairs.append(("score", attributes_dto.score))
    if attributes_dto.kind:
        pairs.append(("kind", attributes_dto.kind))
    return pairs


def _attributes_to_text(
    attributes_dto: CibConstraintOrderAttributesDto,
) -> list[str]:
    return pairs_to_text(_attributes_to_pairs(attributes_dto))


def plain_constraint_to_text(
    constraint_dto: CibConstraintOrderDto,
    with_id: bool,
) -> list[str]:
    result = [
        "{first_action}resource '{first_resource}' then {then_action}resource '{then_resource}'".format(
            first_action=format_optional(constraint_dto.first_action),
            first_resource=constraint_dto.first_resource_id,
            then_action=format_optional(constraint_dto.then_action),
            then_resource=constraint_dto.then_resource_id,
        )
    ]
    if with_id:
        result[0] += f" (id: {constraint_dto.attributes.constraint_id})"
    result.extend(
        indent(
            _attributes_to_text(constraint_dto.attributes),
            indent_step=INDENT_STEP,
        )
    )
    return result


def set_constraint_to_text(
    constraint_dto: CibConstraintOrderSetDto,
    with_id: bool,
) -> list[str]:
    return _set.set_constraint_to_text(
        constraint_dto.attributes.constraint_id,
        _attributes_to_text(constraint_dto.attributes),
        constraint_dto.resource_sets,
        with_id,
    )


def constraints_to_text(
    plain_dtos: Iterable[CibConstraintOrderDto],
    set_dtos: Iterable[CibConstraintOrderSetDto],
    with_id: bool,
) -> list[str]:
    result = []
    if plain_dtos:
        result.append("Order Constraints:")
        for constraint_dto in plain_dtos:
            result.extend(
                indent(
                    plain_constraint_to_text(constraint_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )
    if set_dtos:
        result.append("Order Set Constraints:")
        for set_constraint_dto in set_dtos:
            result.extend(
                indent(
                    set_constraint_to_text(set_constraint_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )
    return result


def _attributes_to_cmd_pairs(
    attributes_dto: CibConstraintOrderAttributesDto,
) -> list[tuple[str, str]]:
    return [("id", attributes_dto.constraint_id)] + _attributes_to_pairs(
        attributes_dto
    )


def plain_constraint_to_cmd(
    constraint_dto: CibConstraintOrderDto,
) -> list[str]:
    if (
        constraint_dto.first_resource_instance is not None
        or constraint_dto.then_resource_instance is not None
    ):
        warn(
            "Resource instance(s) detected in constraint "
            f"'{constraint_dto.attributes.constraint_id}' but not supported by "
            "this command."
            " Command for creating the constraint is omitted."
        )
        return []
    result = [
        "pcs -- constraint order {first_action}{first_resource_id} then {then_action}{then_resource_id}".format(
            first_action=format_optional(constraint_dto.first_action),
            first_resource_id=quote(constraint_dto.first_resource_id),
            then_action=format_optional(constraint_dto.then_action),
            then_resource_id=quote(constraint_dto.then_resource_id),
        )
    ]
    params = pairs_to_cmd(_attributes_to_cmd_pairs(constraint_dto.attributes))
    if params:
        result.extend(indent([params], indent_step=INDENT_STEP))
    return result


def set_constraint_to_cmd(
    constraint_dto: CibConstraintOrderSetDto,
) -> list[str]:
    result = ["pcs -- constraint order"]
    for resource_set in constraint_dto.resource_sets:
        set_cmd_part = _set.resource_set_to_cmd(resource_set)
        if not set_cmd_part:
            return []
        result.extend(indent(set_cmd_part, indent_step=INDENT_STEP))
    pairs = []
    for pair in _attributes_to_cmd_pairs(constraint_dto.attributes):
        # this list is based on pcs.lib.cib.constraint.order.ATTRIB
        if pair[0] not in ("symmetrical", "kind", "id"):
            warn(
                f"Option '{pair[0]}' detected in constraint "
                f"'{constraint_dto.attributes.constraint_id}' but not "
                "supported by this command."
                " Command for creating the constraint is omitted."
            )
            return []
        pairs.append(pair)
    if pairs:
        result.extend(
            indent(
                [f"setoptions {pairs_to_cmd(pairs)}"], indent_step=INDENT_STEP
            )
        )
    return result
