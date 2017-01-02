from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.errors import CmdLineInputError


ARG_TYPE_DELIMITER = "%"

# h = help, f = file,
# p = password (cluster auth), u = user (cluster auth),
# V = verbose (cluster verify)
PCS_SHORT_OPTIONS = "hf:p:u:V"
PCS_LONG_OPTIONS = [
    "debug", "version", "help", "fullhelp",
    "force", "skip-offline", "autocorrect", "interactive", "autodelete",
    "all", "full", "groups", "local", "wait", "config",
    "start", "enable", "disabled", "off",
    "pacemaker", "corosync",
    "no-default-ops", "defaults", "nodesc",
    "clone", "master", "name=", "group=", "node=",
    "from=", "to=", "after=", "before=",
    "transport=", "rrpmode=", "ipv6",
    "addr0=", "bcast0=", "mcast0=", "mcastport0=", "ttl0=", "broadcast0",
    "addr1=", "bcast1=", "mcast1=", "mcastport1=", "ttl1=", "broadcast1",
    "wait_for_all=", "auto_tie_breaker=", "last_man_standing=",
    "last_man_standing_window=",
    "token=", "token_coefficient=", "consensus=", "join=",
    "miss_count_const=", "fail_recv_const=",
    "corosync_conf=", "cluster_conf=",
    "booth-conf=", "booth-key=",
    "remote", "watchdog=",
    #in pcs status - do not display resorce status on inactive node
    "hide-inactive",
]

def split_list(arg_list, separator):
    """return list of list of arg_list using separator as delimiter"""
    separator_indexes = [i for i, x in enumerate(arg_list) if x == separator]
    bounds = zip([0]+[i+1 for i in separator_indexes], separator_indexes+[None])
    return [arg_list[i:j] for i, j in bounds]

def split_option(arg):
    """
    Get (key, value) from a key=value commandline argument.

    Split the argument by the first = and return resulting parts. Raise
    CmdLineInputError if the argument cannot be splitted.

    string arg -- commandline argument
    """
    if "=" not in arg:
        raise CmdLineInputError("missing value of '{0}' option".format(arg))
    if arg.startswith("="):
        raise CmdLineInputError("missing key in '{0}' option".format(arg))
    return arg.split("=", 1)

def prepare_options(cmdline_args):
    """return dictionary of options from commandline key=value args"""
    options = dict()
    for arg in cmdline_args:
        name, value = split_option(arg)
        options[name] = value
    return options

def group_by_keywords(
    arg_list, keyword_set,
    implicit_first_keyword=None, keyword_repeat_allowed=True,
):
    groups = dict([(keyword, []) for keyword in keyword_set])
    if implicit_first_keyword:
        groups[implicit_first_keyword] = []

    if not arg_list:
        return groups

    used_keywords = []
    if implicit_first_keyword:
        used_keywords.append(implicit_first_keyword)
    elif arg_list[0] not in keyword_set:
        raise CmdLineInputError()

    for arg in arg_list:
        if arg in list(groups.keys()):
            if arg in used_keywords and not keyword_repeat_allowed:
                raise CmdLineInputError()
            used_keywords.append(arg)
        else:
            groups[used_keywords[-1]].append(arg)

    return groups

def parse_typed_arg(arg, allowed_types, default_type):
    """
    Get (type, value) from a typed commandline argument.

    Split the argument by the type separator and return the type and the value.
    Raise CmdLineInputError in the argument format or type is not valid.
    string arg -- commandline argument
    Iterable allowed_types -- list of allowed argument types
    string default_type -- type to return if the argument doesn't specify a type
    """
    if ARG_TYPE_DELIMITER not in arg:
        return default_type, arg
    arg_type, arg_value = arg.split(ARG_TYPE_DELIMITER, 1)
    if not arg_type:
        return default_type, arg_value
    if arg_type not in allowed_types:
        raise CmdLineInputError(
            "'{arg_type}' is not an allowed type for '{arg_full}', use {hint}"
            .format(
                arg_type=arg_type,
                arg_full=arg,
                hint=", ".join(sorted(allowed_types))
            )
        )
    return arg_type, arg_value

def is_num(arg):
    return arg.isdigit() or arg.lower() == "infinity"

def is_negative_num(arg):
    return arg.startswith("-") and is_num(arg[1:])

def is_short_option_expecting_value(arg):
    return (
        len(arg) == 2
        and
        arg[0] == "-"
        and
        "{0}:".format(arg[1]) in PCS_SHORT_OPTIONS
    )

def is_long_option_expecting_value(arg):
    return (
        len(arg) > 2
        and
        arg[0:2] == "--"
        and
        "{0}=".format(arg[2:]) in PCS_LONG_OPTIONS
    )

def is_option_expecting_value(arg):
    return (
        is_short_option_expecting_value(arg)
        or
        is_long_option_expecting_value(arg)
    )

def filter_out_non_option_negative_numbers(arg_list):
    """
    Return arg_list without non-option negative numbers.
    Negative numbers following the option expecting value are kept.

    There is the problematic legacy.
    Argumet "--" has special meaning: can be used to signal that no more
    options will follow. This would solve the problem with negative numbers in
    a standard way: there would be no special approach to negative numbers,
    everything would be left in the hands of users. But now it would be
    backward incompatible change.

    list arg_list contains command line arguments
    """
    args_without_negative_nums = []
    for i, arg in enumerate(arg_list):
        prev_arg = arg_list[i-1] if i > 0 else ""
        if not is_negative_num(arg) or is_option_expecting_value(prev_arg):
            args_without_negative_nums.append(arg)

    return args_without_negative_nums

def filter_out_options(arg_list):
    """
    Return arg_list without options and its negative numbers.

    list arg_list contains command line arguments
    """
    args_without_options = []
    for i, arg in enumerate(arg_list):
        prev_arg = arg_list[i-1] if i > 0 else ""
        if(
            not is_option_expecting_value(prev_arg)
            and (
                not arg.startswith("-")
                or
                arg == "-"
                or
                is_negative_num(arg)
            )
        ):
            args_without_options.append(arg)
    return args_without_options
