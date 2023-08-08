from typing import Union

from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import (
    Argv,
    prepare_options,
    split_list,
)


def prepare_resource_sets(
    cmdline_args: Argv,
) -> list[dict[str, Union[list[str], dict[str, Union[str, list[str]]]]]]:
    return [
        {
            "ids": [id for id in args if "=" not in id],
            "options": prepare_options([opt for opt in args if "=" in opt]),
        }
        for args in split_list(cmdline_args, "set")
    ]


def prepare_set_args(
    argv: Argv,
) -> tuple[
    list[dict[str, Union[list[str], dict[str, Union[str, list[str]]]]]],
    dict[str, Union[str, list[str]]],
]:
    args_groups = split_list(argv, "setoptions")
    if len(args_groups) > 2:
        raise CmdLineInputError(
            "Keyword 'setoptions' may be mentioned at most once"
        )
    resource_set_args = args_groups[0]
    constraint_options_args = args_groups[1] if len(args_groups) == 2 else []

    if not resource_set_args:
        raise CmdLineInputError()

    resource_set_list = prepare_resource_sets(resource_set_args)
    if not resource_set_list or not all(
        resource_set["ids"] for resource_set in resource_set_list
    ):
        raise CmdLineInputError()

    constraint_options = {}
    if constraint_options_args:
        constraint_options = prepare_options(constraint_options_args)

    return (resource_set_list, constraint_options)
