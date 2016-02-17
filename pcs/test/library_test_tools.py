from __future__ import absolute_import
from __future__ import division
from __future__ import print_function
from __future__ import unicode_literals

import xml.dom.minidom
from lxml.doctestcompare import LXMLOutputChecker
from doctest import Example

from errors import LibraryError

class LibraryAssertionMixin(object):
    def __find_report_info(self, report_info_list, report_item):
        for report_info in report_info_list:
            if(
                report_item.severity == report_info[0]
                and
                report_item.code == report_info[1]
                and
                #checks only presence and match of expected in info,
                #extra info is ignored
                all(
                    (k in report_item.info and report_item.info[k]==v)
                    for k,v in report_info[2].iteritems()
                )
            ):
                return report_info
        raise AssertionError(
            'Unexpected report given: {0}'
            .format(repr((
                report_item.severity, report_item.code, repr(report_item.info)
            )))
        )

    def __check_error(self, e, report_info_list):
        for report_item in e.args:
            report_info_list.remove(
                self.__find_report_info(report_info_list, report_item)
            )

        if report_info_list:
            raise AssertionError(
                'In the report from LibraryError was not present: '
                +', '+repr(report_info_list)
            )

    def assert_raise_library_error(self, callableObj, *report_info_list):
        if not report_info_list:
            raise AssertionError(
                'Raising LibraryError expected, but no report item specified.'
                +' Please specify report items, that you expect in LibraryError'
            )

        try:
            callableObj()
            raise AssertionError('LibraryError not raised')
        except LibraryError as e:
            self.__check_error(e, list(report_info_list))

    def assert_xml_equal(self, expected_cib, got_cib=None):
        got_cib = got_cib if got_cib else self.cib
        got_xml = got_cib.dom.toxml()
        expected_xml = expected_cib.dom.toxml()

        checker = LXMLOutputChecker()
        if checker.check_output(expected_xml, got_xml, 0):
            return

        raise AssertionError(checker.output_difference(
            Example("", expected_xml),
            got_xml,
            0
        ))

class XmlManipulation(object):
    def __init__(self, file_name):
        self.dom = xml.dom.minidom.parse(file_name)

    def __append_to_child(self, element, xml_string):
        element.appendChild(
            xml.dom.minidom.parseString(xml_string).firstChild
        )

    def append_to_first_tag_name(self, tag_name, *xml_string_list):
        for xml_string in xml_string_list:
            self.__append_to_child(
                self.dom.getElementsByTagName(tag_name)[0], xml_string
            )
        return self

def get_xml_manipulation_creator(file_name):
    def create_xml_manipulation():
       return XmlManipulation(file_name)
    return create_xml_manipulation
