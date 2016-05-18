from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re

from pcs.lib import reports
from pcs.lib.errors import LibraryError


__BOOLEAN_TRUE = ["true", "on", "yes", "y", "1"]
__BOOLEAN_FALSE = ["false", "off", "no", "n", "0"]
SCORE_INFINITY = "INFINITY"


def is_true(val):
    """
    Does pacemaker consider a value to be true?
    See crm_is_true in pacemaker/lib/common/utils.c
    var checked value
    """
    return val.lower() in __BOOLEAN_TRUE

def is_boolean(val):
    """
    Does pacemaker consider a value to be a boolean?
    See crm_is_true in pacemaker/lib/common/utils.c
    val checked value
    """
    return val.lower() in __BOOLEAN_TRUE + __BOOLEAN_FALSE

def timeout_to_seconds(timeout, return_unknown=False):
    """
    Transform pacemaker style timeout to number of seconds
    timeout timeout string
    return_unknown if timeout is not valid then return None on False or timeout
        on True (default False)
    """
    if timeout.isdigit():
        return int(timeout)
    suffix_multiplier = {
        "s": 1,
        "sec": 1,
        "m": 60,
        "min": 60,
        "h": 3600,
        "hr": 3600,
    }
    for suffix, multiplier in suffix_multiplier.items():
        if timeout.endswith(suffix) and timeout[:-len(suffix)].isdigit():
            return int(timeout[:-len(suffix)]) * multiplier
    return timeout if return_unknown else None

def get_valid_timeout_seconds(timeout_candidate):
    """
    Transform pacemaker style timeout to number of seconds, raise LibraryError
        on invalid timeout
    timeout_candidate timeout string or None
    """
    if timeout_candidate is None:
        return None
    wait_timeout = timeout_to_seconds(timeout_candidate)
    if wait_timeout is None:
        raise LibraryError(reports.invalid_timeout(timeout_candidate))
    return wait_timeout

def validate_id(id_candidate, description="id"):
    """
    Validate a pacemaker id, raise LibraryError on invalid id.

    id_candidate id's value
    description id's role description (default "id")
    """
    # see NCName definition
    # http://www.w3.org/TR/REC-xml-names/#NT-NCName
    # http://www.w3.org/TR/REC-xml/#NT-Name
    if len(id_candidate) < 1:
        raise LibraryError(reports.invalid_id_is_empty(
            id_candidate, description
        ))
    first_char_re = re.compile("[a-zA-Z_]")
    if not first_char_re.match(id_candidate[0]):
        raise LibraryError(reports.invalid_id_bad_char(
            id_candidate, description, id_candidate[0], True
        ))
    char_re = re.compile("[a-zA-Z0-9_.-]")
    for char in id_candidate[1:]:
        if not char_re.match(char):
            raise LibraryError(reports.invalid_id_bad_char(
                id_candidate, description, char, False
            ))

def is_score_value(value):
    if not value:
        return False
    unsigned_value = value[1:] if value[0] in ("+", "-") else value
    return unsigned_value == SCORE_INFINITY or unsigned_value.isdigit()
