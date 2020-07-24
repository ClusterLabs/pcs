# pylint: disable=too-many-lines
from io import StringIO
import sys
from time import sleep
from unittest import mock, TestCase
import xml.dom.minidom
import xml.etree.ElementTree as ET

from pcs_test.tools.xml import dom_get_child_elements
from pcs_test.tools.misc import get_test_resource as rc

from pcs import utils

# pylint: disable=line-too-long
# pylint: disable=invalid-name

cib_with_nodes = rc("cib-empty-withnodes.xml")
empty_cib = rc("cib-empty.xml")

TestCase.maxDiff = None


class UtilsTest(TestCase):
    # pylint: disable=too-many-public-methods
    @staticmethod
    def get_cib_empty():
        return xml.dom.minidom.parse(empty_cib)

    @staticmethod
    def get_cib_with_nodes_minidom():
        return xml.dom.minidom.parse(cib_with_nodes)

    def get_cib_resources(self):
        cib_dom = self.get_cib_empty()
        new_resources = xml.dom.minidom.parseString(
            """
            <resources>
                  <primitive id="myResource"
                        class="ocf" provider="heartbeat" type="Dummy">
                  </primitive>
                  <clone id="myClone">
                      <primitive id="myClonedResource"
                          class="ocf" provider="heartbeat" type="Dummy">
                      </primitive>
                  </clone>
                  <clone id="myUniqueClone">
                      <primitive id="myUniqueClonedResource"
                          class="ocf" provider="heartbeat" type="Dummy">
                      </primitive>
                      <meta-attributes>
                        <nvpair name="globally-unique" value="true" />
                      </meta-attributes>
                  </clone>
                  <main id="myMain">
                      <primitive id="myMainedResource"
                            class="ocf" provider="heartbeat" type="Dummy">
                      </primitive>
                  </main>
                  <group id="myGroup">
                      <primitive id="myGroupedResource"
                            class="ocf" provider="heartbeat" type="Dummy">
                      </primitive>
                  </group>
                  <clone id="myGroupClone">
                      <group id="myClonedGroup">
                          <primitive id="myClonedGroupedResource"
                                class="ocf" provider="heartbeat" type="Dummy">
                          </primitive>
                      </group>
                  </clone>
                  <main id="myGroupMain">
                      <group id="myMainedGroup">
                          <primitive id="myMainedGroupedResource"
                                class="ocf" provider="heartbeat" type="Dummy">
                          </primitive>
                      </group>
                  </main>
                  <bundle id="myBundle">
                      <primitive id="myBundledResource"
                          class="ocf" provider="heartbeat" type="Dummy" />
                  </bundle>
                  <bundle id="myEmptyBundle"/>
            </resources>
        """
        ).documentElement
        resources = cib_dom.getElementsByTagName("resources")[0]
        resources.parentNode.replaceChild(new_resources, resources)
        return cib_dom

    def testDomGetResources(self):
        # pylint: disable=too-many-statements
        def test_dom_get(method, dom, ok_ids, bad_ids):
            for element_id in ok_ids:
                self.assert_element_id(method(dom, element_id), element_id)
            for element_id in bad_ids:
                self.assertFalse(method(dom, element_id))

        cib_dom = self.get_cib_empty()
        self.assertFalse(utils.dom_get_resource(cib_dom, "myResource"))
        self.assertFalse(
            utils.dom_get_resource_clone(cib_dom, "myClonedResource")
        )
        self.assertFalse(
            utils.dom_get_resource_mainsubordinate(cib_dom, "myMainedResource")
        )
        self.assertFalse(utils.dom_get_group(cib_dom, "myGroup"))
        self.assertFalse(utils.dom_get_group_clone(cib_dom, "myClonedGroup"))
        self.assertFalse(
            utils.dom_get_group_mainsubordinate(cib_dom, "myMainedGroup")
        )
        self.assertFalse(utils.dom_get_clone(cib_dom, "myClone"))
        self.assertFalse(utils.dom_get_main(cib_dom, "myMain"))
        self.assertFalse(utils.dom_get_clone_ms_resource(cib_dom, "myClone"))
        self.assertFalse(utils.dom_get_clone_ms_resource(cib_dom, "myMain"))
        self.assertFalse(
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myClonedResource")
        )
        self.assertFalse(
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myMainedResource"
            )
        )
        self.assertIsNone(utils.dom_get_bundle(cib_dom, "myResource"))
        self.assertIsNone(utils.dom_get_bundle(cib_dom, "notExisting"))
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myBundledResource")
        )

        cib_dom = self.get_cib_resources()
        all_ids = set(
            [
                "none",
                "myResource",
                "myClone",
                "myClonedResource",
                "myUniqueClone",
                "myUniqueClonedResource",
                "myMain",
                "myMainedResource",
                "myGroup",
                "myGroupedResource",
                "myGroupClone",
                "myClonedGroup",
                "myClonedGroupedResource",
                "myGroupMain",
                "myMainedGroup",
                "myMainedGroupedResource",
                "myBundledResource",
                "myBundle",
                "myEmptyBundle",
            ]
        )

        resource_ids = set(
            [
                "myResource",
                "myClonedResource",
                "myUniqueClonedResource",
                "myGroupedResource",
                "myMainedResource",
                "myClonedGroupedResource",
                "myMainedGroupedResource",
                "myBundledResource",
            ]
        )
        test_dom_get(
            utils.dom_get_resource,
            cib_dom,
            resource_ids,
            all_ids - resource_ids,
        )

        cloned_ids = set(
            [
                "myClonedResource",
                "myUniqueClonedResource",
                "myClonedGroupedResource",
            ]
        )
        test_dom_get(
            utils.dom_get_resource_clone,
            cib_dom,
            cloned_ids,
            all_ids - cloned_ids,
        )

        mained_ids = set(["myMainedResource", "myMainedGroupedResource"])
        test_dom_get(
            utils.dom_get_resource_mainsubordinate,
            cib_dom,
            mained_ids,
            all_ids - mained_ids,
        )

        group_ids = set(["myGroup", "myClonedGroup", "myMainedGroup"])
        test_dom_get(
            utils.dom_get_group, cib_dom, group_ids, all_ids - group_ids
        )

        cloned_group_ids = set(["myClonedGroup"])
        test_dom_get(
            utils.dom_get_group_clone,
            cib_dom,
            cloned_group_ids,
            all_ids - cloned_group_ids,
        )

        clone_ids = set(["myClone", "myUniqueClone", "myGroupClone"])
        test_dom_get(
            utils.dom_get_clone, cib_dom, clone_ids, all_ids - clone_ids
        )

        mained_group_ids = set(["myMainedGroup"])
        test_dom_get(
            utils.dom_get_group_mainsubordinate,
            cib_dom,
            mained_group_ids,
            all_ids - mained_group_ids,
        )

        main_ids = set(["myMain", "myGroupMain"])
        test_dom_get(
            utils.dom_get_main, cib_dom, main_ids, all_ids - main_ids
        )

        bundle_ids = set(["myBundle", "myEmptyBundle"])
        test_dom_get(
            utils.dom_get_bundle, cib_dom, bundle_ids, all_ids - bundle_ids
        )

        self.assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myClone"),
            "myClonedResource",
        )
        self.assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myGroupClone"),
            "myClonedGroup",
        )
        self.assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myMain"),
            "myMainedResource",
        )
        self.assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myGroupMain"),
            "myMainedGroup",
        )

        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myClonedResource"),
            "myClone",
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myClonedGroup"),
            "myGroupClone",
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myClonedGroupedResource"
            ),
            "myGroupClone",
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myMainedResource"
            ),
            "myMain",
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myMainedGroup"),
            "myGroupMain",
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myMainedGroupedResource"
            ),
            "myGroupMain",
        )
        self.assertEqual(
            None, utils.dom_get_resource_clone_ms_parent(cib_dom, "myResource")
        )
        self.assertEqual(
            None, utils.dom_get_resource_clone_ms_parent(cib_dom, "myGroup")
        )
        self.assertEqual(
            None,
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myGroupedResource"
            ),
        )

        self.assertIsNone(
            utils.dom_get_resource_bundle(
                utils.dom_get_bundle(cib_dom, "myEmptyBundle")
            )
        )
        self.assert_element_id(
            utils.dom_get_resource_bundle(
                utils.dom_get_bundle(cib_dom, "myBundle")
            ),
            "myBundledResource",
            "primitive",
        )

        self.assert_element_id(
            utils.dom_get_resource_bundle_parent(cib_dom, "myBundledResource"),
            "myBundle",
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myResource")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myClone")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myClonedResource")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myMain")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myMainedGroup")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myGroup")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myGroupedResource")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myGroupClone")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(cib_dom, "myClonedGroup")
        )
        self.assertIsNone(
            utils.dom_get_resource_bundle_parent(
                cib_dom, "myClonedGroupedResource"
            )
        )

    def testDomGetResourceRemoteNodeName(self):
        dom = self.get_cib_empty()
        new_resources = xml.dom.minidom.parseString(
            """
            <resources>
                <primitive id="dummy1"
                        class="ocf" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="vm-guest1" provider="heartbeat"
                        type="VirtualDomain">
                    <instance_attributes id="vm-guest1-instance_attributes">
                        <nvpair id="vm-guest1-instance_attributes-hypervisor"
                            name="hypervisor" value="qemu:///system"/>
                        <nvpair id="vm-guest1-instance_attributes-config"
                            name="config" value="/root/guest1.xml"/>
                    </instance_attributes>
                    <meta_attributes id="vm-guest1-meta_attributes">
                        <nvpair id="vm-guest1-meta_attributes-remote-node"
                            name="remote-node" value="guest1"/>
                    </meta_attributes>
                </primitive>
                <primitive id="dummy2"
                        class="ocf" provider="heartbeat" type="Dummy">
                    <instance_attributes id="vm-guest1-meta_attributes">
                        <nvpair id="dummy2-remote-node"
                            name="remote-node" value="guest2"/>
                    </instance_attributes>
                </primitive>
                <primitive id="dummy3"
                        class="ocf" provider="pacemaker" type="remote">
                </primitive>
            </resources>
        """
        ).documentElement
        resources = dom.getElementsByTagName("resources")[0]
        resources.parentNode.replaceChild(new_resources, resources)

        self.assertEqual(
            None,
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "dummy1")
            ),
        )
        self.assertEqual(
            None,
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "dummy2")
            ),
        )
        self.assertEqual(
            "guest1",
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "vm-guest1")
            ),
        )
        self.assertEqual(
            "dummy3",
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "dummy3")
            ),
        )

    def test_dom_get_meta_attr_value(self):
        dom = self.get_cib_empty()
        new_resources = xml.dom.minidom.parseString(
            """
            <resources>
                <primitive id="dummy1"
                        class="ocf" provider="heartbeat" type="Dummy">
                </primitive>
                <primitive class="ocf" id="vm-guest1" provider="heartbeat"
                        type="VirtualDomain">
                    <instance_attributes id="vm-guest1-instance_attributes">
                        <nvpair id="vm-guest1-instance_attributes-hypervisor"
                            name="hypervisor" value="qemu:///system"/>
                        <nvpair id="vm-guest1-instance_attributes-config"
                            name="config" value="/root/guest1.xml"/>
                    </instance_attributes>
                    <meta_attributes id="vm-guest1-meta_attributes">
                        <nvpair id="vm-guest1-meta_attributes-remote-node"
                            name="remote-node" value="guest1"/>
                    </meta_attributes>
                </primitive>
                <primitive id="dummy2"
                        class="ocf" provider="heartbeat" type="Dummy">
                    <instance_attributes id="vm-guest1-meta_attributes">
                        <nvpair id="dummy2-remote-node"
                            name="remote-node" value="guest2"/>
                    </instance_attributes>
                </primitive>
            </resources>
        """
        ).documentElement
        resources = dom.getElementsByTagName("resources")[0]
        resources.parentNode.replaceChild(new_resources, resources)

        self.assertEqual(
            None,
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "dummy1"), "foo"
            ),
        )
        self.assertEqual(
            None,
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "dummy2"), "remote-node"
            ),
        )
        self.assertEqual(
            "guest1",
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "vm-guest1"), "remote-node"
            ),
        )
        self.assertEqual(
            None,
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "vm-guest1"), "foo"
            ),
        )

    def testGetElementWithId(self):
        dom = xml.dom.minidom.parseString(
            """
            <aa>
                <bb id="bb1"/>
                <bb/>
                <bb id="bb2">
                    <cc id="cc1"/>
                </bb>
                <bb id="bb3">
                    <cc id="cc2"/>
                </bb>
            </aa>
        """
        ).documentElement

        self.assert_element_id(
            utils.dom_get_element_with_id(dom, "bb", "bb1"), "bb1"
        )
        self.assert_element_id(
            utils.dom_get_element_with_id(dom, "bb", "bb2"), "bb2"
        )
        self.assert_element_id(
            utils.dom_get_element_with_id(dom, "cc", "cc1"), "cc1"
        )
        self.assert_element_id(
            utils.dom_get_element_with_id(
                utils.dom_get_element_with_id(dom, "bb", "bb2"), "cc", "cc1"
            ),
            "cc1",
        )
        self.assertEqual(None, utils.dom_get_element_with_id(dom, "dd", "bb1"))
        self.assertEqual(None, utils.dom_get_element_with_id(dom, "bb", "bb4"))
        self.assertEqual(None, utils.dom_get_element_with_id(dom, "bb", "cc1"))
        self.assertEqual(
            None,
            utils.dom_get_element_with_id(
                utils.dom_get_element_with_id(dom, "bb", "bb2"), "cc", "cc2"
            ),
        )

    def test_dom_get_parent_by_tag_name(self):
        dom = xml.dom.minidom.parseString(
            """
            <aa id="aa1">
                <bb id="bb1"/>
                <bb id="bb2">
                    <cc id="cc1"/>
                </bb>
                <bb id="bb3">
                    <cc id="cc2"/>
                </bb>
                <dd id="dd1" />
            </aa>
        """
        ).documentElement
        bb1 = utils.dom_get_element_with_id(dom, "bb", "bb1")
        cc1 = utils.dom_get_element_with_id(dom, "cc", "cc1")

        self.assert_element_id(
            utils.dom_get_parent_by_tag_names(bb1, ["aa"]), "aa1"
        )
        self.assert_element_id(
            utils.dom_get_parent_by_tag_names(cc1, ["aa"]), "aa1"
        )
        self.assert_element_id(
            utils.dom_get_parent_by_tag_names(cc1, ["bb"]), "bb2"
        )

        self.assertEqual(None, utils.dom_get_parent_by_tag_names(bb1, ["cc"]))
        self.assertEqual(None, utils.dom_get_parent_by_tag_names(cc1, ["dd"]))
        self.assertEqual(None, utils.dom_get_parent_by_tag_names(cc1, ["ee"]))

    def testValidateConstraintResource(self):
        dom = self.get_cib_resources()
        self.assertEqual(
            (True, "", "myClone"),
            utils.validate_constraint_resource(dom, "myClone"),
        )
        self.assertEqual(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myGroupClone"),
        )
        self.assertEqual(
            (True, "", "myMain"),
            utils.validate_constraint_resource(dom, "myMain"),
        )
        self.assertEqual(
            (True, "", "myGroupMain"),
            utils.validate_constraint_resource(dom, "myGroupMain"),
        )
        self.assertEqual(
            (True, "", "myBundle"),
            utils.validate_constraint_resource(dom, "myBundle"),
        )
        self.assertEqual(
            (True, "", "myEmptyBundle"),
            utils.validate_constraint_resource(dom, "myEmptyBundle"),
        )
        self.assertEqual(
            (True, "", "myResource"),
            utils.validate_constraint_resource(dom, "myResource"),
        )
        self.assertEqual(
            (True, "", "myGroup"),
            utils.validate_constraint_resource(dom, "myGroup"),
        )
        self.assertEqual(
            (True, "", "myGroupedResource"),
            utils.validate_constraint_resource(dom, "myGroupedResource"),
        )

        self.assertEqual(
            (False, "Resource 'myNonexistent' does not exist", None),
            utils.validate_constraint_resource(dom, "myNonexistent"),
        )

        message = (
            "%s is a clone resource, you should use the clone id: "
            "%s when adding constraints. Use --force to override."
        )
        self.assertEqual(
            (False, message % ("myClonedResource", "myClone"), "myClone"),
            utils.validate_constraint_resource(dom, "myClonedResource"),
        )
        self.assertEqual(
            (
                False,
                message % ("myClonedGroup", "myGroupClone"),
                "myGroupClone",
            ),
            utils.validate_constraint_resource(dom, "myClonedGroup"),
        )
        self.assertEqual(
            (
                False,
                message % ("myClonedGroupedResource", "myGroupClone"),
                "myGroupClone",
            ),
            utils.validate_constraint_resource(dom, "myClonedGroupedResource"),
        )

        message = (
            "%s is a clone resource, you should use the clone id: "
            "%s when adding constraints. Use --force to override."
        )
        self.assertEqual(
            (False, message % ("myMainedResource", "myMain"), "myMain"),
            utils.validate_constraint_resource(dom, "myMainedResource"),
        )
        self.assertEqual(
            (
                False,
                message % ("myMainedGroup", "myGroupMain"),
                "myGroupMain",
            ),
            utils.validate_constraint_resource(dom, "myMainedGroup"),
        )
        self.assertEqual(
            (
                False,
                message % ("myMainedGroupedResource", "myGroupMain"),
                "myGroupMain",
            ),
            utils.validate_constraint_resource(
                dom, "myMainedGroupedResource"
            ),
        )

        message = (
            "%s is a bundle resource, you should use the bundle id: "
            "%s when adding constraints. Use --force to override."
        )
        self.assertEqual(
            (False, message % ("myBundledResource", "myBundle"), "myBundle"),
            utils.validate_constraint_resource(dom, "myBundledResource"),
        )

        utils.pcs_options["--force"] = True
        self.assertEqual(
            (True, "", "myClone"),
            utils.validate_constraint_resource(dom, "myClonedResource"),
        )
        self.assertEqual(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myClonedGroup"),
        )
        self.assertEqual(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myClonedGroupedResource"),
        )
        self.assertEqual(
            (True, "", "myMain"),
            utils.validate_constraint_resource(dom, "myMainedResource"),
        )
        self.assertEqual(
            (True, "", "myGroupMain"),
            utils.validate_constraint_resource(dom, "myMainedGroup"),
        )
        self.assertEqual(
            (True, "", "myGroupMain"),
            utils.validate_constraint_resource(
                dom, "myMainedGroupedResource"
            ),
        )
        self.assertEqual(
            (True, "", "myBundle"),
            utils.validate_constraint_resource(dom, "myBundledResource"),
        )

    def testValidateXmlId(self):
        self.assertEqual((True, ""), utils.validate_xml_id("dummy"))
        self.assertEqual((True, ""), utils.validate_xml_id("DUMMY"))
        self.assertEqual((True, ""), utils.validate_xml_id("dUmMy"))
        self.assertEqual((True, ""), utils.validate_xml_id("dummy0"))
        self.assertEqual((True, ""), utils.validate_xml_id("dum0my"))
        self.assertEqual((True, ""), utils.validate_xml_id("dummy-"))
        self.assertEqual((True, ""), utils.validate_xml_id("dum-my"))
        self.assertEqual((True, ""), utils.validate_xml_id("dummy."))
        self.assertEqual((True, ""), utils.validate_xml_id("dum.my"))
        self.assertEqual((True, ""), utils.validate_xml_id("_dummy"))
        self.assertEqual((True, ""), utils.validate_xml_id("dummy_"))
        self.assertEqual((True, ""), utils.validate_xml_id("dum_my"))

        self.assertEqual(
            (False, "test id cannot be empty"),
            utils.validate_xml_id("", "test id"),
        )

        msg = "invalid test id '%s', '%s' is not a valid first character for a test id"
        self.assertEqual(
            (False, msg % ("0", "0")), utils.validate_xml_id("0", "test id")
        )
        self.assertEqual(
            (False, msg % ("-", "-")), utils.validate_xml_id("-", "test id")
        )
        self.assertEqual(
            (False, msg % (".", ".")), utils.validate_xml_id(".", "test id")
        )
        self.assertEqual(
            (False, msg % (":", ":")), utils.validate_xml_id(":", "test id")
        )
        self.assertEqual(
            (False, msg % ("0dummy", "0")),
            utils.validate_xml_id("0dummy", "test id"),
        )
        self.assertEqual(
            (False, msg % ("-dummy", "-")),
            utils.validate_xml_id("-dummy", "test id"),
        )
        self.assertEqual(
            (False, msg % (".dummy", ".")),
            utils.validate_xml_id(".dummy", "test id"),
        )
        self.assertEqual(
            (False, msg % (":dummy", ":")),
            utils.validate_xml_id(":dummy", "test id"),
        )

        msg = (
            "invalid test id '%s', '%s' is not a valid character for a test id"
        )
        self.assertEqual(
            (False, msg % ("dum:my", ":")),
            utils.validate_xml_id("dum:my", "test id"),
        )
        self.assertEqual(
            (False, msg % ("dummy:", ":")),
            utils.validate_xml_id("dummy:", "test id"),
        )
        self.assertEqual(
            (False, msg % ("dum?my", "?")),
            utils.validate_xml_id("dum?my", "test id"),
        )
        self.assertEqual(
            (False, msg % ("dummy?", "?")),
            utils.validate_xml_id("dummy?", "test id"),
        )

    def testIsIso8601Date(self):
        self.assertTrue(utils.is_iso8601_date("2014-07-03"))
        self.assertTrue(utils.is_iso8601_date("2014-07-03T11:35:14"))
        self.assertTrue(utils.is_iso8601_date("20140703"))
        self.assertTrue(utils.is_iso8601_date("2014-W27-4"))
        self.assertTrue(utils.is_iso8601_date("2014-184"))

        self.assertFalse(utils.is_iso8601_date(""))
        self.assertFalse(utils.is_iso8601_date("foo"))
        self.assertFalse(utils.is_iso8601_date("2014-07-32"))
        self.assertFalse(utils.is_iso8601_date("2014-13-03"))
        self.assertFalse(utils.is_iso8601_date("2014-W27-8"))
        self.assertFalse(utils.is_iso8601_date("2014-367"))

    def test_is_score(self):
        self.assertTrue(utils.is_score("INFINITY"))
        self.assertTrue(utils.is_score("+INFINITY"))
        self.assertTrue(utils.is_score("-INFINITY"))
        self.assertTrue(utils.is_score("0"))
        self.assertTrue(utils.is_score("+0"))
        self.assertTrue(utils.is_score("-0"))
        self.assertTrue(utils.is_score("123"))
        self.assertTrue(utils.is_score("-123"))
        self.assertTrue(utils.is_score("+123"))

        self.assertFalse(utils.is_score(""))
        self.assertFalse(utils.is_score("abc"))
        self.assertFalse(utils.is_score("+abc"))
        self.assertFalse(utils.is_score("-abc"))
        self.assertFalse(utils.is_score("10a"))
        self.assertFalse(utils.is_score("+10a"))
        self.assertFalse(utils.is_score("-10a"))
        self.assertFalse(utils.is_score("a10"))
        self.assertFalse(utils.is_score("+a10"))
        self.assertFalse(utils.is_score("a-10"))
        self.assertFalse(utils.is_score("infinity"))
        self.assertFalse(utils.is_score("+infinity"))
        self.assertFalse(utils.is_score("-infinity"))
        self.assertFalse(utils.is_score("+InFiNiTy"))
        self.assertFalse(utils.is_score("INFINITY10"))
        self.assertFalse(utils.is_score("INFINITY+10"))
        self.assertFalse(utils.is_score("-INFINITY10"))
        self.assertFalse(utils.is_score("+INFINITY+10"))
        self.assertFalse(utils.is_score("10INFINITY"))
        self.assertFalse(utils.is_score("+10+INFINITY"))

    def get_cib_status_lrm(self):
        cib_dom = self.get_cib_empty()
        new_status = xml.dom.minidom.parseString(
            """
<status>
  <node_state id="1" uname="rh70-node1">
    <lrm id="1">
      <lrm_resources>
        <lrm_resource id="dummy" type="Dummy" class="ocf" provider="heartbeat">
          <lrm_rsc_op id="dummy_monitor_30000" operation="monitor" call-id="34"
            rc-code="1" on_node="Xrh70-node1X" exit-reason="test" />
          <lrm_rsc_op id="dummy_stop_0" operation="stop" call-id="32"
            rc-code="0" />
          <lrm_rsc_op id="dummy_start_0" operation="start" call-id="33"
            rc-code="0" />
        </lrm_resource>
      </lrm_resources>
    </lrm>
  </node_state>
  <node_state id="2" uname="rh70-node2">
    <lrm id="2">
      <lrm_resources>
        <lrm_resource id="dummy" type="Dummy" class="ocf" provider="heartbeat">
          <lrm_rsc_op id="dummy_monitor_0" operation="monitor" call-id="5"
            rc-code="1" />
        </lrm_resource>
        <lrm_resource id="dummy1" type="Dummy" class="ocf" provider="heartbeat">
          <lrm_rsc_op id="dummy1_monitor_0" operation="monitor" call-id="3"
            rc-code="0" />
        </lrm_resource>
      </lrm_resources>
    </lrm>
  </node_state>
</status>
        """
        ).documentElement
        status = cib_dom.getElementsByTagName("status")[0]
        status.parentNode.replaceChild(new_status, status)
        return cib_dom

    def test_resource_running_on(self):
        status = xml.dom.minidom.parseString(
            """
<crm_mon>
    <summary />
    <nodes />
    <resources>
        <resource id="myResource" role="Started">
            <node name="rh70-node1" />
        </resource>
        <clone id="myClone">
            <resource id="myClonedResource" role="Started">
                <node name="rh70-node1" />
            </resource>
            <resource id="myClonedResource" role="Started">
                <node name="rh70-node2" />
            </resource>
            <resource id="myClonedResource" role="Started">
                <node name="rh70-node3" />
            </resource>
        </clone>
        <clone id="myMain">
            <resource id="myMainedResource:1" role="Subordinate">
                <node name="rh70-node2" />
            </resource>
            <resource id="myMainedResource" role="Subordinate">
                <node name="rh70-node3" />
            </resource>
            <resource id="myMainedResource" role="Main">
                <node name="rh70-node1" />
            </resource>
        </clone>
        <group id="myGroup">
             <resource id="myGroupedResource" role="Started">
                 <node name="rh70-node2" />
             </resource>
        </group>
        <clone id="myGroupClone">
            <group id="myClonedGroup:0">
                 <resource id="myClonedGroupedResource" role="Started">
                     <node name="rh70-node1" />
                 </resource>
            </group>
            <group id="myClonedGroup:1">
                 <resource id="myClonedGroupedResource" role="Started">
                     <node name="rh70-node2" />
                 </resource>
            </group>
            <group id="myClonedGroup:2">
                 <resource id="myClonedGroupedResource" role="Started">
                     <node name="rh70-node3" />
                 </resource>
            </group>
            <group id="myClonedGroup:3">
                 <resource id="myClonedGroupedResource" role="Started">
                     <node name="rh70-node3" />
                 </resource>
            </group>
        </clone>
        <clone id="myGroupMain">
            <group id="myMainedGroup:0">
                 <resource id="myMainedGroupedResource" role="Subordinate">
                     <node name="rh70-node1" />
                 </resource>
            </group>
            <group id="myMainedGroup:1">
                 <resource id="myMainedGroupedResource" role="Main">
                     <node name="rh70-node2" />
                 </resource>
            </group>
            <group id="myMainedGroup:2">
                 <resource id="myMainedGroupedResource" role="Subordinate">
                     <node name="rh70-node3" />
                 </resource>
            </group>
        </clone>
        <resource id="myStoppedResource" role="Stopped">
        </resource>
    </resources>
</crm_mon>
        """
        ).documentElement

        self.assertEqual(
            utils.resource_running_on("myResource", status),
            {
                "message": "Resource 'myResource' is running on node rh70-node1.",
                "is_running": True,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": ["rh70-node1"],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myClonedResource", status),
            {
                "message": "Resource 'myClonedResource' is running on nodes "
                "rh70-node1, rh70-node2, rh70-node3.",
                "is_running": True,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": ["rh70-node1", "rh70-node2", "rh70-node3"],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myClone", status),
            {
                "message": "Resource 'myClone' is running on nodes "
                "rh70-node1, rh70-node2, rh70-node3.",
                "is_running": True,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": ["rh70-node1", "rh70-node2", "rh70-node3"],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myMainedResource", status),
            {
                "message": "Resource 'myMainedResource' is main on node "
                "rh70-node1; subordinate on nodes rh70-node2, rh70-node3.",
                "is_running": True,
                "nodes_main": ["rh70-node1"],
                "nodes_subordinate": ["rh70-node2", "rh70-node3"],
                "nodes_started": [],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myMain", status),
            {
                "message": "Resource 'myMain' is main on node "
                "rh70-node1; subordinate on nodes rh70-node2, rh70-node3.",
                "is_running": True,
                "nodes_main": ["rh70-node1"],
                "nodes_subordinate": ["rh70-node2", "rh70-node3"],
                "nodes_started": [],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myGroupedResource", status),
            {
                "message": "Resource 'myGroupedResource' is running on node "
                "rh70-node2.",
                "is_running": True,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": ["rh70-node2"],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myGroup", status),
            {
                "message": "Resource 'myGroup' is running on node "
                "rh70-node2.",
                "is_running": True,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": ["rh70-node2"],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myClonedGroupedResource", status),
            {
                "message": "Resource 'myClonedGroupedResource' is running on nodes "
                "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                "is_running": True,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": [
                    "rh70-node1",
                    "rh70-node2",
                    "rh70-node3",
                    "rh70-node3",
                ],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myClonedGroup", status),
            {
                "message": "Resource 'myClonedGroup' is running on nodes "
                "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                "is_running": True,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": [
                    "rh70-node1",
                    "rh70-node2",
                    "rh70-node3",
                    "rh70-node3",
                ],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myGroupClone", status),
            {
                "message": "Resource 'myGroupClone' is running on nodes "
                "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                "is_running": True,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": [
                    "rh70-node1",
                    "rh70-node2",
                    "rh70-node3",
                    "rh70-node3",
                ],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myMainedGroupedResource", status),
            {
                "message": "Resource 'myMainedGroupedResource' is main on node "
                "rh70-node2; subordinate on nodes rh70-node1, rh70-node3.",
                "is_running": True,
                "nodes_main": ["rh70-node2"],
                "nodes_subordinate": ["rh70-node1", "rh70-node3"],
                "nodes_started": [],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myMainedGroup", status),
            {
                "message": "Resource 'myMainedGroup' is main on node "
                "rh70-node2; subordinate on nodes rh70-node1, rh70-node3.",
                "is_running": True,
                "nodes_main": ["rh70-node2"],
                "nodes_subordinate": ["rh70-node1", "rh70-node3"],
                "nodes_started": [],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myGroupMain", status),
            {
                "message": "Resource 'myGroupMain' is main on node "
                "rh70-node2; subordinate on nodes rh70-node1, rh70-node3.",
                "is_running": True,
                "nodes_main": ["rh70-node2"],
                "nodes_subordinate": ["rh70-node1", "rh70-node3"],
                "nodes_started": [],
            },
        )
        self.assertEqual(
            utils.resource_running_on("notMyResource", status),
            {
                "message": "Resource 'notMyResource' is not running on any node",
                "is_running": False,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": [],
            },
        )
        self.assertEqual(
            utils.resource_running_on("myStoppedResource", status),
            {
                "message": "Resource 'myStoppedResource' is not running on any node",
                "is_running": False,
                "nodes_main": [],
                "nodes_subordinate": [],
                "nodes_started": [],
            },
        )

    def test_get_operations_from_transitions(self):
        transitions = xml.dom.minidom.parse(rc("transitions01.xml"))
        self.assertEqual(
            [
                {
                    "id": "dummy",
                    "long_id": "dummy",
                    "operation": "stop",
                    "on_node": "rh7-3",
                },
                {
                    "id": "dummy",
                    "long_id": "dummy",
                    "operation": "start",
                    "on_node": "rh7-2",
                },
                {
                    "id": "d0",
                    "long_id": "d0:1",
                    "operation": "stop",
                    "on_node": "rh7-1",
                },
                {
                    "id": "d0",
                    "long_id": "d0:1",
                    "operation": "start",
                    "on_node": "rh7-2",
                },
                {
                    "id": "state",
                    "long_id": "state:0",
                    "operation": "stop",
                    "on_node": "rh7-3",
                },
                {
                    "id": "state",
                    "long_id": "state:0",
                    "operation": "start",
                    "on_node": "rh7-2",
                },
            ],
            utils.get_operations_from_transitions(transitions),
        )

        transitions = xml.dom.minidom.parse(rc("transitions02.xml"))
        self.assertEqual(
            [
                {
                    "id": "RemoteNode",
                    "long_id": "RemoteNode",
                    "operation": "stop",
                    "on_node": "virt-143",
                },
                {
                    "id": "RemoteNode",
                    "long_id": "RemoteNode",
                    "operation": "migrate_to",
                    "on_node": "virt-143",
                },
                {
                    "id": "RemoteNode",
                    "long_id": "RemoteNode",
                    "operation": "migrate_from",
                    "on_node": "virt-142",
                },
                {
                    "id": "dummy8",
                    "long_id": "dummy8",
                    "operation": "stop",
                    "on_node": "virt-143",
                },
                {
                    "id": "dummy8",
                    "long_id": "dummy8",
                    "operation": "start",
                    "on_node": "virt-142",
                },
            ],
            utils.get_operations_from_transitions(transitions),
        )

    def test_get_resources_location_from_operations(self):
        cib_dom = self.get_cib_resources()

        operations = []
        self.assertEqual(
            {},
            utils.get_resources_location_from_operations(cib_dom, operations),
        )

        operations = [
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "start",
                "on_node": "rh7-1",
            },
        ]
        self.assertEqual(
            {
                "myResource": {
                    "id": "myResource",
                    "id_for_constraint": "myResource",
                    "long_id": "myResource",
                    "start_on_node": "rh7-1",
                },
            },
            utils.get_resources_location_from_operations(cib_dom, operations),
        )

        operations = [
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "start",
                "on_node": "rh7-1",
            },
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "start",
                "on_node": "rh7-2",
            },
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "monitor",
                "on_node": "rh7-3",
            },
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "stop",
                "on_node": "rh7-3",
            },
        ]
        self.assertEqual(
            {
                "myResource": {
                    "id": "myResource",
                    "id_for_constraint": "myResource",
                    "long_id": "myResource",
                    "start_on_node": "rh7-2",
                },
            },
            utils.get_resources_location_from_operations(cib_dom, operations),
        )

        operations = [
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "start",
                "on_node": "rh7-1",
            },
            {
                "id": "myClonedResource",
                "long_id": "myClonedResource:0",
                "operation": "start",
                "on_node": "rh7-1",
            },
            {
                "id": "myClonedResource",
                "long_id": "myClonedResource:0",
                "operation": "start",
                "on_node": "rh7-2",
            },
            {
                "id": "myClonedResource",
                "long_id": "myClonedResource:1",
                "operation": "start",
                "on_node": "rh7-3",
            },
        ]
        self.assertEqual(
            {
                "myResource": {
                    "id": "myResource",
                    "id_for_constraint": "myResource",
                    "long_id": "myResource",
                    "start_on_node": "rh7-1",
                },
                "myClonedResource:0": {
                    "id": "myClonedResource",
                    "id_for_constraint": "myClone",
                    "long_id": "myClonedResource:0",
                    "start_on_node": "rh7-2",
                },
                "myClonedResource:1": {
                    "id": "myClonedResource",
                    "id_for_constraint": "myClone",
                    "long_id": "myClonedResource:1",
                    "start_on_node": "rh7-3",
                },
            },
            utils.get_resources_location_from_operations(cib_dom, operations),
        )

        operations = [
            {
                "id": "myUniqueClonedResource:0",
                "long_id": "myUniqueClonedResource:0",
                "operation": "start",
                "on_node": "rh7-1",
            },
            {
                "id": "myUniqueClonedResource:1",
                "long_id": "myUniqueClonedResource:1",
                "operation": "monitor",
                "on_node": "rh7-2",
            },
            {
                "id": "myUniqueClonedResource:2",
                "long_id": "myUniqueClonedResource:2",
                "operation": "start",
                "on_node": "rh7-3",
            },
        ]
        self.assertEqual(
            {
                "myUniqueClonedResource:0": {
                    "id": "myUniqueClonedResource:0",
                    "id_for_constraint": "myUniqueClone",
                    "long_id": "myUniqueClonedResource:0",
                    "start_on_node": "rh7-1",
                },
                "myUniqueClonedResource:2": {
                    "id": "myUniqueClonedResource:2",
                    "id_for_constraint": "myUniqueClone",
                    "long_id": "myUniqueClonedResource:2",
                    "start_on_node": "rh7-3",
                },
            },
            utils.get_resources_location_from_operations(cib_dom, operations),
        )

        operations = [
            {
                "id": "myMainedGroupedResource",
                "long_id": "myMainedGroupedResource:0",
                "operation": "start",
                "on_node": "rh7-1",
            },
            {
                "id": "myMainedGroupedResource",
                "long_id": "myMainedGroupedResource:1",
                "operation": "demote",
                "on_node": "rh7-2",
            },
            {
                "id": "myMainedGroupedResource",
                "long_id": "myMainedGroupedResource:1",
                "operation": "promote",
                "on_node": "rh7-3",
            },
        ]
        self.assertEqual(
            {
                "myMainedGroupedResource:0": {
                    "id": "myMainedGroupedResource",
                    "id_for_constraint": "myGroupMain",
                    "long_id": "myMainedGroupedResource:0",
                    "start_on_node": "rh7-1",
                },
                "myMainedGroupedResource:1": {
                    "id": "myMainedGroupedResource",
                    "id_for_constraint": "myGroupMain",
                    "long_id": "myMainedGroupedResource:1",
                    "promote_on_node": "rh7-3",
                },
            },
            utils.get_resources_location_from_operations(cib_dom, operations),
        )

        operations = [
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "stop",
                "on_node": "rh7-1",
            },
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "migrate_to",
                "on_node": "rh7-1",
            },
            {
                "id": "myResource",
                "long_id": "myResource",
                "operation": "migrate_from",
                "on_node": "rh7-2",
            },
        ]
        self.assertEqual(
            {
                "myResource": {
                    "id": "myResource",
                    "id_for_constraint": "myResource",
                    "long_id": "myResource",
                    "start_on_node": "rh7-2",
                },
            },
            utils.get_resources_location_from_operations(cib_dom, operations),
        )

    def test_is_int(self):
        self.assertTrue(utils.is_int("-999"))
        self.assertTrue(utils.is_int("-1"))
        self.assertTrue(utils.is_int("0"))
        self.assertTrue(utils.is_int("1"))
        self.assertTrue(utils.is_int("99999"))
        self.assertTrue(utils.is_int(" 99999  "))
        self.assertFalse(utils.is_int("0.0"))
        self.assertFalse(utils.is_int("-1.0"))
        self.assertFalse(utils.is_int("-0.1"))
        self.assertFalse(utils.is_int("0.001"))
        self.assertFalse(utils.is_int("-999999.1"))
        self.assertFalse(utils.is_int("0.0001"))
        self.assertFalse(utils.is_int(""))
        self.assertFalse(utils.is_int("   "))
        self.assertFalse(utils.is_int("A"))
        self.assertFalse(utils.is_int("random 15 47 text  "))

    def test_dom_get_node(self):
        cib = self.get_cib_with_nodes_minidom()
        self.assertIsNone(utils.dom_get_node(cib, "non-existing-node"))
        node = utils.dom_get_node(cib, "rh7-1")
        self.assertEqual(node.getAttribute("uname"), "rh7-1")
        self.assertEqual(node.getAttribute("id"), "1")

    def test_dom_prepare_child_element(self):
        cib = self.get_cib_with_nodes_minidom()
        node = cib.getElementsByTagName("node")[0]
        self.assertEqual(len(dom_get_child_elements(node)), 0)
        child = utils.dom_prepare_child_element(
            node, "utilization", "rh7-1-utilization"
        )
        self.assertEqual(len(dom_get_child_elements(node)), 1)
        self.assertEqual(child, dom_get_child_elements(node)[0])
        self.assertEqual(dom_get_child_elements(node)[0].tagName, "utilization")
        self.assertEqual(
            dom_get_child_elements(node)[0].getAttribute("id"),
            "rh7-1-utilization",
        )
        child2 = utils.dom_prepare_child_element(
            node, "utilization", "rh7-1-utilization"
        )
        self.assertEqual(len(dom_get_child_elements(node)), 1)
        self.assertEqual(child, child2)

    def test_dom_update_nv_pair_add(self):
        nv_set = xml.dom.minidom.parseString("<nvset/>").documentElement
        utils.dom_update_nv_pair(nv_set, "test_name", "test_val", "prefix-")
        self.assertEqual(len(dom_get_child_elements(nv_set)), 1)
        pair = dom_get_child_elements(nv_set)[0]
        self.assertEqual(pair.getAttribute("name"), "test_name")
        self.assertEqual(pair.getAttribute("value"), "test_val")
        self.assertEqual(pair.getAttribute("id"), "prefix-test_name")
        utils.dom_update_nv_pair(nv_set, "another_name", "value", "prefix2-")
        self.assertEqual(len(dom_get_child_elements(nv_set)), 2)
        self.assertEqual(pair, dom_get_child_elements(nv_set)[0])
        pair = dom_get_child_elements(nv_set)[1]
        self.assertEqual(pair.getAttribute("name"), "another_name")
        self.assertEqual(pair.getAttribute("value"), "value")
        self.assertEqual(pair.getAttribute("id"), "prefix2-another_name")

    def test_dom_update_nv_pair_update(self):
        nv_set = xml.dom.minidom.parseString(
            """
        <nv_set>
            <nvpair id="prefix-test_name" name="test_name" value="test_val"/>
            <nvpair id="prefix2-another_name" name="another_name" value="value"/>
        </nv_set>
        """
        ).documentElement
        utils.dom_update_nv_pair(nv_set, "test_name", "new_value")
        self.assertEqual(len(dom_get_child_elements(nv_set)), 2)
        pair1 = dom_get_child_elements(nv_set)[0]
        pair2 = dom_get_child_elements(nv_set)[1]
        self.assertEqual(pair1.getAttribute("name"), "test_name")
        self.assertEqual(pair1.getAttribute("value"), "new_value")
        self.assertEqual(pair1.getAttribute("id"), "prefix-test_name")
        self.assertEqual(pair2.getAttribute("name"), "another_name")
        self.assertEqual(pair2.getAttribute("value"), "value")
        self.assertEqual(pair2.getAttribute("id"), "prefix2-another_name")

    def test_dom_update_nv_pair_remove(self):
        nv_set = xml.dom.minidom.parseString(
            """
        <nv_set>
            <nvpair id="prefix-test_name" name="test_name" value="test_val"/>
            <nvpair id="prefix2-another_name" name="another_name" value="value"/>
        </nv_set>
        """
        ).documentElement
        utils.dom_update_nv_pair(nv_set, "non_existing_name", "")
        self.assertEqual(len(dom_get_child_elements(nv_set)), 2)
        utils.dom_update_nv_pair(nv_set, "another_name", "")
        self.assertEqual(len(dom_get_child_elements(nv_set)), 1)
        pair = dom_get_child_elements(nv_set)[0]
        self.assertEqual(pair.getAttribute("name"), "test_name")
        self.assertEqual(pair.getAttribute("value"), "test_val")
        self.assertEqual(pair.getAttribute("id"), "prefix-test_name")
        utils.dom_update_nv_pair(nv_set, "test_name", "")
        self.assertEqual(len(dom_get_child_elements(nv_set)), 0)

    def test_convert_args_to_tuples(self):
        out = utils.convert_args_to_tuples(
            ["invalid_string", "key=value", "key2=val=ue", "k e y= v a l u e "]
        )
        self.assertEqual(
            out,
            [("key", "value"), ("key2", "val=ue"), ("k e y", " v a l u e ")],
        )

    def test_dom_update_utilization_invalid(self):
        # commands writes to stderr
        # we want clean test output, so we capture it
        tmp_stderr = sys.stderr
        sys.stderr = StringIO()

        el = xml.dom.minidom.parseString(
            """
        <resource id="test_id"/>
        """
        ).documentElement
        self.assertRaises(
            SystemExit,
            utils.dom_update_utilization,
            el,
            {"name": "invalid_val"},
        )

        self.assertRaises(
            SystemExit, utils.dom_update_utilization, el, {"name": "0.01"}
        )

        sys.stderr = tmp_stderr

    def test_dom_update_utilization_add(self):
        el = xml.dom.minidom.parseString(
            """
        <resource id="test_id"/>
        """
        ).documentElement
        utils.dom_update_utilization(
            el, {"name": "", "key": "-1", "keys": "90",}
        )

        self.assertEqual(len(dom_get_child_elements(el)), 1)
        u = dom_get_child_elements(el)[0]
        self.assertEqual(u.tagName, "utilization")
        self.assertEqual(u.getAttribute("id"), "test_id-utilization")
        self.assertEqual(len(dom_get_child_elements(u)), 2)

        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("id"),
            "test_id-utilization-key",
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("name"), "key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("value"), "-1"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("id"),
            "test_id-utilization-keys",
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("name"), "keys"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("value"), "90"
        )

    def test_dom_update_utilization_update_remove(self):
        el = xml.dom.minidom.parseString(
            """
        <resource id="test_id">
            <utilization id="test_id-utilization">
                <nvpair id="test_id-utilization-key" name="key" value="-1"/>
                <nvpair id="test_id-utilization-keys" name="keys" value="90"/>
            </utilization>
        </resource>
        """
        ).documentElement
        utils.dom_update_utilization(el, {"key": "100", "keys": "",})

        u = dom_get_child_elements(el)[0]
        self.assertEqual(len(dom_get_child_elements(u)), 1)
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("id"),
            "test_id-utilization-key",
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("name"), "key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("value"), "100"
        )

    def test_dom_update_meta_attr_add(self):
        el = xml.dom.minidom.parseString(
            """
        <resource id="test_id"/>
        """
        ).documentElement
        utils.dom_update_meta_attr(
            el, [("name", ""), ("key", "test"), ("key2", "val")]
        )

        self.assertEqual(len(dom_get_child_elements(el)), 1)
        u = dom_get_child_elements(el)[0]
        self.assertEqual(u.tagName, "meta_attributes")
        self.assertEqual(u.getAttribute("id"), "test_id-meta_attributes")
        self.assertEqual(len(dom_get_child_elements(u)), 2)

        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("id"),
            "test_id-meta_attributes-key",
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("name"), "key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("value"), "test"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("id"),
            "test_id-meta_attributes-key2",
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("name"), "key2"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("value"), "val"
        )

    def test_dom_update_meta_attr_update_remove(self):
        el = xml.dom.minidom.parseString(
            """
        <resource id="test_id">
            <meta_attributes id="test_id-utilization">
                <nvpair id="test_id-meta_attributes-key" name="key" value="test"/>
                <nvpair id="test_id-meta_attributes-key2" name="key2" value="val"/>
            </meta_attributes>
        </resource>
        """
        ).documentElement
        utils.dom_update_meta_attr(el, [("key", "another_val"), ("key2", "")])

        u = dom_get_child_elements(el)[0]
        self.assertEqual(len(dom_get_child_elements(u)), 1)
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("id"),
            "test_id-meta_attributes-key",
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("name"), "key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("value"), "another_val"
        )

    def test_get_utilization(self):
        el = xml.dom.minidom.parseString(
            """
        <resource id="test_id">
            <utilization id="test_id-utilization">
                <nvpair id="test_id-utilization-key" name="key" value="-1"/>
                <nvpair id="test_id-utilization-keys" name="keys" value="90"/>
            </utilization>
        </resource>
        """
        ).documentElement
        self.assertEqual({"key": "-1", "keys": "90"}, utils.get_utilization(el))

    def test_get_utilization_str(self):
        el = xml.dom.minidom.parseString(
            """
        <resource id="test_id">
            <utilization id="test_id-utilization">
                <nvpair id="test_id-utilization-key" name="key" value="-1"/>
                <nvpair id="test_id-utilization-keys" name="keys" value="90"/>
            </utilization>
        </resource>
        """
        ).documentElement
        self.assertEqual("key=-1 keys=90", utils.get_utilization_str(el))

    def test_get_cluster_property_from_xml_enum(self):
        el = ET.fromstring(
            """
        <parameter name="no-quorum-policy" unique="0">
            <shortdesc lang="en">What to do when the cluster does not have quorum</shortdesc>
            <content type="enum" default="stop"/>
            <longdesc lang="en">What to do when the cluster does not have quorum  Allowed values: stop, freeze, ignore, suicide</longdesc>
        </parameter>
        """
        )
        expected = {
            "name": "no-quorum-policy",
            "shortdesc": "What to do when the cluster does not have quorum",
            "longdesc": "",
            "type": "enum",
            "default": "stop",
            "enum": ["stop", "freeze", "ignore", "suicide"],
        }
        self.assertEqual(expected, utils.get_cluster_property_from_xml(el))

    def test_get_cluster_property_from_xml(self):
        el = ET.fromstring(
            """
        <parameter name="an-integer-property" unique="0">
            <shortdesc lang="en"></shortdesc>
            <content type="integer" default="0"/>
            <longdesc lang="en"></longdesc>
        </parameter>
        """
        )
        expected = {
            "name": "an-integer-property",
            "shortdesc": "",
            "longdesc": "",
            "type": "integer",
            "default": "0",
        }
        self.assertEqual(expected, utils.get_cluster_property_from_xml(el))

    def test_is_valid_cib_value_unknown_type(self):
        # should be always true
        self.assertTrue(utils.is_valid_cib_value("unknown", "test"))
        self.assertTrue(utils.is_valid_cib_value("string", "string value"))

    def test_is_valid_cib_value_integer(self):
        self.assertTrue(utils.is_valid_cib_value("integer", "0"))
        self.assertTrue(utils.is_valid_cib_value("integer", "42"))
        self.assertTrue(utils.is_valid_cib_value("integer", "-90"))
        self.assertTrue(utils.is_valid_cib_value("integer", "+90"))
        self.assertTrue(utils.is_valid_cib_value("integer", "INFINITY"))
        self.assertTrue(utils.is_valid_cib_value("integer", "-INFINITY"))
        self.assertTrue(utils.is_valid_cib_value("integer", "+INFINITY"))
        self.assertFalse(utils.is_valid_cib_value("integer", "0.0"))
        self.assertFalse(utils.is_valid_cib_value("integer", "-10.9"))
        self.assertFalse(utils.is_valid_cib_value("integer", "string"))

    def test_is_valid_cib_value_enum(self):
        self.assertTrue(
            utils.is_valid_cib_value("enum", "this", ["another", "this", "1"])
        )
        self.assertFalse(
            utils.is_valid_cib_value("enum", "this", ["another", "this_not"])
        )
        self.assertFalse(utils.is_valid_cib_value("enum", "this", []))
        self.assertFalse(utils.is_valid_cib_value("enum", "this"))

    def test_is_valid_cib_value_boolean(self):
        self.assertTrue(utils.is_valid_cib_value("boolean", "true"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "TrUe"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "TRUE"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "yes"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "on"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "y"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "Y"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "1"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "false"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "FaLse"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "FALSE"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "off"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "no"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "N"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "n"))
        self.assertTrue(utils.is_valid_cib_value("boolean", "0"))
        self.assertFalse(utils.is_valid_cib_value("boolean", "-1"))
        self.assertFalse(utils.is_valid_cib_value("boolean", "not"))
        self.assertFalse(utils.is_valid_cib_value("boolean", "random_string"))
        self.assertFalse(utils.is_valid_cib_value("boolean", "truth"))

    def test_is_valid_cib_value_time(self):
        self.assertTrue(utils.is_valid_cib_value("time", "10"))
        self.assertTrue(utils.is_valid_cib_value("time", "0"))
        self.assertTrue(utils.is_valid_cib_value("time", "9s"))
        self.assertTrue(utils.is_valid_cib_value("time", "10sec"))
        self.assertTrue(utils.is_valid_cib_value("time", "10min"))
        self.assertTrue(utils.is_valid_cib_value("time", "10m"))
        self.assertTrue(utils.is_valid_cib_value("time", "10h"))
        self.assertTrue(utils.is_valid_cib_value("time", "10hr"))
        self.assertFalse(utils.is_valid_cib_value("time", "5.2"))
        self.assertFalse(utils.is_valid_cib_value("time", "-10"))
        self.assertFalse(utils.is_valid_cib_value("time", "10m 2s"))
        self.assertFalse(utils.is_valid_cib_value("time", "hour"))
        self.assertFalse(utils.is_valid_cib_value("time", "day"))

    def test_validate_cluster_property(self):
        definition = {
            "property-int": {
                "name": "property-int",
                "shortdesc": "int description",
                "longdesc": "long int description",
                "type": "integer",
                "default": "0",
                "source": "pacemaker-schedulerd",
            },
            "property-enum": {
                "name": "property-enum",
                "shortdesc": "What to do when the cluster does not have quorum",
                "longdesc": (
                    "What to do when the cluster does not have quorum  "
                    "Allowed values: stop, freeze, ignore, suicide"
                ),
                "type": "enum",
                "default": "stop",
                "enum": ["stop", "freeze", "ignore", "suicide"],
                "source": "pacemaker-schedulerd",
            },
            "property-bool": {
                "name": "property-bool",
                "shortdesc": "Enable CIB ACL",
                "longdesc": "Enable CIB ACL",
                "type": "boolean",
                "default": "false",
                "source": "cib",
            },
        }
        self.assertTrue(
            utils.is_valid_cluster_property(definition, "property-int", "10")
        )
        self.assertTrue(
            utils.is_valid_cluster_property(definition, "property-int", "-1")
        )
        self.assertTrue(
            utils.is_valid_cluster_property(
                definition, "property-enum", "freeze"
            )
        )
        self.assertTrue(
            utils.is_valid_cluster_property(
                definition, "property-enum", "suicide"
            )
        )
        self.assertTrue(
            utils.is_valid_cluster_property(definition, "property-bool", "true")
        )
        self.assertTrue(
            utils.is_valid_cluster_property(
                definition, "property-bool", "false"
            )
        )
        self.assertTrue(
            utils.is_valid_cluster_property(definition, "property-bool", "on")
        )
        self.assertTrue(
            utils.is_valid_cluster_property(definition, "property-bool", "OFF")
        )
        self.assertFalse(
            utils.is_valid_cluster_property(definition, "property-int", "test")
        )
        self.assertFalse(
            utils.is_valid_cluster_property(definition, "property-int", "1.2")
        )
        self.assertFalse(
            utils.is_valid_cluster_property(
                definition, "property-enum", "invalid"
            )
        )
        self.assertFalse(
            utils.is_valid_cluster_property(definition, "property-bool", "not")
        )
        self.assertRaises(
            utils.UnknownPropertyException,
            utils.is_valid_cluster_property,
            definition,
            "unknown",
            "value",
        )

    def assert_element_id(self, node, node_id, tag=None):
        self.assertTrue(
            isinstance(node, xml.dom.minidom.Element),
            "element with id '%s' not found" % node_id,
        )
        self.assertEqual(node.getAttribute("id"), node_id)
        if tag:
            self.assertEqual(node.tagName, tag)


