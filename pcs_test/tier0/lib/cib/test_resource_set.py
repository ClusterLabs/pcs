from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common import (
    const,
    reports,
)
from pcs.lib.cib.constraint import resource_set

from pcs_test.tools import fixture
from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_xml_equal,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor


class PrepareSetTest(TestCase):
    def setUp(self):
        self.report_processor = MockLibraryReportProcessor(debug=False)

    def test_return_corrected_resource_set(self):
        find_valid_id = mock.Mock()
        find_valid_id.side_effect = lambda id: {"A": "AA", "B": "BB"}[id]
        self.assertEqual(
            {"ids": ["AA", "BB"], "options": {"sequential": "true"}},
            resource_set.prepare_set(
                find_valid_id,
                {"ids": ["A", "B"], "options": {"sequential": "true"}},
                self.report_processor,
            ),
        )
        self.report_processor.assert_reports([])

    def test_refuse_invalid_attribute_name(self):
        assert_raise_library_error(
            lambda: resource_set.prepare_set(
                mock.Mock(),
                {"ids": ["A", "B"], "options": {"invalid_name": "true"}},
                self.report_processor,
            ),
        )
        self.report_processor.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTIONS,
                    option_names=["invalid_name"],
                    option_type="set",
                    allowed=["action", "require-all", "role", "sequential"],
                    allowed_patterns=[],
                ),
            ]
        )

    def test_refuse_invalid_attribute_value(self):
        assert_raise_library_error(
            lambda: resource_set.prepare_set(
                mock.Mock(),
                {"ids": ["A", "B"], "options": {"role": "invalid"}},
                self.report_processor,
            ),
        )
        self.report_processor.assert_reports(
            [
                fixture.error(
                    reports.codes.INVALID_OPTION_VALUE,
                    option_name="role",
                    allowed_values=const.PCMK_ROLES,
                    option_value="invalid",
                    cannot_be_empty=False,
                    forbidden_characters=None,
                ),
            ]
        )


class CreateTest(TestCase):
    def test_resource_set_to_parent(self):
        # pylint: disable=no-self-use
        constraint_element = etree.Element("constraint")
        resource_set.create(
            constraint_element,
            {"ids": ["A", "B"], "options": {"sequential": "true"}},
        )
        assert_xml_equal(
            etree.tostring(constraint_element).decode(),
            """
            <constraint>
              <resource_set id="constraint_set_set" sequential="true">
                <resource_ref id="A"></resource_ref>
                <resource_ref id="B"></resource_ref>
              </resource_set>
            </constraint>
        """,
        )


class GetResourceIdListTest(TestCase):
    def test_returns_id_list_from_element(self):
        element = etree.Element("resource_set")
        for _id in ("A", "B"):
            etree.SubElement(element, "resource_ref").attrib["id"] = _id

        self.assertEqual(
            ["A", "B"], resource_set.get_resource_id_set_list(element)
        )
