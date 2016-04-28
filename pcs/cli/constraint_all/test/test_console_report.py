from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from pcs.test.tools.pcs_mock import mock
from pcs.cli.constraint_all import console_report

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

class DuplicitConstraintsReportTest(TestCase):
    @mock.patch("pcs.cli.constraint_all.console_report.constraint")
    def test_translate_from_report_item(self, mock_constraint):
        report_item = mock.MagicMock()
        report_item.info = {
            "constraint_info_list": [{"options": {"a": "b"}}],
            "type": "rsc_some"
        }
        mock_constraint.return_value = "constraint info"

        self.assertEqual(
            "\n".join([
                "duplicate constraint already exists, use --force to override",
                "  constraint info"
            ]),
            console_report.duplicit_constraints_report(report_item)

        )
