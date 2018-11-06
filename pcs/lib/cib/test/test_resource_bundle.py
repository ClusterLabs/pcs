from unittest import TestCase
from lxml import etree

from pcs.lib.cib.resource import bundle

# pcs.lib.cib.resource.bundle is covered by:
# - pcs.lib.commands.test.resource.test_bundle_create
# - pcs.lib.commands.test.resource.test_bundle_update
# - pcs.lib.commands.test.resource.test_resource_create

class IsBundle(TestCase):
    def test_is_bundle(self):
        self.assertTrue(bundle.is_bundle(etree.fromstring("<bundle/>")))
        self.assertFalse(bundle.is_bundle(etree.fromstring("<clone/>")))
        self.assertFalse(bundle.is_bundle(etree.fromstring("<group/>")))


class GetInnerResource(TestCase):
    def assert_inner_resource(self, resource_id, xml):
        self.assertEqual(
            resource_id,
            bundle.get_inner_resource(etree.fromstring(xml)).get("id", "")
        )

    def test_primitive(self):
        self.assert_inner_resource(
            "A",
            """
                <bundle id="B">
                    <meta_attributes />
                    <primitive id="A" />
                    <meta_attributes />
                </bundle>
            """
        )
