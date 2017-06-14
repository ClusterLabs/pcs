from __future__ import (
    absolute_import,
    division,
    print_function,
)

from lxml import etree
from lxml.doctestcompare import LXMLOutputChecker

from pcs.test.tools.xml import etree_to_str


def replace_element(element_xpath, new_content):
    """
    Return function that replace element (defined by element_xpath) in the
    cib_tree with new_content.

    string element_xpath -- its destination must be one element: replacement
        is applied only on the first occurence
    """
    def replace(cib_tree):
        element_to_replace = cib_tree.find(element_xpath)
        if element_to_replace is None:
            raise AssertionError(
                "Cannot find '{0}' in given cib:\n{1}".format(
                    element_xpath,
                    etree_to_str(cib_tree)
                )
            )
        element_to_replace_xml = etree_to_str(element_to_replace)
        parent = element_to_replace.getparent()

        try:
            new_element = etree.fromstring(new_content)
        except etree.XMLSyntaxError:
            raise AssertionError(
                "Cannot put to the cib non-xml fragment:\n'{0}'"
                .format(new_content)
            )

        check = LXMLOutputChecker().check_output
        for child in parent:
            if check(element_to_replace_xml, etree_to_str(child), 0):
                index = list(parent).index(child)
                parent.remove(child)
                parent.insert(index, new_element)
                return

    return replace
