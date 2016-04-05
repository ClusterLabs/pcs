from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib import error_codes
from pcs.lib.errors import ReportItem, LibraryError
from pcs.lib.corosync import config_parser
from pcs.lib.node import NodeAddresses, NodeAddressesList

class ConfigFacade(object):
    """
    Provides high level access to a corosync config file
    """

    QUORUM_OPTIONS = (
        "auto_tie_breaker",
        "last_man_standing",
        "last_man_standing_window",
        "wait_for_all",
    )

    @classmethod
    def from_string(cls, config_string):
        """
        Parse corosync config and create a facade around it
        config_string corosync config text
        """
        try:
            return cls(config_parser.parse_string(config_string))
        except config_parser.MissingClosingBraceException:
            raise LibraryError(ReportItem.error(
                error_codes.PARSE_ERROR_COROSYNC_CONF_MISSING_CLOSING_BRACE,
                "Unable to parse corosync config: missing closing brace"
            ))
        except config_parser.UnexpectedClosingBraceException:
            raise LibraryError(ReportItem.error(
                error_codes.PARSE_ERROR_COROSYNC_CONF_UNEXPECTED_CLOSING_BRACE,
                "Unable to parse corosync config: unexpected closing brace"
            ))
        except config_parser.CorosyncConfParserException:
            raise LibraryError(ReportItem.error(
                error_codes.PARSE_ERROR_COROSYNC_CONF,
                "Unable to parse corosync config"
            ))

    def __init__(self, parsed_config):
        """
        Create a facade around a parsed corosync config file
        parsed_config parsed corosync config
        """
        self._config = parsed_config

    @property
    def config(self):
        return self._config

    def get_nodes(self):
        """
        Get all defined nodes
        """
        result = NodeAddressesList()
        for nodelist in self.config.get_sections("nodelist"):
            for node in nodelist.get_sections("node"):
                node_data = {
                    "ring0_addr": None,
                    "ring1_addr": None,
                    "name": None,
                    "nodeid": None,
                }
                for attr_name, attr_value in node.get_attributes():
                    if attr_name in node_data:
                        node_data[attr_name] = attr_value
                result.append(NodeAddresses(
                    node_data["ring0_addr"],
                    node_data["ring1_addr"],
                    node_data["name"],
                    node_data["nodeid"]
                ))
        return result

    def set_quorum_options(self, options):
        """
        Set options in "quorum" section
        options quorum options dict
        """
        self.__validate_quorum_options(options)
        quorum_section_list = self.__ensure_section(self.config, "quorum")
        for section in quorum_section_list[:-1]:
            for name in options:
                section.del_attributes_by_name(name)
        for name, value in options.items():
            if value == "":
                quorum_section_list[-1].del_attributes_by_name(name)
            else:
                quorum_section_list[-1].set_attribute(name, value)

    def get_quorum_options(self):
        """
        Get configurable options from quorum section
        """
        options = {}
        for section in self.config.get_sections("quorum"):
            for name, value in section.get_attributes():
                if name in self.__class__.QUORUM_OPTIONS:
                    options[name] = value
        return options

    def __validate_quorum_options(self, options):
        report = []
        for name, value in options.items():

            allowed_names = self.__class__.QUORUM_OPTIONS
            if name not in allowed_names:
                report.append(ReportItem.error(
                    error_codes.INVALID_OPTION,
                    "invalid {type} option '{option}'"
                        + ", allowed options are: {allowed}"
                    ,
                    info={
                        "option": name,
                        "type": "quorum",
                        "allowed_raw": allowed_names,
                        "allowed": " or ".join(allowed_names),
                    },
                ))
                continue

            if value == "":
                continue

            if name == "last_man_standing_window":
                if not value.isdigit():
                    report.append(ReportItem.error(
                        error_codes.INVALID_OPTION_VALUE,
                        "'{option_value}' is not a valid value for "
                            + "{option_name}, use {allowed_values}"
                        ,
                        info={
                            "option_name": name,
                            "option_value": value,
                            "allowed_types_raw": ("integer", ),
                            "allowed_values": "integer",
                        },
                    ))

            else:
                allowed_values = ("0", "1")
                if value not in allowed_values:
                    report.append(ReportItem.error(
                        error_codes.INVALID_OPTION_VALUE,
                        "'{option_value}' is not a valid value for "
                            + "{option_name}, use {allowed_values}"
                        ,
                        info={
                            "option_name": name,
                            "option_value": value,
                            "allowed_values_raw": allowed_values,
                            "allowed_values": " or ".join(allowed_values),
                        },
                    ))

        if report:
            raise LibraryError(*report)

    def __ensure_section(self, parent_section, section_name):
        section_list = parent_section.get_sections(section_name)
        if not section_list:
            new_section = config_parser.Section(section_name)
            parent_section.add_section(new_section)
            section_list.append(new_section)
        return section_list
