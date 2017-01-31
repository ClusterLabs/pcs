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
            common.disable_meta({"target-role": "Started"})
        )

class AreMetaDisabled(TestCase):
    def test_detect_is_disabled(self):
        self.assertTrue(common.are_meta_disabled({"target-role": "Stopped"}))
        self.assertTrue(common.are_meta_disabled({"target-role": "stopped"}))

    def test_detect_is_not_disabled(self):
        self.assertFalse(common.are_meta_disabled({}))
        self.assertFalse(common.are_meta_disabled({"target-role": "any"}))

class IsCloneDeactivatedByMeta(TestCase):
    def assert_is_disabled(self, meta_attributes):
        self.assertTrue(common.is_clone_deactivated_by_meta(meta_attributes))

    def assert_is_not_disabled(self, meta_attributes):
        self.assertFalse(common.is_clone_deactivated_by_meta(meta_attributes))

    def test_detect_is_disabled(self):
        self.assert_is_disabled({"target-role": "Stopped"})
        self.assert_is_disabled({"target-role": "stopped"})
        self.assert_is_disabled({"clone-max": "0"})
        self.assert_is_disabled({"clone-max": "00"})
        self.assert_is_disabled({"clone-max": 0})
        self.assert_is_disabled({"clone-node-max": "0"})
        self.assert_is_disabled({"clone-node-max": "abc1"})

    def test_detect_is_not_disabled(self):
        self.assert_is_not_disabled({})
        self.assert_is_not_disabled({"target-role": "any"})
        self.assert_is_not_disabled({"clone-max": "1"})
        self.assert_is_not_disabled({"clone-max": "01"})
        self.assert_is_not_disabled({"clone-max": 1})
        self.assert_is_not_disabled({"clone-node-max": "1"})
        self.assert_is_not_disabled({"clone-node-max": 1})
        self.assert_is_not_disabled({"clone-node-max": "1abc"})
        self.assert_is_not_disabled({"clone-node-max": "1.1"})
