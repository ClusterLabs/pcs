from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys


def error(message, exit=True):
    sys.stderr.write("Error: {0}\n".format(message))
    if exit:
        sys.exit(1)

def indent(line_list, indent_step=2):
    """
    return line list where each line of input is prefixed by N spaces
    list of string line_list are original lines
    int indent_step is count of spaces for line prefix
    """
    return [
        "{0}{1}".format(" "*indent_step, line) if line else line
        for line in line_list
    ]
