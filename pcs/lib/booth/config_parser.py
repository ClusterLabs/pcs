from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import re

from pcs.lib.booth import config_structure, reports
from pcs.lib.errors import LibraryError


class InvalidLines(Exception):
    pass

def parse(content):
    try:
        return organize_lines(parse_to_raw_lines(content))
    except InvalidLines as e:
        raise LibraryError(
            reports.booth_config_unexpected_lines(e.args[0])
        )

def build(config_line_list):
    newline = [""]
    return "\n".join(build_to_lines(config_line_list) + newline)

def build_to_lines(config_line_list, deep=0):
    line_list = []
    for key, value, details in config_line_list:
        line_value = value if key != "ticket" else '"{0}"'.format(value)
        line_list.append("{0}{1} = {2}".format("  "*deep, key, line_value))
        if details:
            line_list.extend(build_to_lines(details, deep+1))
    return line_list


def organize_lines(raw_line_list):
    #Decision: Global key is moved up when is below ticket. Alternative is move
    #it below all ticket details. But it is confusing.
    global_section = []
    ticket_section = []
    current_ticket = None
    for key, value in raw_line_list:
        if key == "ticket":
            current_ticket = config_structure.ConfigItem(key, value)
            ticket_section.append(current_ticket)
        elif key in config_structure.GLOBAL_KEYS or not current_ticket:
            global_section.append(config_structure.ConfigItem(key, value))
        else:
            current_ticket.details.append(
                config_structure.ConfigItem(key, value)
            )

    return global_section + ticket_section

def search_with_multiple_re(re_object_list, string):
    """
    return MatchObject of first matching regular expression object or None
    list re_object_list contains regular expresssion objects (products of
        re.compile)
    """
    for expression in re_object_list:
        match = expression.search(string)
        if match:
            return match
    return None

def parse_to_raw_lines(config_content):
    keyword_part = r"^(?P<key>[a-zA-Z0-9_-]+)\s*=\s*"
    expression_list = [re.compile(pattern.format(keyword_part)) for pattern in [
        r"""{0}(?P<value>[^'"]+)$""",
        r"""{0}'(?P<value>[^']*)'\s*(#.*)?$""",
        r"""{0}"(?P<value>[^"]*)"\s*(#.*)?$""",
    ]]

    line_list = []
    invalid_line_list = []
    for line in config_content.splitlines():
        line = line.strip()
        match = search_with_multiple_re(expression_list, line)
        if match:
            line_list.append((match.group("key"), match.group("value")))
        elif line and not line.startswith("#"):
            invalid_line_list.append(line)

    if invalid_line_list:
        raise InvalidLines(invalid_line_list)

    return line_list
