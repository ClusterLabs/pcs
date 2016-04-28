from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.cli.constraint.console_report import prepare_options


def constraint_plain(constraint_info, with_id=False):
    """
    dict constraint_info  see constraint in pcs/lib/exchange_formats.md
    bool with_id have to show id with options_dict
    """
    options = constraint_info["options"]
    return " ".join(
        [options.get("rsc-role", ""), options.get("rsc", "")]
        +
        prepare_options(
            dict(
                (name, value) for name, value in options.items()
                if name not in ["rsc-role", "rsc"]
            ),
            with_id
        )
    )
