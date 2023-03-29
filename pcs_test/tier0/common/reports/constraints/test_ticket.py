from unittest import TestCase

from pcs.common.reports.constraints import ticket


class ConstraintPlainTest(TestCase):
    def test_prepare_report(self):
        self.assertEqual(
            "Master resourceA (id:some_id)",
            ticket.constraint_plain(
                {
                    "options": {
                        "rsc-role": "Master",
                        "rsc": "resourceA",
                        "id": "some_id",
                    }
                },
            ),
        )

    def test_prepare_report_without_role(self):
        self.assertEqual(
            "resourceA (id:some_id)",
            ticket.constraint_plain(
                {"options": {"rsc": "resourceA", "id": "some_id"}}
            ),
        )
