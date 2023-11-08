from unittest import TestCase

from lxml import etree

from pcs.lib.cib.constraint import all as constraint_all


class IsConstraint(TestCase):
    def test_is_constraint_true(self):
        for element in (
            etree.Element("rsc_colocation"),
            etree.Element("rsc_location"),
            etree.Element("rsc_order"),
            etree.Element("rsc_ticket"),
        ):
            with self.subTest(element=element):
                self.assertTrue(constraint_all.is_constraint(element))

    def test_is_constraint_false(self):
        self.assertFalse(constraint_all.is_constraint(etree.Element("element")))
