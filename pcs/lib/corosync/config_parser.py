class Section:

    def __init__(self, name):
        self._parent = None
        self._attr_list = []
        self._section_list = []
        self._name = name

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
        self._attr_list.append([name, value])
        return self

    def del_attribute(self, attribute):
        self._attr_list = [
            attr for attr in self._attr_list if attr != attribute
        ]
        return self

    def del_attributes_by_name(self, name, value=None):
        self._attr_list = [
            attr for attr in self._attr_list
                if not(attr[0] == name and (value is None or attr[1] == value))
        ]
        return self

    def set_attribute(self, name, value):
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
            section for section in self._section_list
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


def parse_string(conf_text):
    root = Section("")
    _parse_section(conf_text.split("\n"), root)
    return root

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
            _parse_section(lines, new_section)
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


class CorosyncConfParserException(Exception):
    pass

class CircularParentshipException(CorosyncConfParserException):
    pass

class ParseErrorException(CorosyncConfParserException):
    pass

class MissingClosingBraceException(ParseErrorException):
    pass

class UnexpectedClosingBraceException(ParseErrorException):
    pass

class MissingSectionNameBeforeOpeningBraceException(ParseErrorException):
    pass

class ExtraCharactersAfterOpeningBraceException(ParseErrorException):
    pass

class ExtraCharactersBeforeOrAfterClosingBraceException(ParseErrorException):
    pass

class LineIsNotSectionNorKeyValueException(ParseErrorException):
    pass
