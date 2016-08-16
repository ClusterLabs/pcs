from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from pcs.test.tools.pcs_unittest import TestCase
from lxml import etree
from pcs.lib.cib.resource import find_by_id

class FindByIdTest(TestCase):
    def test_find_correct_tag(self):
        tree = etree.XML("""
            <root>
                <rsc_set id="A" />
                <primitive id="A" />
            </root>
        """)
        element = find_by_id(tree, "A")
        self.assertEqual(element.tag, "primitive")
