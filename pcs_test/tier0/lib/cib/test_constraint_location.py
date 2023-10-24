from unittest import TestCase

from lxml import etree

from pcs.lib.cib.constraint import location


class IsLocationConstraint(TestCase):
    def test_location_constraint_true(self):
        self.assertTrue(
            location.is_location_constraint(etree.Element("rsc_location"))
        )

    def test_location_constraint_false(self):
        self.assertFalse(
            location.is_location_constraint(etree.Element("location"))
        )


class IsLocationRule(TestCase):
    def test_location_constraint_true(self):
        self.assertTrue(
            location.is_location_rule(
                etree.SubElement(etree.Element("rsc_location"), "rule")
            )
        )

    def test_location_constraint_false(self):
        for element in (
            etree.Element("rule"),
            etree.SubElement(etree.Element("rsc_order"), "rule"),
            etree.SubElement(
                etree.SubElement(etree.Element("rsc_location"), "rsc_order"),
                "rule",
            ),
        ):
            with self.subTest(element=element):
                self.assertFalse(location.is_location_rule(element))
