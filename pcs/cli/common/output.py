import textwrap
import sys
from shutil import get_terminal_size
from typing import List


def format_with_indentation(
    text: str, indentation: int = 0, max_length_trim: int = 0
) -> List[str]:
    if any((sys.stdout.isatty(), sys.stderr.isatty())):
        return textwrap.wrap(
            text,
            max(get_terminal_size()[0] - max_length_trim, 40),
            subsequent_indent=" " * indentation,
        )
    return [text]
