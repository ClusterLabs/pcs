import re
from typing import (
    Optional,
    Union,
)

_INTEGER_RE = re.compile(r"^[+-]?[0-9]+$")


def is_integer(
    value: Union[str, int, float],
    at_least: Optional[int] = None,
    at_most: Optional[int] = None,
) -> bool:
    """
    Check if the specified value is an integer, optionally check a range

    value -- value to check
    at_least -- minimal allowed value
    at_most -- maximal allowed value
    """
    # Using str.isnumeric(), str.isdigit() or str.isdecimal() is not good
    # enough, as they return True for unicode characters which cannot be
    # processed by int() and turned to an integer.
    # Using int() to check a string is not enough, because it allows whitespace
    # in the value.
    try:
        if value is None or isinstance(value, float):
            return False
        if isinstance(value, str) and not _INTEGER_RE.fullmatch(value):
            return False
        value_int = int(value)
        if at_least is not None and value_int < at_least:
            return False
        if at_most is not None and value_int > at_most:
            return False
    except ValueError:
        return False
    return True


def is_port_number(value: str) -> bool:
    """
    Check if the specified value is a TCP or UDP port number

    value -- value to check
    """
    return is_integer(value, 1, 65535)
