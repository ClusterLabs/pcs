import sys
import textwrap
from shlex import quote
from shutil import get_terminal_size
from typing import (
    Iterable,
    List,
)

from pcs.common.types import (
    StringIterable,
    StringSequence,
)

INDENT_STEP = 2
SUBSEQUENT_INDENT_STEP = 4


def bool_to_cli_value(value: bool) -> str:
    return "1" if value else "0"


def _smart_wrap(
    text: str, subsequent_indent: int = SUBSEQUENT_INDENT_STEP
) -> List[str]:
    initial_indent = len(text) - len(text.lstrip(" "))
    return format_wrap_for_terminal(
        text, subsequent_indent=subsequent_indent + initial_indent
    )


def smart_wrap_text(
    lines: StringSequence, subsequent_indent: int = SUBSEQUENT_INDENT_STEP
) -> List[str]:
    output = []
    for line in lines:
        if not line:
            output.append("")
            continue
        output.extend(_smart_wrap(line, subsequent_indent=subsequent_indent))
    return output


def format_wrap_for_terminal(
    text: str,
    subsequent_indent: int = SUBSEQUENT_INDENT_STEP,
    trim: int = 0,
) -> List[str]:
    """
    Returns text as a list of lines. Length of a line is determined by a
    terminal size if not explicitly specified.

    text -- string to format
    subsequent_indent -- number of spaces all subsequent lines will be indented
        compared to the first one.
    trim -- number which will be substracted from terminal size. Can be used in
        cases lines will be indented later by this number of spaces.
    """
    if (sys.stdout is not None and sys.stdout.isatty()) or (
        sys.stderr is not None and sys.stderr.isatty()
    ):
        return format_wrap(
            text,
            # minimal line length is 40
            max(get_terminal_size()[0] - trim, 40),
            subsequent_indent=subsequent_indent,
        )
    return [text]


def format_wrap(
    text: str,
    max_length: int,
    subsequent_indent: int = SUBSEQUENT_INDENT_STEP,
) -> List[str]:
    return textwrap.wrap(
        text,
        max_length,
        subsequent_indent=" " * subsequent_indent,
    )


def options_to_cmd(options: StringIterable) -> str:
    return " ".join(quote(option) for option in options)


def pair_to_cmd(pair: tuple[str, str]) -> str:
    return quote("=".join(pair))


def pairs_to_cmd(pairs: Iterable[tuple[str, str]]) -> str:
    return " ".join(pair_to_cmd(item) for item in pairs)


def lines_to_str(lines: StringSequence) -> str:
    return "\n".join(smart_wrap_text(lines))
