import sys
import textwrap
from shutil import get_terminal_size
from typing import List


def format_with_indentation(
    text: str,
    indentation: int = 0,
    indent_first: bool = False,
    max_length_trim: int = 0,
    max_length: int = 0,
) -> List[str]:
    """
    Returns text as a list of lines. Length of a line is determined by a
    terminal size if not explicitely specified.

    text -- string to format
    indentation -- number of spaces to put at the begining of each line (except
        first one)
    indent_first -- if True also indent the first line by the same number of
        spaces as defined as `indentation` argument
    max_length_trim -- number which will be substracted from maximal line
        length. Can be used in cases lines will be indented later by this
        number of spaces.
    max_length -- maximal line length. Terminal size is used if less than or
        equal to 0.
    """
    if any((sys.stdout.isatty(), sys.stderr.isatty())):
        indent = " " * indentation
        default_max_length = 40
        if max_length <= 0:
            max_length = get_terminal_size()[0]
        return textwrap.wrap(
            text,
            max(
                max_length - max_length_trim,
                default_max_length,
            ),
            initial_indent=indent if indent_first else "",
            subsequent_indent=indent,
        )
    return [text]
