from unittest import TestCase

import os.path

from lxml import etree


class TestCapabilities(TestCase):
    def test_parsable(self):
        # pylint: disable=no-self-use
        current_dir = os.path.dirname(os.path.abspath(__file__))
        capabilities_dir = os.path.join(current_dir, "..", "..", "pcsd")
        dom = etree.parse(os.path.join(capabilities_dir, "capabilities.xml"))
        etree.RelaxNG(
            file=os.path.join(capabilities_dir, "capabilities.rng")
        ).assertValid(dom)
