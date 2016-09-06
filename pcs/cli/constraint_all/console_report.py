from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

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
from pcs.common import report_codes as codes


def constraint(constraint_type, constraint_info, with_id=True):
    """
    dict constraint_info  see constraint in pcs/lib/exchange_formats.md
    bool with_id have to show id with options_dict
    """
    if "resource_sets" in constraint_info:
        return constraint_with_sets(constraint_info, with_id)
    return constraint_plain(constraint_type, constraint_info, with_id)

def constraint_plain(constraint_type, options_dict, with_id=False):
    """return console shape for any constraint_type of plain constraint"""
    type_report_map = {
        "rsc_colocation": colocation_plain,
        "rsc_order": order_plain,
        "rsc_ticket": ticket_plain,
    }

    if constraint_type not in type_report_map:
        return constraint_plain_default(constraint_type, options_dict, with_id)

    return type_report_map[constraint_type](options_dict, with_id)

#Each value (callable taking report_item.info) returns string template.
#Optionaly the template can contain placehodler {force} for next processing.
#Placeholder {force} will be appended if is necessary and if is not presset
CODE_TO_MESSAGE_BUILDER_MAP = {
    codes.DUPLICATE_CONSTRAINTS_EXIST: lambda info:
        "duplicate constraint already exists{force}\n" + "\n".join([
            "  " + constraint(info["constraint_type"], constraint_info)
            for constraint_info in info["constraint_info_list"]
        ])
    ,

    codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE: lambda info:
        (
            "{resource_id} is a {mode} resource, you should use the"
            " {parent_type} id: {parent_id} when adding constraints"
        ).format(
            mode="master/slave" if info["parent_type"] == "master" else "clone",
            **info
        )
    ,
}
