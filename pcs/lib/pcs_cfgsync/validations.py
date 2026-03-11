from typing import Mapping

from pcs.common import reports
from pcs.lib import validate
from pcs.lib.pcs_cfgsync.actions import UPDATE_SYNC_OPTIONS_ACTIONS


def validate_update_sync_options(
    options: Mapping[str, str],
) -> reports.ReportItemList:
    allowed_options = UPDATE_SYNC_OPTIONS_ACTIONS.keys()
    return validate.ValidatorAll(
        [
            validate.NamesIn(allowed_options),
            validate.IsRequiredSome(allowed_options),
            validate.MutuallyExclusive(
                ["sync_thread_disable", "sync_thread_enable"]
            ),
            validate.MutuallyExclusive(
                ["sync_thread_pause", "sync_thread_resume"]
            ),
            validate.ValueInteger("sync_thread_pause", at_least=0),
        ]
    ).validate(options)
