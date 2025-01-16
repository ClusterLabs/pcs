import sys
from typing import Union

from pcs.common.tools import timeout_to_seconds


def timeout_to_seconds_legacy(
    timeout: Union[int, str],
) -> Union[int, str, None]:
    """
    Transform pacemaker style timeout to number of seconds. If timeout is not
    valid then `timeout` is returned.

    timeout -- timeout string
    """
    parsed_timeout = timeout_to_seconds(timeout)
    if parsed_timeout is None:
        return timeout
    return parsed_timeout


def print_to_stderr(output: str, end: str = "\n") -> None:
    """
    Prints output to stderr and flushes

    str output -- a string that is printed to stderr
    str end -- an optional ending, newline by default as Python's print
    """
    sys.stderr.write(f"{output}{end}")
    sys.stderr.flush()
