from unittest import (
    TestCase,
    mock,
)

from lxml import etree

from pcs.common.reports import ReportItemSeverity as severities
from pcs.common.reports import codes as report_codes
from pcs.lib.cib.constraint import constraint

from pcs_test.tools.assertions import (
    assert_raise_library_error,
    assert_report_item_list_equal,
    assert_xml_equal,
)
from pcs_test.tools.custom_mock import MockLibraryReportProcessor


class PrepareOptionsTest(TestCase):
    def test_refuse_unknown_option(self):
        # pylint: disable=no-self-use
        assert_raise_library_error(
            lambda: constraint.prepare_options(
                ("a",), {"b": "c"}, mock.MagicMock(), mock.MagicMock()
            ),
            (
                severities.ERROR,
                report_codes.INVALID_OPTIONS,
                {
                    "option_names": ["b"],
                    "option_type": None,
                    "allowed": ["a", "id"],
                    "allowed_patterns": [],
                },
            ),
        )

    def test_complete_id(self):
        mock_create_id = mock.MagicMock()
        mock_create_id.return_value = "new-id"
        self.assertEqual(
            {"id": "new-id"},
            constraint.prepare_options(
                ("a",), {}, mock_create_id, mock.MagicMock()
            ),
        )

    def test_has_no_side_effect_on_input_options(self):
        mock_create_id = mock.MagicMock()
        mock_create_id.return_value = "new-id"
        options = {"a": "b"}
        self.assertEqual(
            {"id": "new-id", "a": "b"},
            constraint.prepare_options(
                ("a",), options, mock_create_id, mock.MagicMock()
            ),
        )
        self.assertEqual({"a": "b"}, options)

    def test_refuse_invalid_id(self):
        class SomeException(Exception):
            pass

        mock_validate_id = mock.MagicMock()
        mock_validate_id.side_effect = SomeException()
        self.assertRaises(
            SomeException,
            lambda: constraint.prepare_options(
                ("a",), {"id": "invalid"}, mock.MagicMock(), mock_validate_id
            ),
        )
        mock_validate_id.assert_called_once_with("invalid")


class CreateIdTest(TestCase):
    @mock.patch("pcs.lib.cib.constraint.constraint.find_unique_id")
    def test_create_id_from_resource_set_list(self, mock_find_id):
        resource_set_list = [{"ids": ["A", "B"]}, {"ids": ["C"]}]
        mock_find_id.return_value = "some_id"
        self.assertEqual(
            "some_id",
            constraint.create_id("cib", "PREFIX", resource_set_list),
        )
        mock_find_id.assert_called_once_with("cib", "PREFIX_set_AABBCC")


def fixture_constraint_section(return_value):
    constraint_section = mock.MagicMock()
    constraint_section.xpath = mock.MagicMock()
    constraint_section.xpath.return_value = return_value
    return constraint_section


class CheckIsWithoutDuplicationTest(TestCase):
    def test_raises_when_duplicate_element_found(self):
        # pylint: disable=no-self-use
        element = mock.MagicMock()
        element.tag = "constraint_type"

        report_processor = MockLibraryReportProcessor()
        assert_raise_library_error(
            lambda: constraint.check_is_without_duplication(
                report_processor,
                fixture_constraint_section(
                    [etree.Element("tag", {"id": "duplicate_element"})]
                ),
                element,
                are_duplicate=lambda e1, e2: True,
            )
        )
        assert_report_item_list_equal(
            report_processor.report_item_list,
            [
                (
                    severities.ERROR,
                    report_codes.DUPLICATE_CONSTRAINTS_EXIST,
                    {
                        "constraint_ids": ["duplicate_element"],
                    },
                    report_codes.FORCE,
                ),
            ],
        )

    def test_success_when_no_duplication_found(self):
        # pylint: disable=no-self-use
        element = mock.MagicMock()
        element.tag = "constraint_type"
        # no exception raised
        report_processor = MockLibraryReportProcessor()
        constraint.check_is_without_duplication(
            report_processor,
            fixture_constraint_section([]),
            element,
            are_duplicate=lambda e1, e2: True,
        )

    def test_report_when_duplication_allowed(self):
        # pylint: disable=no-self-use
        element = mock.MagicMock()
        element.tag = "constraint_type"

        report_processor = MockLibraryReportProcessor()
        constraint.check_is_without_duplication(
            report_processor,
            fixture_constraint_section(
                [etree.Element("tag", {"id": "duplicate_element"})]
            ),
            element,
            are_duplicate=lambda e1, e2: True,
            duplication_allowed=True,
        )
        assert_report_item_list_equal(
            report_processor.report_item_list,
            [
                (
                    severities.WARNING,
                    report_codes.DUPLICATE_CONSTRAINTS_EXIST,
                    {
                        "constraint_ids": ["duplicate_element"],
                    },
                ),
            ],
        )


class CreateWithSetTest(TestCase):
    def test_put_new_constraint_to_constraint_section(self):
        # pylint: disable=no-self-use
        constraint_section = etree.Element("constraints")
        constraint.create_with_set(
            constraint_section,
            "ticket",
            {"a": "b"},
            [{"ids": ["A", "B"], "options": {"c": "d"}}],
        )
        assert_xml_equal(
            etree.tostring(constraint_section).decode(),
            """
            <constraints>
                <ticket a="b">
                    <resource_set c="d" id="constraint_set_set">
                        <resource_ref id="A"/>
                        <resource_ref id="B"/>
                    </resource_set>
                </ticket>
            </constraints>
        """,
        )

    def test_refuse_empty_resource_set_list(self):
        # pylint: disable=no-self-use
        constraint_section = etree.Element("constraints")
        assert_raise_library_error(
            lambda: constraint.create_with_set(
                constraint_section, "ticket", {"a": "b"}, []
            ),
            (severities.ERROR, report_codes.EMPTY_RESOURCE_SET_LIST, {}),
        )
