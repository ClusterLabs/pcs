import re
from collections import namedtuple

from pcs.common import reports
from pcs.common.reports import (
    ReportItem,
    get_severity,
)
from pcs.lib.booth import constants
from pcs.lib.interface.config import (
    ExporterInterface,
    ParserErrorException,
    ParserInterface,
)


class ConfigItem(namedtuple("ConfigItem", "key value details")):
    __slots__ = ()

    def __new__(cls, key, value, details=None):
        return super().__new__(cls, key, value, details or [])


class InvalidLines(ParserErrorException):
    pass


class Parser(ParserInterface):
    @staticmethod
    def parse(raw_file_data):
        return _organize_lines(
            _parse_to_raw_lines(raw_file_data.decode("utf-8"))
        )

    @staticmethod
    def exception_to_report_list(
        exception, file_type_code, file_path, force_code, is_forced_or_warning
    ):
        del file_type_code  # this is defined by the report code
        if isinstance(exception, InvalidLines):
            return [
                ReportItem(
                    severity=get_severity(force_code, is_forced_or_warning),
                    message=reports.messages.BoothConfigUnexpectedLines(
                        exception.args[0],
                        file_path,
                    ),
                )
            ]
        raise exception


class Exporter(ExporterInterface):
    @staticmethod
    def export(config_structure):
        return "\n".join(_build_to_lines(config_structure) + [""]).encode(
            "utf-8"
        )


def _build_to_lines(config_line_list, deep=0):
    line_list = []
    for key, value, details in config_line_list:
        line_value = value if key != "ticket" else f'"{value}"'
        indent = "  " * deep
        line_list.append(f"{indent}{key} = {line_value}")
        if details:
            line_list.extend(_build_to_lines(details, deep + 1))
    return line_list


def _organize_lines(raw_line_list):
    # Decision: Global key is moved up when is below ticket. Alternative is move
    # it below all ticket details. But it is confusing.
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
    list re_object_list contains regular expression objects (products of
        re.compile)
    """
    for expression in re_object_list:
        match = expression.search(string)
        if match:
            return match
    return None


def _parse_to_raw_lines(config_content):
    keyword_part = r"^(?P<key>[a-zA-Z0-9_-]+)\s*=\s*"
    expression_list = [
        re.compile(pattern.format(keyword_part))
        for pattern in [
            r"""{0}(?P<value>[^'"]+)$""",
            r"""{0}'(?P<value>[^']*)'\s*(#.*)?$""",
            r"""{0}"(?P<value>[^"]*)"\s*(#.*)?$""",
        ]
    ]

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
