from typing import (
    Mapping,
    Optional,
    Type,
)

from pcs.common import (
    file_type_codes,
    reports,
)
from pcs.lib.corosync import constants
from pcs.lib.interface.config import (
    ExporterInterface,
    ParserErrorException,
    ParserInterface,
)


class Section:
    def __init__(self, name):
        self._parent = None
        self._attr_list = []
        self._section_list = []
        self._name = str(name)

    @property
    def parent(self):
        return self._parent

    @property
    def name(self):
        return self._name

    @property
    def empty(self):
        return not self._attr_list and not self._section_list

    def export(self, indent="    "):
        lines = []
        for attr in self._attr_list:
            lines.append("{0}: {1}".format(*attr))
        if self._attr_list and self._section_list:
            lines.append("")
        section_count = len(self._section_list)
        for index, section in enumerate(self._section_list, 1):
            lines.extend(str(section).split("\n"))
            if not lines[-1].strip():
                del lines[-1]
            if index < section_count:
                lines.append("")
        if self.parent:
            lines = [indent + x if x else x for x in lines]
            lines.insert(0, self.name + " {")
            lines.append("}")
        final = "\n".join(lines)
        if final:
            final += "\n"
        return final

    def get_root(self):
        parent = self
        while parent.parent:
            parent = parent.parent
        return parent

    def get_attributes(self, name=None):
        return [
            attr for attr in self._attr_list if name is None or attr[0] == name
        ]

    def get_attributes_dict(self):
        return {attr[0]: attr[1] for attr in self._attr_list}

    def get_attribute_value(self, name, default=None):
        return self.get_attributes_dict().get(name, default)

    def add_attribute(self, name, value):
        name, value = str(name), str(value)
        self._attr_list.append([name, value])
        return self

    def del_attribute(self, attribute):
        self._attr_list = [
            attr for attr in self._attr_list if attr != attribute
        ]
        return self

    def del_attributes_by_name(self, name, value=None):
        self._attr_list = [
            attr
            for attr in self._attr_list
            if not (attr[0] == name and (value is None or attr[1] == value))
        ]
        return self

    def set_attribute(self, name, value):
        name, value = str(name), str(value)
        found = False
        new_attr_list = []
        for attr in self._attr_list:
            if attr[0] != name:
                new_attr_list.append(attr)
            elif not found:
                found = True
                attr[1] = value
                new_attr_list.append(attr)
        self._attr_list = new_attr_list
        if not found:
            self.add_attribute(name, value)
        return self

    def get_sections(self, name=None):
        return [
            section
            for section in self._section_list
            if name is None or section.name == name
        ]

    def add_section(self, section):
        parent = self
        while parent:
            if parent == section:
                raise CircularParentshipException()
            parent = parent.parent
        if section.parent:
            section.parent.del_section(section)
        # here we are editing obj's _parent attribute of the same class
        # pylint: disable=protected-access
        section._parent = self
        self._section_list.append(section)
        return self

    def del_section(self, section):
        self._section_list.remove(section)
        # don't set parent to None if the section was not found in the list
        # thanks to remove raising a ValueError in that case
        # here we are editing obj's _parent attribute of the same class
        # pylint: disable=protected-access
        section._parent = None
        return self

    def __str__(self):
        return self.export()


