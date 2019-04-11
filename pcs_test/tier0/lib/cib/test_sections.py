from unittest import TestCase
from lxml import etree

from pcs_test.tools.assertions import(
    assert_xml_equal,
    assert_raise_library_error
)
from pcs_test.tools.xml import etree_to_str

from pcs.common import report_codes
from pcs.lib.cib import sections
from pcs.lib.errors import ReportItemSeverity as severities


class Get(TestCase):
    def setUp(self):
        self.tree = etree.fromstring(
            """
            <cib>
                <configuration>
                    <acls/>
                </configuration>
            </cib>
            """
        )

    @staticmethod
    def assert_element_content(section_element, expected_xml):
        assert_xml_equal(etree_to_str(section_element), expected_xml)

    def test_get_existing_mandatory(self):
        self.assert_element_content(
            sections.get(self.tree, sections.CONFIGURATION),
            """
            <configuration>
                <acls/>
            </configuration>
            """
        )

    def test_get_existing_optinal(self):
        self.assert_element_content(
            sections.get(self.tree, sections.ACLS),
            "<acls/>"
        )

    def test_get_no_existing_optinal(self):
        self.assert_element_content(
            sections.get(self.tree, sections.ALERTS),
            "<alerts/>"
        )
        self.assert_element_content(
            self.tree,
            """
            <cib>
                <configuration>
                    <acls/>
                    <alerts/>
                </configuration>
            </cib>
            """
        )

    def test_raises_on_no_existing_mandatory_section(self):
        assert_raise_library_error(
            lambda: sections.get(self.tree, sections.NODES),
            (
                severities.ERROR,
                report_codes.CIB_CANNOT_FIND_MANDATORY_SECTION,
                {
                    "section": "configuration/nodes",
                }
            ),
        )
