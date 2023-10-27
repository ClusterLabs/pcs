from dataclasses import dataclass
from typing import (
    Iterable,
    Sequence,
    Union,
)

from pcs.common.interface.dto import DataTransferObject

from .colocation import (
    CibConstraintColocationDto,
    CibConstraintColocationSetDto,
)
from .location import (
    CibConstraintLocationDto,
    CibConstraintLocationSetDto,
)
from .order import (
    CibConstraintOrderDto,
    CibConstraintOrderSetDto,
)
from .ticket import (
    CibConstraintTicketDto,
    CibConstraintTicketSetDto,
)


@dataclass(frozen=True)
class CibConstraintsDto(DataTransferObject):
    # pylint: disable=too-many-instance-attributes
    location: Sequence[CibConstraintLocationDto] = tuple()
    location_set: Sequence[CibConstraintLocationSetDto] = tuple()
    colocation: Sequence[CibConstraintColocationDto] = tuple()
    colocation_set: Sequence[CibConstraintColocationSetDto] = tuple()
    order: Sequence[CibConstraintOrderDto] = tuple()
    order_set: Sequence[CibConstraintOrderSetDto] = tuple()
    ticket: Sequence[CibConstraintTicketDto] = tuple()
    ticket_set: Sequence[CibConstraintTicketSetDto] = tuple()


def _get_constraint_ids(
    constraint_dtos: Iterable[
        Union[
            CibConstraintLocationDto,
            CibConstraintLocationSetDto,
            CibConstraintColocationDto,
            CibConstraintColocationSetDto,
            CibConstraintOrderDto,
            CibConstraintOrderSetDto,
            CibConstraintTicketDto,
            CibConstraintTicketSetDto,
        ]
    ]
) -> list[str]:
    return [
        constraint_dto.attributes.constraint_id
        for constraint_dto in constraint_dtos
    ]


def get_all_constraints_ids(constraints_dto: CibConstraintsDto) -> set[str]:
    return set(
        _get_constraint_ids(constraints_dto.location)
        + _get_constraint_ids(constraints_dto.location_set)
        + _get_constraint_ids(constraints_dto.colocation)
        + _get_constraint_ids(constraints_dto.colocation_set)
        + _get_constraint_ids(constraints_dto.order)
        + _get_constraint_ids(constraints_dto.order_set)
        + _get_constraint_ids(constraints_dto.ticket)
        + _get_constraint_ids(constraints_dto.ticket_set)
    )
