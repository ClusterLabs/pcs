from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from pcs.cli.constraint.console_report import prepare_attrs


def constraint_plain(constraint_info, with_id=False):
    attributes = constraint_info["attrib"]
    return " ".join(
        [attributes.get("rsc-role", ""), attributes.get("rsc", "")]
        +
        prepare_attrs(
            {
                name:value for name, value in attributes.items()
                if name not in ["rsc-role", "rsc"]
            },
            with_id
        )
    )
