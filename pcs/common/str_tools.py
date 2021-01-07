from collections.abc import Iterable as IterableAbc
from typing import (
    Any,
    Iterable,
    List,
    Mapping,
    Optional,
    Sequence,
    Tuple,
    TypeVar,
    Union,
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
    item_list: List[str],  # Intetionaly not Sequence so string is prohibited
    separator: str = ", ",
) -> str:
    item_list = sorted(item_list)

    to_value = lambda item: f"'{item}'"

    if len(item_list) == 1:
        return to_value(item_list[0])

    return separator.join(sorted([to_value(item) for item in item_list]))


def format_list_custom_last_separator(
    item_list: List[str],  # Intetionaly not Sequence so string is prohibited
    last_separator: str,
    separator: str = ", ",
) -> str:
    item_list = sorted(item_list)
    if len(item_list) < 2:
        return format_list(item_list, separator=separator)
    return "{}{}{}".format(
        format_list(item_list[:-1], separator=separator),
        last_separator,
        format_list(item_list[-1:], separator=separator),
    )


# For now, Tuple[str, str] is sufficient. Feel free to change it if needed,
# e.g. when values can be integers.
def format_name_value_list(item_list: Sequence[Tuple[str, str]]) -> List[str]:
    """
    Turn 2-tuples to 'name=value' strings with standard quoting
    """
    output = []
    for name, value in item_list:
        name = quote(name, "= ")
        value = quote(value, "= ")
        output.append(f"{name}={value}")
    return output


def quote(string: str, chars_to_quote: str) -> str:
    """
    Quote a string if it contains specified characters

    string -- the string to be processed
    chars_to_quote -- the characters causing quoting
    """
    if not frozenset(chars_to_quote) & frozenset(string):
        return string
    if '"' not in string:
        return f'"{string}"'
    if "'" not in string:
        return f"'{string}'"
    return '"{string}"'.format(string=string.replace('"', '\\"'))


def join_multilines(strings):
    return "\n".join([a.strip() for a in strings if a.strip()])


def format_optional(
    value: Any,
    template: str = "{} ",
    empty_case: str = "",
) -> str:
    # Number 0 is considered False which does not suit our needs so we check
    # for it explicitly. Beware that False == 0 is true, so we must have an
    # additional check for that (bool is a subclass of int).
    if value or (
        isinstance(value, int) and not isinstance(value, bool) and value == 0
    ):
        return template.format(value)
    return empty_case


def _is_multiple(what):
    """
    Return True if 'what' does not mean one item, False otherwise

    iterable/int what -- this will be counted
    """
    retval = False
    if isinstance(what, int):
        retval = abs(what) != 1
    elif not isinstance(what, str):
        try:
            retval = len(what) != 1
        except TypeError:
            pass
    return retval


def _add_s(word):
    """
    add "s" or "es" to the word based on its ending

    string word -- word where "s" or "es" should be added
    """
    if word[-1:] in ("s", "x", "o") or word[-2:] in ("ss", "sh", "ch"):
        return word + "es"
    return word + "s"


def format_plural(
    depends_on: Union[int, Iterable[Any]],
    singular: str,
    plural: Optional[str] = None,
) -> str:
    """
    Takes the singular word form and returns its plural form if depends_on
    is not equal to one/contains one item

    iterable/int/string depends_on -- if number (of items) isn't equal to one,
        returns plural
    singular -- singular word (like: is, do, node)
    plural -- optional irregular plural form
    """
    common_plurals = {
        "is": "are",
        "has": "have",
        "does": "do",
    }
    if not _is_multiple(depends_on):
        return singular
    if plural:
        return plural
    if singular in common_plurals:
        return common_plurals[singular]
    return _add_s(singular)


T = TypeVar("T")


def transform(items: List[T], mapping: Mapping[T, str]) -> List[str]:
    return list(map(lambda item: mapping.get(item, str(item)), items))


def is_iterable_not_str(value):
    return isinstance(value, IterableAbc) and not isinstance(value, str)
