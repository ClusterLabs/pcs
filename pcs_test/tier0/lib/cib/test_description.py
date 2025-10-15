from unittest import TestCase

from lxml import etree

from pcs.common import reports
from pcs.lib.cib import description

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal
from pcs_test.tools.xml import etree_to_str, str_to_etree


class ValidateDescriptionSupport(TestCase):
    def test_supported_element_no_reports(self):
        supported_elements = [
            '<primitive id="A" />',
            '<bundle id="A" />',
            '<clone id="A" />',
            '<group id="A" />',
            '<acl_permission id="A" />',
            '<alert id="A" />',
            '<node id="A" />',
            '<recipient id="A" />',
        ]

        for element_str in supported_elements:
            element = str_to_etree(element_str)
            with self.subTest(element=element_str):
                assert_report_item_list_equal(
                    description.validate_description_support(element), []
                )

    def test_unusported_element_report(self):
        supported_elements = [
            '<tag id="A" />',
            '<rsc_colocation id="A" />',
            '<rsc_resource_set id="A" />',
            '<rule id="A" />',
        ]

        for element_str in supported_elements:
            element = str_to_etree(element_str)
            with self.subTest(element=element_str):
                assert_report_item_list_equal(
                    description.validate_description_support(element),
                    [
                        fixture.error(
                            reports.codes.ID_BELONGS_TO_UNEXPECTED_TYPE,
                            id="A",
                            expected_types=sorted(
                                description.TAG_LIST_SUPPORTS_DESCRIPTION
                            ),
                            current_type=element.tag,
                        )
                    ],
                )


class SetDescription(TestCase):
    def test_add_description(self):
        element = etree.fromstring('<primitive id="A"/>')

        description.set_description(element, "X")

        self.assertEqual(
            etree_to_str(element), '<primitive id="A" description="X"/>\n'
        )

    def test_update_description(self):
        element = etree.fromstring('<primitive id="A" description="X"/>')

        description.set_description(element, "Y")

        self.assertEqual(
            etree_to_str(element), '<primitive id="A" description="Y"/>\n'
        )

    def test_remove_description(self):
        element = etree.fromstring('<primitive id="A" description="X"/>')

        description.set_description(element, "")

        self.assertEqual(etree_to_str(element), '<primitive id="A"/>\n')


class GetDescription(TestCase):
    def test_read_description(self):
        element = etree.fromstring('<primitive id="A" description="X"/>')

        result = description.get_description(element)

        self.assertEqual(result, "X")

    def test_no_description(self):
        element = etree.fromstring('<primitive id="A"/>')

        result = description.get_description(element)

        self.assertEqual(result, "")
