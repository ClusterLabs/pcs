from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.lib.cib.resource import common
from pcs.test.tools.pcs_unittest import TestCase

class DisableMeta(TestCase):
    def test_add_target_role(self):
        self.assertEqual(
            {"a": "b", "target-role": "Stopped"},
            common.disable_meta({"a": "b"})
        )

    def test_modify_target_role(self):
        self.assertEqual(
            {"target-role": "Stopped"},
            common.disable_meta({"target-role": "Stopped"})
        )
