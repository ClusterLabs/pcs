from .colocation import constraint_plain as colocation_plain
from .common import constraint_plain as constraint_plain_default
from .common import constraint_with_sets
from .order import constraint_plain as order_plain
from .ticket import constraint_plain as ticket_plain


def constraint_to_str(constraint_type, constraint_info):
    """
    dict constraint_info  see constraint in pcs/lib/exchange_formats.md
    """
    if "resource_sets" in constraint_info:
        return constraint_with_sets(constraint_info)
    return _constraint_plain(constraint_type, constraint_info)


def _constraint_plain(constraint_type, options_dict):
    """return console shape for any constraint_type of plain constraint"""
    type_report_map = {
        "rsc_colocation": colocation_plain,
        "rsc_order": order_plain,
        "rsc_ticket": ticket_plain,
    }

    if constraint_type not in type_report_map:
        return constraint_plain_default(constraint_type, options_dict)
    return type_report_map[constraint_type](options_dict)
