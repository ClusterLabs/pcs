from shlex import quote
from typing import Iterable

from pcs.cli.common.output import (
    INDENT_STEP,
    pairs_to_cmd,
)
from pcs.common.pacemaker.constraint import (
    CibConstraintTicketAttributesDto,
    CibConstraintTicketDto,
    CibConstraintTicketSetDto,
)
from pcs.common.str_tools import (
    format_optional,
    indent,
    pairs_to_text,
)

from . import set as _set


def _attributes_to_pairs(
    attributes_dto: CibConstraintTicketAttributesDto,
) -> list[tuple[str, str]]:
    pairs = []
    if attributes_dto.loss_policy:
        pairs.append(("loss-policy", str(attributes_dto.loss_policy)))
    return pairs


def plain_constraint_to_text(
    constraint_dto: CibConstraintTicketDto,
    with_id: bool,
) -> list[str]:
    result = [
        "{role}resource '{resource}' depends on ticket '{ticket}'".format(
            role=format_optional(constraint_dto.role),
            resource=constraint_dto.resource_id,
            ticket=constraint_dto.attributes.ticket,
        )
    ]
    if with_id:
        result[0] += f" (id: {constraint_dto.attributes.constraint_id})"
    result.extend(
        indent(
            pairs_to_text(_attributes_to_pairs(constraint_dto.attributes)),
            indent_step=INDENT_STEP,
        )
    )
    return result


def set_constraint_to_text(
    constraint_dto: CibConstraintTicketSetDto,
    with_id: bool,
) -> list[str]:
    return _set.set_constraint_to_text(
        constraint_dto.attributes.constraint_id,
        pairs_to_text(
            [("ticket", constraint_dto.attributes.ticket)]
            + _attributes_to_pairs(constraint_dto.attributes)
        ),
        constraint_dto.resource_sets,
        with_id,
    )


def constraints_to_text(
    plain_dtos: Iterable[CibConstraintTicketDto],
    set_dtos: Iterable[CibConstraintTicketSetDto],
    with_id: bool,
) -> list[str]:
    result = []
    if plain_dtos:
        result.append("Ticket Constraints:")
        for constraint_dto in plain_dtos:
            result.extend(
                indent(
                    plain_constraint_to_text(constraint_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )
    if set_dtos:
        result.append("Ticket Set Constraints:")
        for set_constraint_dto in set_dtos:
            result.extend(
                indent(
                    set_constraint_to_text(set_constraint_dto, with_id),
                    indent_step=INDENT_STEP,
                )
            )
    return result


def _attributes_to_cmd_pairs(
    attributes_dto: CibConstraintTicketAttributesDto,
) -> list[tuple[str, str]]:
    return [("id", attributes_dto.constraint_id)] + _attributes_to_pairs(
        attributes_dto
    )


def plain_constraint_to_cmd(
    constraint_dto: CibConstraintTicketDto,
) -> list[str]:
    result = [
        "pcs -- constraint ticket add {ticket} {role}{resource_id}".format(
            ticket=quote(constraint_dto.attributes.ticket),
            role=format_optional(constraint_dto.role),
            resource_id=quote(constraint_dto.resource_id),
        )
    ]
    params = pairs_to_cmd(_attributes_to_cmd_pairs(constraint_dto.attributes))
    if params:
        result.extend(indent([params], indent_step=INDENT_STEP))
    return result


def set_constraint_to_cmd(
    constraint_dto: CibConstraintTicketSetDto,
) -> list[str]:
    result = ["pcs -- constraint ticket"]
    for resource_set in constraint_dto.resource_sets:
        set_cmd_part = _set.resource_set_to_cmd(resource_set)
        if not set_cmd_part:
            return []
        result.extend(indent(set_cmd_part, indent_step=INDENT_STEP))
    params = pairs_to_cmd(
        _attributes_to_cmd_pairs(constraint_dto.attributes)
        + [("ticket", constraint_dto.attributes.ticket)]
    )
    if params:
        result.extend(indent([f"setoptions {params}"], indent_step=INDENT_STEP))
    return result
