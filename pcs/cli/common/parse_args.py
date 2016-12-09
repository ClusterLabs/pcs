from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.errors import CmdLineInputError

ARG_TYPE_DELIMITER = "%"

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
