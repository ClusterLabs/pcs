import os
import sys
import unittest
import xml.dom.minidom
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
import utils

class UtilsTest(unittest.TestCase):

    def get_cib_empty(self):
        return xml.dom.minidom.parse("empty.xml")

    def get_cib_resources(self):
        cib_dom = self.get_cib_empty()
        new_resources = xml.dom.minidom.parseString("""
            <resources>
                  <primitive id="myResource"
                        class="ocf" provider="heartbeat" type="Dummy">
                  </primitive>
                  <clone id="myClone">
                      <primitive id="myClonedResource"
                          class="ocf" provider="heartbeat" type="Dummy">
                      </primitive>
                  </clone>
                  <master id="myMaster">
                      <primitive id="myMasteredResource"
                            class="ocf" provider="heartbeat" type="Dummy">
                      </primitive>
                  </master>
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
                  <master id="myGroupMaster">
                      <group id="myMasteredGroup">
                          <primitive id="myMasteredGroupedResource"
                                class="ocf" provider="heartbeat" type="Dummy">
                          </primitive>
                      </group>
                  </master>
            </resources>
        """).documentElement
        resources = cib_dom.getElementsByTagName("resources")[0]
        resources.parentNode.replaceChild(new_resources, resources)
        return cib_dom

    def testDomGetResources(self):
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
            utils.dom_get_resource_masterslave(cib_dom, "myMasteredResource")
        )
        self.assertFalse(utils.dom_get_group(cib_dom, "myGroup"))
        self.assertFalse(utils.dom_get_group_clone(cib_dom, "myClonedGroup"))
        self.assertFalse(
            utils.dom_get_group_masterslave(cib_dom, "myMasteredGroup")
        )
        self.assertFalse(utils.dom_get_clone(cib_dom, "myClone"))
        self.assertFalse(utils.dom_get_master(cib_dom, "myMaster"))
        self.assertFalse(utils.dom_get_clone_ms_resource(cib_dom, "myClone"))
        self.assertFalse(utils.dom_get_clone_ms_resource(cib_dom, "myMaster"))
        self.assertFalse(
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myClonedResource")
        )
        self.assertFalse(
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myMasteredResource")
        )

        cib_dom = self.get_cib_resources()
        all_ids = set([
            "none", "myResource",
            "myClone", "myClonedResource",
            "myMaster", "myMasteredResource",
            "myGroup", "myGroupedResource",
            "myGroupClone", "myClonedGroup", "myClonedGroupedResource",
            "myGroupMaster", "myMasteredGroup", "myMasteredGroupedResource",
        ])

        resource_ids = set([
            "myResource",
            "myClonedResource", "myGroupedResource", "myMasteredResource",
            "myClonedGroupedResource", "myMasteredGroupedResource"
        ])
        test_dom_get(
            utils.dom_get_resource, cib_dom,
            resource_ids, all_ids - resource_ids
        )

        cloned_ids = set(["myClonedResource", "myClonedGroupedResource"])
        test_dom_get(
            utils.dom_get_resource_clone, cib_dom,
            cloned_ids, all_ids - cloned_ids
        )

        mastered_ids = set(["myMasteredResource", "myMasteredGroupedResource"])
        test_dom_get(
            utils.dom_get_resource_masterslave, cib_dom,
            mastered_ids, all_ids - mastered_ids
        )

        group_ids = set(["myGroup", "myClonedGroup", "myMasteredGroup"])
        test_dom_get(
            utils.dom_get_group, cib_dom, group_ids, all_ids - group_ids
        )

        cloned_group_ids = set(["myClonedGroup"])
        test_dom_get(
            utils.dom_get_group_clone, cib_dom,
            cloned_group_ids, all_ids - cloned_group_ids
        )

        clone_ids = set(["myClone", "myGroupClone"])
        test_dom_get(
            utils.dom_get_clone, cib_dom,
            clone_ids, all_ids - clone_ids
        )

        mastered_group_ids = set(["myMasteredGroup"])
        test_dom_get(
            utils.dom_get_group_masterslave, cib_dom,
            mastered_group_ids, all_ids - mastered_group_ids
        )

        master_ids = set(["myMaster", "myGroupMaster"])
        test_dom_get(
            utils.dom_get_master, cib_dom,
            master_ids, all_ids - master_ids
        )


        self.assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myClone"),
            "myClonedResource"
        )
        self.assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myGroupClone"),
            "myClonedGroup"
        )
        self.assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myMaster"),
            "myMasteredResource"
        )
        self.assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myGroupMaster"),
            "myMasteredGroup"
        )

        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myClonedResource"),
            "myClone"
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myClonedGroup"),
            "myGroupClone"
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myClonedGroupedResource"
            ),
            "myGroupClone"
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myMasteredResource"
            ),
            "myMaster"
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myMasteredGroup"
            ),
            "myGroupMaster"
        )
        self.assert_element_id(
            utils.dom_get_resource_clone_ms_parent(
                cib_dom, "myMasteredGroupedResource"
            ),
            "myGroupMaster"
        )
        self.assertEquals(
            None,
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myResource")
        )
        self.assertEquals(
            None,
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myGroup")
        )
        self.assertEquals(
            None,
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myGroupedResource")
        )

    def testDomGetResourceRemoteNodeName(self):
        dom = xml.dom.minidom.parse("empty.xml")
        new_resources = xml.dom.minidom.parseString("""
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
        """).documentElement
        resources = dom.getElementsByTagName("resources")[0]
        resources.parentNode.replaceChild(new_resources, resources)

        self.assertEquals(
            None,
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "dummy1")
            )
        )
        self.assertEquals(
            None,
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "dummy2")
            )
        )
        self.assertEquals(
            "guest1",
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "vm-guest1")
            )
        )

    def testGetElementWithId(self):
        dom = xml.dom.minidom.parseString("""
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
        """).documentElement

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
                utils.dom_get_element_with_id(dom, "bb", "bb2"),
                "cc",
                "cc1"
            ),
            "cc1"
        )
        self.assertEquals(None, utils.dom_get_element_with_id(dom, "dd", "bb1"))
        self.assertEquals(None, utils.dom_get_element_with_id(dom, "bb", "bb4"))
        self.assertEquals(None, utils.dom_get_element_with_id(dom, "bb", "cc1"))
        self.assertEquals(
            None,
            utils.dom_get_element_with_id(
                utils.dom_get_element_with_id(dom, "bb", "bb2"),
                "cc",
                "cc2"
            )
        )

    def testValidateConstraintResource(self):
        dom = self.get_cib_resources()
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myClone")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myGroupClone")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myMaster")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myGroupMaster")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myResource")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myGroup")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myGroupedResource")
        )

        self.assertEquals(
            (False, "Resource 'myNonexistent' does not exist"),
            utils.validate_constraint_resource(dom, "myNonexistent")
        )

        message = (
            "%s is a clone resource, you should use the clone id: "
            "%s when adding constraints. Use --force to override."
        )
        self.assertEquals(
            (False, message % ("myClonedResource", "myClone")),
            utils.validate_constraint_resource(dom, "myClonedResource")
        )
        self.assertEquals(
            (False, message % ("myClonedGroup", "myGroupClone")),
            utils.validate_constraint_resource(dom, "myClonedGroup")
        )
        self.assertEquals(
            (False, message % ("myClonedGroupedResource", "myGroupClone")),
            utils.validate_constraint_resource(dom, "myClonedGroupedResource")
        )

        message = (
            "%s is a master/slave resource, you should use the master id: "
            "%s when adding constraints. Use --force to override."
        )
        self.assertEquals(
            (False, message % ("myMasteredResource", "myMaster")),
            utils.validate_constraint_resource(dom, "myMasteredResource")
        )
        self.assertEquals(
            (False, message % ("myMasteredGroup", "myGroupMaster")),
            utils.validate_constraint_resource(dom, "myMasteredGroup")
        )
        self.assertEquals(
            (False, message % ("myMasteredGroupedResource", "myGroupMaster")),
            utils.validate_constraint_resource(dom, "myMasteredGroupedResource")
        )

        utils.pcs_options["--force"] = True
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myClonedResource")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myClonedGroup")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myClonedGroupedResource")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myMasteredResource")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myMasteredGroup")
        )
        self.assertEquals(
            (True, ""),
            utils.validate_constraint_resource(dom, "myMasteredGroupedResource")
        )

    def testValidateXmlId(self):
        self.assertEquals((True, ""), utils.validate_xml_id("dummy"))
        self.assertEquals((True, ""), utils.validate_xml_id("DUMMY"))
        self.assertEquals((True, ""), utils.validate_xml_id("dUmMy"))
        self.assertEquals((True, ""), utils.validate_xml_id("dummy0"))
        self.assertEquals((True, ""), utils.validate_xml_id("dum0my"))
        self.assertEquals((True, ""), utils.validate_xml_id("dummy-"))
        self.assertEquals((True, ""), utils.validate_xml_id("dum-my"))
        self.assertEquals((True, ""), utils.validate_xml_id("dummy."))
        self.assertEquals((True, ""), utils.validate_xml_id("dum.my"))
        self.assertEquals((True, ""), utils.validate_xml_id("_dummy"))
        self.assertEquals((True, ""), utils.validate_xml_id("dummy_"))
        self.assertEquals((True, ""), utils.validate_xml_id("dum_my"))

        self.assertEquals(
            (False, "test id cannot be empty"),
            utils.validate_xml_id("", "test id")
        )

        msg = "invalid test id '%s', '%s' is not a valid first character for a test id"
        self.assertEquals(
            (False, msg % ("0", "0")),
            utils.validate_xml_id("0", "test id")
        )
        self.assertEquals(
            (False, msg % ("-", "-")),
            utils.validate_xml_id("-", "test id")
        )
        self.assertEquals(
            (False, msg % (".", ".")),
            utils.validate_xml_id(".", "test id")
        )
        self.assertEquals(
            (False, msg % (":", ":")),
            utils.validate_xml_id(":", "test id")
        )
        self.assertEquals(
            (False, msg % ("0dummy", "0")),
            utils.validate_xml_id("0dummy", "test id")
        )
        self.assertEquals(
            (False, msg % ("-dummy", "-")),
            utils.validate_xml_id("-dummy", "test id")
        )
        self.assertEquals(
            (False, msg % (".dummy", ".")),
            utils.validate_xml_id(".dummy", "test id")
        )
        self.assertEquals(
            (False, msg % (":dummy", ":")),
            utils.validate_xml_id(":dummy", "test id")
        )

        msg = "invalid test id '%s', '%s' is not a valid character for a test id"
        self.assertEquals(
            (False, msg % ("dum:my", ":")),
            utils.validate_xml_id("dum:my", "test id")
        )
        self.assertEquals(
            (False, msg % ("dummy:", ":")),
            utils.validate_xml_id("dummy:", "test id")
        )
        self.assertEquals(
            (False, msg % ("dum?my", "?")),
            utils.validate_xml_id("dum?my", "test id")
        )
        self.assertEquals(
            (False, msg % ("dummy?", "?")),
            utils.validate_xml_id("dummy?", "test id")
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

    def assert_element_id(self, node, node_id):
        self.assertTrue(
            isinstance(node, xml.dom.minidom.Element),
            "element with id '%s' not found" % node_id
        )
        self.assertEquals(node.getAttribute("id"), node_id)


if __name__ == "__main__":
    unittest.main()