class RunParallelTest(TestCase):
    @staticmethod
    def fixture_create_worker(log, name, sleepSeconds=0):
        def worker():
            sleep(sleepSeconds)
            log.append(name)

        return worker

    def test_run_all_workers(self):
        log = []
        utils.run_parallel(
            [
                self.fixture_create_worker(log, "first"),
                self.fixture_create_worker(log, "second"),
            ],
            wait_seconds=0.1,
        )

        self.assertEqual(sorted(log), sorted(["first", "second"]))


class NodeActionTaskTest(TestCase):
    def test_can_run_action(self):
        def action(node, arg, kwarg=None):
            return (0, ":".join([node, arg, kwarg]))

        report_list = []

        def report(node, returncode, output):
            report_list.append("|".join([node, str(returncode), output]))

        task = utils.create_task(report, action, "node", "arg", kwarg="kwarg")
        task()

        self.assertEqual(["node|0|node:arg:kwarg"], report_list)


class TouchCibFile(TestCase):
    @mock.patch("pcs.utils.os.path.isfile", mock.Mock(return_value=False))
    @mock.patch(
        "pcs.utils.write_empty_cib",
        mock.Mock(side_effect=EnvironmentError("some message")),
    )
    @mock.patch("pcs.utils.err")
    def test_exception_is_transformed_correctly(self, err):
        # pylint: disable=no-self-use
        filename = "/fake/filename"
        utils.touch_cib_file(filename)
        err.assert_called_once_with(
            "Unable to write to file: '/fake/filename': 'some message'"
        )
