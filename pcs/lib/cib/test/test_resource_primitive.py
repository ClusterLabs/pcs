from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

from functools import partial

from lxml import etree

from pcs.lib.cib.resource import primitive
from pcs.test.tools.pcs_unittest import TestCase, mock

@mock.patch("pcs.lib.cib.resource.primitive.append_new_instance_attributes")
@mock.patch("pcs.lib.cib.resource.primitive.append_new_meta_attributes")
@mock.patch("pcs.lib.cib.resource.primitive.create_operations")
class AppendNew(TestCase):
    def setUp(self):
        self.resources_section = etree.fromstring("<resources/>")

        self.instance_attributes = {"a": "b"}
        self.meta_attributes = {"c": "d"}
        self.operation_list = [{"name": "monitoring"}]

        self.run = partial(
            primitive.append_new,
            self.resources_section,
            instance_attributes=self.instance_attributes,
            meta_attributes=self.meta_attributes,
            operation_list=self.operation_list,
        )

    def check_mocks(
        self,
        primitive_element,
        create_operations,
        append_new_meta_attributes,
        append_new_instance_attributes,
    ):
        create_operations.assert_called_once_with(
            primitive_element,
            self.operation_list
        )
        append_new_meta_attributes.assert_called_once_with(
            primitive_element,
            self.meta_attributes
        )
        append_new_instance_attributes.assert_called_once_with(
            primitive_element,
            self.instance_attributes
        )

    def test_append_without_provider(
        self,
        create_operations,
        append_new_meta_attributes,
        append_new_instance_attributes,
    ):
        primitive_element = self.run("RESOURCE_ID", "OCF", None, "DUMMY")
        self.assertEqual(
            primitive_element,
            self.resources_section.find(".//primitive")
        )
        self.assertEqual(primitive_element.attrib["class"], "OCF")
        self.assertEqual(primitive_element.attrib["type"], "DUMMY")
        self.assertFalse(primitive_element.attrib.has_key("provider"))

        self.check_mocks(
            primitive_element,
            create_operations,
            append_new_meta_attributes,
            append_new_instance_attributes,
        )

    def test_append_with_provider(
        self,
        create_operations,
        append_new_meta_attributes,
        append_new_instance_attributes,
    ):
        primitive_element = self.run("RESOURCE_ID", "OCF", "HEARTBEAT", "DUMMY")
        self.assertEqual(
            primitive_element,
            self.resources_section.find(".//primitive")
        )
        self.assertEqual(primitive_element.attrib["class"], "OCF")
        self.assertEqual(primitive_element.attrib["type"], "DUMMY")
        self.assertEqual(primitive_element.attrib["provider"], "HEARTBEAT")

        self.check_mocks(
            primitive_element,
            create_operations,
            append_new_meta_attributes,
            append_new_instance_attributes,
        )
