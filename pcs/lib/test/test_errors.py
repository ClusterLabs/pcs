from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase

from pcs.lib.errors import LibraryEnvError


class LibraryEnvErrorTest(TestCase):
    def test_can_sign_solved_reports(self):
        e = LibraryEnvError("first", "second", "third")
        for report in e.args:
            if report == "second":
                e.sign_processed(report)

        self.assertEqual(["first", "third"], e.unprocessed)
