from unittest import mock, TestCase

from pcs.common.reports.constraints import (
    constraint_plain,
    constraint_to_str,
)


class ConstraintTest(TestCase):
    @mock.patch("pcs.common.reports.constraints.constraint_plain")
    def test_can_display_plain_constraint(self, mock_constraint_plain):
        mock_constraint_plain.return_value = "plain"
        self.assertEqual(
            'plain',
            constraint_to_str(
                "rsc_ticket",
                "constraint_in_library_representation"
            )
        )
        mock_constraint_plain.assert_called_once_with(
            "rsc_ticket",
            "constraint_in_library_representation",
            True
        )

    @mock.patch("pcs.common.reports.constraints.constraint_with_sets")
    def test_can_display_constraint_with_set(self, mock_constraint_with_sets):
        mock_constraint_with_sets.return_value = "with_set"
        self.assertEqual(
            'with_set',
            constraint_to_str(
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
    @mock.patch("pcs.common.reports.constraints.colocation_plain")
    def test_choose_right_reporter(self, mock_colocation_plain):
        mock_colocation_plain.return_value = "some constraint formated"
        self.assertEqual(
            "some constraint formated",
            constraint_plain(
                "rsc_colocation",
                "constraint_in_library_representation",
                with_id=True
            )
        )
        mock_colocation_plain.assert_called_once_with(
            "constraint_in_library_representation",
            True
        )
