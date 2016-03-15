from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re

from pcs.lib import error_codes
from pcs.lib.errors import LibraryError, ReportItem


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
        raise LibraryError(ReportItem.error(
            error_codes.INVALID_ID,
            "{description} cannot be empty",
            info={
                "id": id_candidate,
                "description": description,
                "reason": "empty",
            }
        ))
    first_char_re = re.compile("[a-zA-Z_]")
    if not first_char_re.match(id_candidate[0]):
        raise LibraryError(ReportItem.error(
            error_codes.INVALID_ID,
            "invalid {description} '{id}', '{invalid_character}' is not " +
                "a valid first character for a {description}"
            ,
            info={
                "id": id_candidate,
                "description": description,
                "reason": "invalid first character",
                "invalid_character": id_candidate[0],
            }
        ))
    char_re = re.compile("[a-zA-Z0-9_.-]")
    for char in id_candidate[1:]:
        if not char_re.match(char):
            raise LibraryError(ReportItem.error(
                error_codes.INVALID_ID,
                "invalid {description} '{id}', '{invalid_character}' is not " +
                    "a valid character for a {description}"
                ,
                info={
                    "id": id_candidate,
                    "description": description,
                    "reason": "invalid character",
                    "invalid_character": char,
                }
            ))

