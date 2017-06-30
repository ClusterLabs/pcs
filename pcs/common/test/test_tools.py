from __future__ import (
    absolute_import,
    division,
    print_function,
)

from pcs.test.tools.pcs_unittest import TestCase
from pcs.common.tools import is_string

class IsString(TestCase):
    def test_recognize_plain_string(self):
        self.assertTrue(is_string(""))

    def test_recognize_unicode_string(self):
        #in python3 this is str type
        self.assertTrue(is_string(u""))

    def test_rcognize_bytes(self):
        #in python3 this is str type
        self.assertTrue(is_string(b""))

    def test_list_of_string_is_not_string(self):
        self.assertFalse(is_string(["a", "b"]))
