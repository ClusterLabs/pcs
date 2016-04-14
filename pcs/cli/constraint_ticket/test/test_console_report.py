from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from unittest import TestCase
from pcs.cli.constraint_ticket import console_report

class ConstraintPlainTest(TestCase):
    def test_prepare_report(self):
        self.assertEqual(
            "Master resourceA (id:some_id)",
            console_report.constraint_plain(
                {"attrib": {
                    "rsc-role": "Master",
                    "rsc": "resourceA",
                    "id": "some_id"
                }},
                with_id=True
            )
        )
