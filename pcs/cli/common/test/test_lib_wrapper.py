from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)
from unittest import TestCase
from pcs.cli.common.lib_wrapper import Library

class LibraryWrapperTest(TestCase):
    def test_raises_for_bad_path(self):
        lib = Library('env')
        self.assertRaises(Exception, lambda:lib.no_valid_library_part)
