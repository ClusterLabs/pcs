from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from pcs.cli.constraint.console_report import (
    constraint_plain as constraint_plain_default,
    constraint_with_sets,
)
from pcs.cli.constraint_colocation.console_report import (
    constraint_plain as colocation_plain
)
from pcs.cli.constraint_order.console_report import (
    constraint_plain as order_plain
)
from pcs.cli.constraint_ticket.console_report import (
    constraint_plain as ticket_plain
)


def get_type_report_map():
    return {
        "rsc_colocation": colocation_plain,
        "rsc_order": order_plain,
        "rsc_ticket": ticket_plain,
    }

def constraint(type, constraint_info, with_id=True):
    if "resource_sets" in constraint_info:
        return constraint_with_sets(constraint_info, with_id)
    return constraint_plain(type, constraint_info, with_id)

def constraint_plain(type, attributes, with_id=False):
    return (
        get_type_report_map().get(
            type,
            partial(constraint_plain_default, type)
        )(attributes, with_id)
    )

def duplicit_constraints_report(report_item):
    line_list = []
    for constraint_with_sets in report_item.info["constraint_info_list"]:
        line_list.append(
            constraint(report_item.info["type"], constraint_with_sets)
        )

    return (
        "duplicate constraint already exists, use --force to override\n"
        +"\n".join(["  "+line for line in line_list])
    )
