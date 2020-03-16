# pylint: disable=too-many-lines
from functools import partial

from pcs.common.reports import codes as report_codes
from pcs.common.reports import ReportItem, ReportItemSeverity

def forceable_error(force_code, report_creator, *args, **kwargs):
    """
    Return ReportItem created by report_creator.

    This is experimental shortcut for common pattern. It is intended to
    cooperate with functions "error" and  "warning".
    the pair with function "warning".

    string force_code is code for forcing error
    callable report_creator is function that produce ReportItem. It must take
        parameters forceable (None or force code) and severity
        (from ReportItemSeverity)
    rest of args are for the report_creator
    """
    return report_creator(
        *args,
        forceable=force_code,
        severity=ReportItemSeverity.ERROR,
        **kwargs
    )

def warning(report_creator, *args, **kwargs):
    """
    Return ReportItem created by report_creator.

    This is experimental shortcut for common pattern. It is intended to
    cooperate with functions "error" and  "forceable_error".

    callable report_creator is function that produce ReportItem. It must take
        parameters forceable (None or force code) and severity
        (from ReportItemSeverity)
    rest of args are for the report_creator
    """
    return report_creator(
        *args,
        forceable=None,
        severity=ReportItemSeverity.WARNING,
        **kwargs
    )

def error(report_creator, *args, **kwargs):
    """
    Return ReportItem created by report_creator.

    This is experimental shortcut for common pattern. It is intended to
    cooperate with functions "forceable_error" and "forceable_error".

    callable report_creator is function that produce ReportItem. It must take
        parameters forceable (None or force code) and severity
        (from ReportItemSeverity)
    rest of args are for the report_creator
    """
    return report_creator(
        *args,
        forceable=None,
        severity=ReportItemSeverity.ERROR,
        **kwargs
    )

def get_problem_creator(force_code=None, is_forced=False):
    """
    Returns report creator wraper (forceable_error or warning).

    This is experimental shortcut for decision if ReportItem will be
    either forceable_error or warning.

    string force_code is code for forcing error. It could be usefull to prepare
        it for whole module by using functools.partial.
    bool warn_only is flag for selecting wrapper
    """
    if not force_code:
        return error
    if is_forced:
        return warning
    return partial(forceable_error, force_code)

def _key_numeric(item):
    return (int(item), item) if item.isdigit() else (-1, item)


def duplicate_constraints_exist(
    constraint_type, constraint_info_list,
    severity=ReportItemSeverity.ERROR, forceable=None
):
    """
    when creating a constraint it was detected the constraint already exists
    constraint_type string "rsc_colocation", "rsc_order", "rsc_ticket"
    constraint_info_list list of structured constraint data according to type
    severity report item severity
    forceable is this report item forceable? by what category?
    """
    return ReportItem(
        report_codes.DUPLICATE_CONSTRAINTS_EXIST,
        severity,
        info={
            "constraint_type": constraint_type,
            "constraint_info_list": constraint_info_list,
        },
        forceable=forceable
    )
