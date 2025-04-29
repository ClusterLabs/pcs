from typing import (
    Any,
    Optional,
)

from pcs.cli.reports.output import error
from pcs.common import reports
from pcs.common.str_tools import format_optional


def check_is_stonith(
    lib: Any,
    resource_id_list: list[str],
    cmd_to_use: Optional[str] = None,
) -> None:
    if lib.resource.is_any_resource_except_stonith(resource_id_list):
        raise error(
            reports.messages.CommandArgumentTypeMismatch("resources").message
            + format_optional(cmd_to_use, " Please use '{}' instead.")
        )
