from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from lxml import etree

from pcs.lib.cib.resource import clone
from pcs.test.tools.pcs_unittest import TestCase
from pcs.test.tools.assertions import assert_xml_equal

class AppendNewCommon(TestCase):
    def setUp(self):
        self.cib = etree.fromstring("""
            <cib>
                <resources>
                    <primitive/>
                </resources>
            </cib>
        """)
        self.resources = self.cib.find(".//resources")
        self.primitive = self.cib.find(".//primitive")

    def assert_clone_effect(self, options, xml):
        clone.append_new(
            clone.TAG_CLONE,
            self.resources,
            self.primitive,
            options
        )
        assert_xml_equal(etree.tostring(self.cib).decode(), xml)

    def test_add_without_options(self):
        self.assert_clone_effect({}, """
            <cib>
                <resources>
                    <clone id="None-clone">
                        <primitive></primitive>
                    </clone>
                </resources>
            </cib>
        """)

    def test_add_with_options(self):
        self.assert_clone_effect({"a": "b"}, """
            <cib>
                <resources>
                    <clone id="None-clone">
                        <primitive></primitive>
                        <meta_attributes id="None-clone-meta_attributes">
                            <nvpair id="None-clone-meta_attributes-a"
                                name="a" value="b"
                            />
                        </meta_attributes>
                    </clone>
                </resources>
            </cib>
        """)
