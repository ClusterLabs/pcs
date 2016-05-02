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
    options = {}
    for arg in cmdline_args:
        if "=" not in arg:
            raise CmdLineInputError("missing value of '{0}' option".format(arg))
        if arg.startswith("="):
            raise CmdLineInputError("missing key in '{0}' option".format(arg))

        name, value = arg.split("=", 1)
        options[name] = value
    return options