class Parser(ParserInterface):
    @staticmethod
    def parse(raw_file_data: bytes) -> Section:
        root = Section("")
        Parser._parse_section(raw_file_data.decode("utf-8").split("\n"), root)
        return root

    @staticmethod
    def exception_to_report_list(
        exception: ParserErrorException,
        file_type_code: file_type_codes.FileTypeCode,
        file_path: Optional[str],
        force_code: Optional[reports.types.ForceCode],
        is_forced_or_warning: bool,
    ) -> reports.ReportItemList:
        # TODO switch to new exceptions / reports and do not ignore input
        # arguments of the function
        return [
            reports.ReportItem.error(
                Parser.parser_exception_to_report_msg(exception)
            )
        ]

    @staticmethod
    def _parse_section(lines, section):
        # parser should work the same way as the original parser in corosync
        while lines:
            current_line = lines.pop(0).strip()
            if not current_line or current_line[0] == "#":
                continue
            if "{" in current_line:
                section_name_candidate, after_brace_junk = current_line.rsplit(
                    "{", 1
                )
                if after_brace_junk.strip():
                    raise ExtraCharactersAfterOpeningBraceException()
                section_name = section_name_candidate.strip()
                if not section_name:
                    raise MissingSectionNameBeforeOpeningBraceException()
                new_section = Section(section_name.strip())
                section.add_section(new_section)
                Parser._parse_section(lines, new_section)
            elif "}" in current_line:
                if current_line.strip() != "}":
                    raise ExtraCharactersBeforeOrAfterClosingBraceException()
                if not section.parent:
                    raise UnexpectedClosingBraceException()
                return
            elif ":" in current_line:
                section.add_attribute(
                    *[x.strip() for x in current_line.split(":", 1)]
                )
            else:
                raise LineIsNotSectionNorKeyValueException()
        if section.parent:
            raise MissingClosingBraceException()

    @staticmethod
    def parser_exception_to_report_msg(
        exception: ParserErrorException,
    ) -> reports.item.ReportItemMessage:
        exc_to_msg: Mapping[
            Type[ParserErrorException], Type[reports.item.ReportItemMessage]
        ] = {
            MissingClosingBraceException: (
                reports.messages.ParseErrorCorosyncConfMissingClosingBrace
            ),
            UnexpectedClosingBraceException: (
                reports.messages.ParseErrorCorosyncConfUnexpectedClosingBrace
            ),
            MissingSectionNameBeforeOpeningBraceException: (
                reports.messages.ParseErrorCorosyncConfMissingSectionNameBeforeOpeningBrace
            ),
            ExtraCharactersAfterOpeningBraceException: (
                reports.messages.ParseErrorCorosyncConfExtraCharactersAfterOpeningBrace
            ),
            ExtraCharactersBeforeOrAfterClosingBraceException: (
                reports.messages.ParseErrorCorosyncConfExtraCharactersBeforeOrAfterClosingBrace
            ),
            LineIsNotSectionNorKeyValueException: (
                reports.messages.ParseErrorCorosyncConfLineIsNotSectionNorKeyValue
            ),
        }
        return exc_to_msg.get(
            type(exception), reports.messages.ParseErrorCorosyncConf
        )()


class Exporter(ExporterInterface):
    @staticmethod
    def export(config_structure: Section) -> bytes:
        return config_structure.export().encode("utf-8")


def verify_section(section, path_prefix=""):
    # prevents putting in any characters which break corosync.conf structure
    bad_section_name_list = []
    bad_attribute_name_list = []
    bad_attribute_value_list = []

    path = _prefix_path(path_prefix, section.name)
    # the root section has no name yet it is valid
    if section.name != "" and not _is_valid_name(section.name):
        bad_section_name_list.append(path)
    for name, value in section.get_attributes():
        if not _is_valid_name(name):
            bad_attribute_name_list.append(_prefix_path(path, name))
        if not _is_valid_value(value):
            bad_attribute_value_list.append((_prefix_path(path, name), value))
    for child_section in section.get_sections():
        bad_sections, bad_attr_names, bad_attr_values = verify_section(
            child_section, path
        )
        bad_section_name_list += bad_sections
        bad_attribute_name_list += bad_attr_names
        bad_attribute_value_list += bad_attr_values

    return (
        bad_section_name_list,
        bad_attribute_name_list,
        bad_attribute_value_list,
    )


def _prefix_path(prefix, path):
    return f"{prefix}.{path}" if prefix and path else path


def _is_valid_name(name):
    return constants.OPTION_NAME_RE.fullmatch(name) is not None


def _is_valid_value(value):
    # pylint: disable=superfluous-parens
    return not (set(value) & set("{}\n\r"))


class CorosyncConfParserException(ParserErrorException):
    pass


class CircularParentshipException(CorosyncConfParserException):
    pass


class ParsingErrorException(CorosyncConfParserException):
    pass


class MissingClosingBraceException(ParsingErrorException):
    pass


class UnexpectedClosingBraceException(ParsingErrorException):
    pass


class MissingSectionNameBeforeOpeningBraceException(ParsingErrorException):
    pass


class ExtraCharactersAfterOpeningBraceException(ParsingErrorException):
    pass


class ExtraCharactersBeforeOrAfterClosingBraceException(ParsingErrorException):
    pass


class LineIsNotSectionNorKeyValueException(ParsingErrorException):
    pass
