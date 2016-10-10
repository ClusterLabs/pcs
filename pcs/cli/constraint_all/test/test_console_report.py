from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools.pcs_unittest import mock
from pcs.cli.constraint_all import console_report
from pcs.common import report_codes as codes

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
                "duplicate constraint already exists{force}",
                "  constraint info"
            ]),
            self.build({
                "constraint_info_list": [{"options": {"a": "b"}}],
                "constraint_type": "rsc_some"
            })
        )

class ResourceForConstraintIsMultiinstanceTest(TestCase):
    def setUp(self):
        self.build = console_report.CODE_TO_MESSAGE_BUILDER_MAP[
            codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE
        ]

    def test_build_message_for_master(self):
        self.assertEqual(
            "RESOURCE_PRIMITIVE is a master/slave resource, you should use the"
                " master id: RESOURCE_MASTER when adding constraints"
            ,
            self.build({
                "resource_id": "RESOURCE_PRIMITIVE",
                "parent_type": "master",
                "parent_id": "RESOURCE_MASTER"
            })
        )

    def test_build_message_for_clone(self):
        self.assertEqual(
            "RESOURCE_PRIMITIVE is a clone resource, you should use the"
                " clone id: RESOURCE_CLONE when adding constraints"
            ,
            self.build({
                "resource_id": "RESOURCE_PRIMITIVE",
                "parent_type": "clone",
                "parent_id": "RESOURCE_CLONE"
            })
        )
