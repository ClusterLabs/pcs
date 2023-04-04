from lxml.etree import _Element

from .colocation import is_colocation_constraint
from .location import is_location_constraint
from .order import is_order_constraint
from .ticket import is_ticket_constraint


def is_constraint(element: _Element) -> bool:
    return any(
        _is_constraint_callback(element)
        for _is_constraint_callback in (
            is_colocation_constraint,
            is_location_constraint,
            is_order_constraint,
            is_ticket_constraint,
        )
    )
