import json
from typing import (
    Iterable,
    TypeVar,
)

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.output import lines_to_str
from pcs.cli.common.parse_args import (
    OUTPUT_FORMAT_VALUE_CMD,
    OUTPUT_FORMAT_VALUE_JSON,
    InputModifiers,
)
from pcs.cli.reports.output import warn
from pcs.common.interface import dto
from pcs.common.pacemaker.constraint import (
    CibConstraintLocationDto,
    CibConstraintLocationSetDto,
    CibConstraintsDto,
)
from pcs.common.types import CibRuleInEffectStatus

from . import (
    colocation,
    location,
    order,
    ticket,
)


def constraints_to_text(
    constraints_dto: CibConstraintsDto, with_id: bool
) -> list[str]:
    return (
        location.constraints_to_text(
            constraints_dto.location, constraints_dto.location_set, with_id
        )
        + colocation.constraints_to_text(
            constraints_dto.colocation, constraints_dto.colocation_set, with_id
        )
        + order.constraints_to_text(
            constraints_dto.order, constraints_dto.order_set, with_id
        )
        + ticket.constraints_to_text(
            constraints_dto.ticket, constraints_dto.ticket_set, with_id
        )
    )


def constraints_to_cmd(constraints_dto: CibConstraintsDto) -> list[list[str]]:
    for location_set_dto in constraints_dto.location_set:
        warn(
            "Location set constraint with id "
            f"'{location_set_dto.attributes.constraint_id}' configured but it's "
            "not supported by this command."
            " Command for creating the constraint is omitted."
        )
    location_cmds = []
    for location_dto in constraints_dto.location:
        location_cmds.extend(location.plain_constraint_to_cmd(location_dto))
    return list(
        filter(
            None,
            (
                location_cmds
                + [
                    colocation.plain_constraint_to_cmd(colocation_dto)
                    for colocation_dto in constraints_dto.colocation
                ]
                + [
                    colocation.set_constraint_to_cmd(colocation_set_dto)
                    for colocation_set_dto in constraints_dto.colocation_set
                ]
                + [
                    order.plain_constraint_to_cmd(order_dto)
                    for order_dto in constraints_dto.order
                ]
                + [
                    order.set_constraint_to_cmd(order_set_dto)
                    for order_set_dto in constraints_dto.order_set
                ]
                + [
                    ticket.plain_constraint_to_cmd(ticket_dto)
                    for ticket_dto in constraints_dto.ticket
                ]
                + [
                    ticket.set_constraint_to_cmd(ticket_set_dto)
                    for ticket_set_dto in constraints_dto.ticket_set
                ]
            ),
        )
    )


CibConstraintLocationAnyDto = TypeVar(
    "CibConstraintLocationAnyDto",
    CibConstraintLocationDto,
    CibConstraintLocationSetDto,
)


def _filter_out_expired_base(
    constraint_dtos: Iterable[CibConstraintLocationAnyDto],
) -> list[CibConstraintLocationAnyDto]:
    return [
        constraint_dto
        for constraint_dto in constraint_dtos
        if not constraint_dto.attributes.rules
        or not all(
            rule.in_effect == CibRuleInEffectStatus.EXPIRED
            for rule in constraint_dto.attributes.rules
        )
    ]


def _filter_constraints(
    constraints_dto: CibConstraintsDto, include_expired: bool
) -> CibConstraintsDto:
    return CibConstraintsDto(
        location=(
            constraints_dto.location
            if include_expired
            else _filter_out_expired_base(constraints_dto.location)
        ),
        location_set=(
            constraints_dto.location_set
            if include_expired
            else _filter_out_expired_base(constraints_dto.location_set)
        ),
        colocation=constraints_dto.colocation,
        colocation_set=constraints_dto.colocation_set,
        order=constraints_dto.order,
        order_set=constraints_dto.order_set,
        ticket=constraints_dto.ticket,
        ticket_set=constraints_dto.ticket_set,
    )


def print_config(
    constraints_dto: CibConstraintsDto, modifiers: InputModifiers
) -> None:
    constraints_dto = _filter_constraints(
        constraints_dto,
        include_expired=modifiers.is_specified("--all"),
    )

    if modifiers.get_output_format() == OUTPUT_FORMAT_VALUE_JSON:
        if modifiers.is_specified("--full"):
            raise CmdLineInputError(
                f"Option '--full' is not compatible with '{modifiers.get_output_format()}' output format."
            )
        print(json.dumps(dto.to_dict(constraints_dto), indent=2))
        return

    if modifiers.get_output_format() == OUTPUT_FORMAT_VALUE_CMD:
        print(
            ";\n".join(
                " \\\n".join(cmd) for cmd in constraints_to_cmd(constraints_dto)
            )
        )
        return

    result = lines_to_str(
        constraints_to_text(constraints_dto, modifiers.is_specified("--full"))
    )
    if result:
        print(result)
