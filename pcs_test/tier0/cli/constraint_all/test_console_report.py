from unittest import mock, TestCase

from pcs.cli.constraint_all import console_report
from pcs.common.reports import codes

class ConstraintTest(TestCase):
    @mock.patch("pcs.cli.constraint_all.console_report.constraint_plain")
    def test_can_display_plain_constraint(self, mock_constraint_plain):
        mock_constraint_plain.return_value = "plain"
        self.assertEqual(
            'plain',
            console_report.constraint(
                "rsc_ticket",
                "constraint_in_library_representation"
            )
        )
        mock_constraint_plain.assert_called_once_with(
            "rsc_ticket",
            "constraint_in_library_representation",
            True
        )

    @mock.patch("pcs.cli.constraint_all.console_report.constraint_with_sets")
    def test_can_display_constraint_with_set(self, mock_constraint_with_sets):
        mock_constraint_with_sets.return_value = "with_set"
        self.assertEqual(
            'with_set',
            console_report.constraint(
                "rsc_ticket",
                {"resource_sets": "some_resource_sets", "options": {"a": "b"}},
                with_id=False
            )
        )
        mock_constraint_with_sets.assert_called_once_with(
            {"resource_sets": "some_resource_sets", "options": {"a": "b"}},
            False
        )

class ConstraintPlainTest(TestCase):
    @mock.patch("pcs.cli.constraint_all.console_report.colocation_plain")
    def test_choose_right_reporter(self, mock_colocation_plain):
        mock_colocation_plain.return_value = "some constraint formated"
        self.assertEqual(
            "some constraint formated",
            console_report.constraint_plain(
                "rsc_colocation",
                "constraint_in_library_representation",
                with_id=True
            )
        )
        mock_colocation_plain.assert_called_once_with(
            "constraint_in_library_representation",
            True
        )

class DuplicateConstraintsReportTest(TestCase):
    def setUp(self):
        self.build = console_report.CODE_TO_MESSAGE_BUILDER_MAP[
            codes.DUPLICATE_CONSTRAINTS_EXIST
        ]

    @mock.patch("pcs.cli.constraint_all.console_report.constraint")
    def test_translate_from_report_info(self, mock_constraint):
        mock_constraint.return_value = "constraint info"

        self.assertEqual(
            "\n".join([
                "duplicate constraint already exists force text",
                "  constraint info"
            ]),
            self.build(
                {
                    "constraint_info_list": [{"options": {"a": "b"}}],
                    "constraint_type": "rsc_some"
                },
                force_text=" force text"
            )
        )
        mock_constraint.assert_called_once_with(
            "rsc_some",
            {"options": {"a": "b"}}
        )
