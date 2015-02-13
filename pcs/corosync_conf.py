class Section(object):

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
            lines = map(lambda x: indent + x if x else x, lines)
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

    def add_attribute(self, name, value):
        self._attr_list.append([name, value])
        return self

    def del_attribute(self, attribute):
        self._attr_list.remove(attribute)
        return self

    def del_attributes_by_name(self, name, value=None):
        for index, attr in enumerate(self._attr_list):
            if attr[0] == name and (value is None or attr[1] == value):
                del self._attr_list[index]
        return self

    def set_attribute(self, name, value):
        existing_attrs = self.get_attributes(name)
        if existing_attrs:
            existing_attrs[0][1] = value
            for attr in existing_attrs[1:]:
                self.del_attribute(attr)
        else:
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
        section._parent = self
        self._section_list.append(section)
        return self

    def del_section(self, section):
        self._section_list.remove(section)
        section._parent = None
        return self

    def __str__(self):
        return self.export()


def parse_string(conf_text):
    root = Section("")
    _parse_section(conf_text.split("\n"), root)
    return root

def _parse_section(lines, section):
    # parser is trying to work the same way as an original corosync parser
    while lines:
        current_line = lines.pop(0).strip()
        if not current_line or current_line[0] == "#":
            continue
        if "{" in current_line:
            section_name, junk = current_line.rsplit("{", 1)
            new_section = Section(section_name.strip())
            section.add_section(new_section)
            _parse_section(lines, new_section)
        elif "}" in current_line:
            if not section.parent:
                raise ParseErrorException("Unexpected closing brace")
            return
        elif ":" in current_line:
            section.add_attribute(
                *map(lambda x: x.strip(), current_line.split(":", 1))
            )
    if section.parent:
        raise ParseErrorException("Missing closing brace")


class CorosyncConfException(Exception):
    pass

class CircularParentshipException(CorosyncConfException):
    pass

class ParseErrorException(CorosyncConfException):
    pass

