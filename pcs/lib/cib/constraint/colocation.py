from functools import partial

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.constraint import constraint
from pcs.lib.cib.tools import check_new_id_applicable
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import (
    SCORE_INFINITY,
    is_score,
)

TAG_NAME = "rsc_colocation"
DESCRIPTION = "constraint id"


def prepare_options_with_set(cib, options, resource_set_list):
    options = constraint.prepare_options(
        ("score",),
        options,
        partial(constraint.create_id, cib, "colocation", resource_set_list),
        partial(check_new_id_applicable, cib, DESCRIPTION),
    )

    if "score" in options:
        if not is_score(options["score"]):
            raise LibraryError(
                ReportItem.error(
                    reports.messages.InvalidScore(options["score"])
                )
            )
    else:
        options["score"] = SCORE_INFINITY

    return options
