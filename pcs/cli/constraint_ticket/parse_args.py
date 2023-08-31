from pcs.cli.common.errors import CmdLineInputError
from pcs.cli.common.parse_args import KeyValueParser


def separate_tail_option_candidates(arg_list):
    for i, arg in enumerate(arg_list):
        if "=" in arg:
            return arg_list[:i], arg_list[i:]

    return arg_list, []


def parse_add(arg_list):
    info, option_candidates = separate_tail_option_candidates(arg_list)

    if not info:
        raise CmdLineInputError("Ticket not specified")

    ticket, resource_specification = info[0], info[1:]

    if len(resource_specification) not in (1, 2):
        raise CmdLineInputError(
            "invalid resource specification: '{0}'".format(
                " ".join(resource_specification)
            )
        )

    if len(resource_specification) == 2:
        resource_role, resource_id = resource_specification
    else:
        resource_role = ""
        resource_id = resource_specification[0]

    return (
        ticket,
        resource_id,
        resource_role,
        KeyValueParser(option_candidates).get_unique(),
    )
