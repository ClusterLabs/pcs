from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common import parse_args
from pcs.cli.common.errors import CmdLineInputError


def prepare_resource_sets(cmdline_args):
    return [
        {
            "ids": [id for id in args if "=" not in id],
            "options": parse_args.prepare_options(
                [opt for opt in args if "=" in opt]
            ),
        } for args in parse_args.split_list(cmdline_args, "set")
    ]

def prepare_set_args(argv):
    if argv.count("setoptions") > 1:
        raise CmdLineInputError(
            "Keyword 'setoptions' may be mentioned at most once"
        )

    resource_set_args, constraint_options_args = (
        parse_args.split_list(argv, "setoptions")
        if "setoptions" in argv else (argv, [])
    )

    if not resource_set_args:
        raise CmdLineInputError()

    resource_set_list = prepare_resource_sets(resource_set_args)
    if(
        not resource_set_list
        or
        not all(resource_set["ids"] for resource_set in resource_set_list)
    ):
        raise CmdLineInputError()

    constraint_options = {}
    if constraint_options_args:
        constraint_options = parse_args.prepare_options(constraint_options_args)

    return (resource_set_list, constraint_options)
