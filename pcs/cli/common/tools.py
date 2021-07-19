from typing import Union

from pcs.common.tools import timeout_to_seconds


def timeout_to_seconds_legacy(
    timeout: Union[int, str]
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
