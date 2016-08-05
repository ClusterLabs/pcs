from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.cli.common.errors import CmdLineInputError

def split_list(arg_list, separator):
    """return list of list of arg_list using separator as delimiter"""
    separator_indexes = [i for i, x in enumerate(arg_list) if x == separator]
    bounds = zip([0]+[i+1 for i in separator_indexes], separator_indexes+[None])
    return [arg_list[i:j] for i, j in bounds]

def prepare_options(cmdline_args):
    """return dictionary of options from comandline key=value args"""
    options = dict()
    for arg in cmdline_args:
        if "=" not in arg:
            raise CmdLineInputError("missing value of '{0}' option".format(arg))
        if arg.startswith("="):
            raise CmdLineInputError("missing key in '{0}' option".format(arg))

        name, value = arg.split("=", 1)
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
