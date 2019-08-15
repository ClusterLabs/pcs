from collections import namedtuple
import re

from pcs.lib import file_interfaces
from pcs.lib.booth import constants, reports
from pcs.lib.errors import LibraryError

class ConfigItem(namedtuple("ConfigItem", "key value details")):
    def __new__(cls, key, value, details=None):
        details = details if details else []
        return super(ConfigItem, cls).__new__(cls, key, value, details)

class InvalidLines(Exception):
    pass

class Parser(file_interfaces.ParserInterface):
    def _main_parse(self):
        try:
            return _organize_lines(
                _parse_to_raw_lines(
                    self._raw_file_data.decode("utf-8")
                )
            )
        except InvalidLines as e:
            self._parse_error = True
            self._report_list.append(
                reports.booth_config_unexpected_lines(e.args[0])
            )

class Exporter(file_interfaces.ExporterInterface):
    @staticmethod
    def export(config_structure):
        return "\n".join(
            _build_to_lines(config_structure) + [""]
        ).encode("utf-8")

# TODO remove
def parse(content):
    try:
        return _organize_lines(_parse_to_raw_lines(content))
    except InvalidLines as e:
        raise LibraryError(
            reports.booth_config_unexpected_lines(e.args[0])
        )

# TODO remove
def build(config_line_list):
    newline = [""]
    return "\n".join(_build_to_lines(config_line_list) + newline)

def _build_to_lines(config_line_list, deep=0):
    line_list = []
    for key, value, details in config_line_list:
        line_value = value if key != "ticket" else '"{0}"'.format(value)
        line_list.append("{0}{1} = {2}".format("  "*deep, key, line_value))
        if details:
            line_list.extend(_build_to_lines(details, deep+1))
    return line_list


def _organize_lines(raw_line_list):
    #Decision: Global key is moved up when is below ticket. Alternative is move
    #it below all ticket details. But it is confusing.
    global_section = []
    ticket_section = []
    current_ticket = None
    for key, value in raw_line_list:
        if key == "ticket":
            current_ticket = ConfigItem(key, value)
            ticket_section.append(current_ticket)
        elif key in constants.GLOBAL_KEYS or not current_ticket:
            global_section.append(ConfigItem(key, value))
        else:
            current_ticket.details.append(ConfigItem(key, value))

    return global_section + ticket_section

def _search_with_multiple_re(re_object_list, string):
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

def _parse_to_raw_lines(config_content):
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
        match = _search_with_multiple_re(expression_list, line)
        if match:
            line_list.append((match.group("key"), match.group("value")))
        elif line and not line.startswith("#"):
            invalid_line_list.append(line)

    if invalid_line_list:
        raise InvalidLines(invalid_line_list)

    return line_list
