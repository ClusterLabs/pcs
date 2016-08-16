from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.cli.constraint_ticket import console_report

class ConstraintPlainTest(TestCase):
    def test_prepare_report(self):
        self.assertEqual(
            "Master resourceA (id:some_id)",
            console_report.constraint_plain(
                {"options": {
                    "rsc-role": "Master",
                    "rsc": "resourceA",
                    "id": "some_id"
                }},
                with_id=True
            )
        )

    def test_prepare_report_without_role(self):
        self.assertEqual(
            "resourceA (id:some_id)",
            console_report.constraint_plain(
                {"options": {
                    "rsc": "resourceA",
                    "id": "some_id"
                }},
                with_id=True
            )
        )
