from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import xml.dom.minidom
from lxml import etree


def dom_get_child_elements(element):
    return [
        child for child in element.childNodes
        if child.nodeType == xml.dom.minidom.Node.ELEMENT_NODE
    ]


class XmlManipulation(object):
    @classmethod
    def from_file(cls, file_name):
        return cls(etree.parse(file_name).getroot())

    @classmethod
    def from_str(cls, string):
        return cls(etree.fromstring(string))

    def __init__(self, tree):
        self.tree = tree

    def __append_to_child(self, element, xml_string):
        element.append(etree.fromstring(xml_string))

    def append_to_first_tag_name(self, tag_name, *xml_string_list):
        for xml_string in xml_string_list:
            self.__append_to_child(
                self.tree.find(".//{0}".format(tag_name)), xml_string
            )
        return self

    def __str__(self):
        #etree returns string in bytes: b'xml'
        #python 3 removed .encode() from byte strings
        #run(...) calls subprocess.Popen.communicate which calls encode...
        #so there is bytes to str conversion
        return etree.tostring(self.tree).decode()


def get_xml_manipulation_creator_from_file(file_name):
    return lambda: XmlManipulation.from_file(file_name)

