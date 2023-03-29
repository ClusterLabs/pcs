from dataclasses import dataclass
from typing import Sequence

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
