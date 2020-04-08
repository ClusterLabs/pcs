from functools import partial

from pcs.common import reports
from pcs.common.reports.item import ReportItem
from pcs.lib.cib.constraint import constraint
from pcs.lib.cib.tools import check_new_id_applicable
from pcs.lib.errors import LibraryError
from pcs.lib.pacemaker.values import is_score, SCORE_INFINITY

TAG_NAME = 'rsc_colocation'
DESCRIPTION = "constraint id"
SCORE_NAMES = ("score", "score-attribute", "score-attribute-mangle")

def prepare_options_with_set(cib, options, resource_set_list):
    options = constraint.prepare_options(
        tuple(SCORE_NAMES),
        options,
        partial(constraint.create_id, cib, TAG_NAME, resource_set_list),
        partial(check_new_id_applicable, cib, DESCRIPTION),
    )

    if "score" in options and not is_score(options["score"]):
        raise LibraryError(
            ReportItem.error(reports.messages.InvalidScore(options["score"]))
        )

    score_attrs_count = len([
        name for name in options.keys() if name in SCORE_NAMES
    ])
    if score_attrs_count > 1:
        raise LibraryError(
            ReportItem.error(reports.messages.MultipleScoreOptions())
        )

    if score_attrs_count == 0:
        options["score"] = SCORE_INFINITY

    return options
