import os.path
from unittest import TestCase

from lxml import etree

from pcs_test import PROJECT_ROOT


class TestCapabilities(TestCase):
    def test_parsable(self):
        # pylint: disable=no-self-use
        capabilities_dir = os.path.join(PROJECT_ROOT, "pcsd")
        dom = etree.parse(os.path.join(capabilities_dir, "capabilities.xml"))
        etree.RelaxNG(
            file=os.path.join(capabilities_dir, "capabilities.rng")
        ).assertValid(dom)
