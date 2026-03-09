from typing import Mapping

from pcs.common import reports
from pcs.lib import validate

_OPTIONS = (
    "sync_thread_disable",
    "sync_thread_enable",
    "sync_thread_pause",
    "sync_thread_resume",
)


def validate_update_sync_options(
    options: Mapping[str, str],
) -> reports.ReportItemList:
    return validate.ValidatorAll(
        [
            validate.NamesIn(_OPTIONS),
            validate.IsRequiredSome(_OPTIONS),
            validate.MutuallyExclusive(
                ["sync_thread_disable", "sync_thread_enable"]
            ),
            validate.MutuallyExclusive(
                ["sync_thread_pause", "sync_thread_resume"]
            ),
            validate.ValueInteger("sync_thread_pause", at_least=0),
        ]
    ).validate(options)
