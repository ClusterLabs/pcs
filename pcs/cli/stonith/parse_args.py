from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.parse_args import group_by_keywords, prepare_options
from pcs.cli.resource.parse_args import build_operations

def parse_create(arg_list):
    groups = group_by_keywords(
        arg_list,
        set(["op", "meta"]),
        implicit_first_group_key="options",
        group_repeated_keywords=["op"],
    )

    parts = {
        "meta":  prepare_options(groups.get("meta", [])),
        "options":  prepare_options(groups.get("options", [])),
        "op": [
            prepare_options(op)
            for op in build_operations(groups.get("op", []))
        ],
    }

    return parts
