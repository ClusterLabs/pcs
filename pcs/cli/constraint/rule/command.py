from typing import Any

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    InputModifiers,
    ensure_unique_args,
)
from pcs.cli.reports.output import deprecation_warning
from pcs.common.pacemaker.constraint import get_all_location_rules_ids
from pcs.common.str_tools import format_list


def remove(lib: Any, argv: Argv, modifiers: InputModifiers) -> None:
    """
    Options:
      * -f - CIB file
    """
    # deprecated in pacemaker 2, removed in pacemaker 3
    # added to pcs after 0.11.8
    # the whole command removed in pcs-0.12
    deprecation_warning(
        "The possibility of defining multiple rules in a single location "
        "constraint is deprecated and will be removed."
    )
    modifiers.ensure_only_supported("-f")
    if not argv:
        raise CmdLineInputError()
    ensure_unique_args(argv)
    missing_ids = set(argv) - get_all_location_rules_ids(
        lib.constraint.get_config(evaluate_rules=False)
    )
    if missing_ids:
        raise CmdLineInputError(
            f"Unable to find constraint rules: {format_list(missing_ids)}"
        )
    lib.cib.remove_elements(argv)
