from typing import (
    Iterable,
    List,
    Mapping,
    Optional,
)


def indent(line_list: Iterable[str], indent_step: int = 2) -> List[str]:
    """
    return line list where each line of input is prefixed by N spaces

    line_list -- original lines
    indent_step -- count of spaces for line prefix
    """
    return [
        "{0}{1}".format(" " * indent_step, line) if line else line
        for line in line_list
    ]


def format_list(
    item_list: Iterable[str],
    optional_transformations: Optional[Mapping[str, str]] = None
) -> str:
    if not optional_transformations:
        optional_transformations = {}

    return ", ".join(sorted([
        "'{0}'".format(optional_transformations.get(item, item))
        for item in item_list
    ]))


def join_multilines(strings):
    return "\n".join([a.strip() for a in strings if a.strip()])
