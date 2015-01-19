import os
import sys
import shutil
import unittest
import xml.dom.minidom
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
from pcs_test_functions import pcs, ac
import utils

empty_cib = "empty.xml"
temp_cib = "temp.xml"

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

    def test_dom_get_meta_attr_value(self):
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
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "dummy1"), "foo"
            )
        )
        self.assertEquals(
            None,
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "dummy2"), "remote-node"
            )
        )
        self.assertEquals(
            "guest1",
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "vm-guest1"), "remote-node"
            )
        )
        self.assertEquals(
            None,
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "vm-guest1"), "foo"
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

    def test_dom_get_parent_by_tag_name(self):
        dom = xml.dom.minidom.parseString("""
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
        """).documentElement
        bb1 = utils.dom_get_element_with_id(dom, "bb", "bb1")
        cc1 = utils.dom_get_element_with_id(dom, "cc", "cc1")

        self.assert_element_id(
            utils.dom_get_parent_by_tag_name(bb1, "aa"),
            "aa1"
        )
        self.assert_element_id(
            utils.dom_get_parent_by_tag_name(cc1, "aa"),
            "aa1"
        )
        self.assert_element_id(
            utils.dom_get_parent_by_tag_name(cc1, "bb"),
            "bb2"
        )

        self.assertEquals(None, utils.dom_get_parent_by_tag_name(bb1, "cc"))
        self.assertEquals(None, utils.dom_get_parent_by_tag_name(cc1, "dd"))
        self.assertEquals(None, utils.dom_get_parent_by_tag_name(cc1, "ee"))

    def testValidateConstraintResource(self):
        dom = self.get_cib_resources()
        self.assertEquals(
            (True, "", "myClone"),
            utils.validate_constraint_resource(dom, "myClone")
        )
        self.assertEquals(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myGroupClone")
        )
        self.assertEquals(
            (True, "", "myMaster"),
            utils.validate_constraint_resource(dom, "myMaster")
        )
        self.assertEquals(
            (True, "", "myGroupMaster"),
            utils.validate_constraint_resource(dom, "myGroupMaster")
        )
        self.assertEquals(
            (True, "", "myResource"),
            utils.validate_constraint_resource(dom, "myResource")
        )
        self.assertEquals(
            (True, "", "myGroup"),
            utils.validate_constraint_resource(dom, "myGroup")
        )
        self.assertEquals(
            (True, "", "myGroupedResource"),
            utils.validate_constraint_resource(dom, "myGroupedResource")
        )

        self.assertEquals(
            (False, "Resource 'myNonexistent' does not exist", None),
            utils.validate_constraint_resource(dom, "myNonexistent")
        )

        message = (
            "%s is a clone resource, you should use the clone id: "
            "%s when adding constraints. Use --force to override."
        )
        self.assertEquals(
            (
                False,
                message % ("myClonedResource", "myClone"),
                "myClone"
            ),
            utils.validate_constraint_resource(dom, "myClonedResource")
        )
        self.assertEquals(
            (
                False,
                message % ("myClonedGroup", "myGroupClone"),
                "myGroupClone"
            ),
            utils.validate_constraint_resource(dom, "myClonedGroup")
        )
        self.assertEquals(
            (
                False,
                message % ("myClonedGroupedResource", "myGroupClone"),
                "myGroupClone"
            ),
            utils.validate_constraint_resource(dom, "myClonedGroupedResource")
        )

        message = (
            "%s is a master/slave resource, you should use the master id: "
            "%s when adding constraints. Use --force to override."
        )
        self.assertEquals(
            (
                False,
                message % ("myMasteredResource", "myMaster"),
                "myMaster"
            ),
            utils.validate_constraint_resource(dom, "myMasteredResource")
        )
        self.assertEquals(
            (
                False,
                message % ("myMasteredGroup", "myGroupMaster"),
                "myGroupMaster"
            ),
            utils.validate_constraint_resource(dom, "myMasteredGroup")
        )
        self.assertEquals(
            (
                False,
                message % ("myMasteredGroupedResource", "myGroupMaster"),
                "myGroupMaster"
            ),
            utils.validate_constraint_resource(dom, "myMasteredGroupedResource")
        )

        utils.pcs_options["--force"] = True
        self.assertEquals(
            (True, "", "myClone"),
            utils.validate_constraint_resource(dom, "myClonedResource")
        )
        self.assertEquals(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myClonedGroup")
        )
        self.assertEquals(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myClonedGroupedResource")
        )
        self.assertEquals(
            (True, "", "myMaster"),
            utils.validate_constraint_resource(dom, "myMasteredResource")
        )
        self.assertEquals(
            (True, "", "myGroupMaster"),
            utils.validate_constraint_resource(dom, "myMasteredGroup")
        )
        self.assertEquals(
            (True, "", "myGroupMaster"),
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

    def test_get_timeout_seconds(self):
        self.assertEquals(utils.get_timeout_seconds("10"), 10)
        self.assertEquals(utils.get_timeout_seconds("10s"), 10)
        self.assertEquals(utils.get_timeout_seconds("10min"), 600)

        self.assertEquals(utils.get_timeout_seconds("1a1s"), None)
        self.assertEquals(utils.get_timeout_seconds("10m"), None)
        self.assertEquals(utils.get_timeout_seconds("10mim"), None)
        self.assertEquals(utils.get_timeout_seconds("aaa"), None)
        self.assertEquals(utils.get_timeout_seconds(""), None)

        self.assertEquals(utils.get_timeout_seconds("1a1s", True), "1a1s")
        self.assertEquals(utils.get_timeout_seconds("10m", True), "10m")
        self.assertEquals(utils.get_timeout_seconds("10mim", True), "10mim")
        self.assertEquals(utils.get_timeout_seconds("aaa", True), "aaa")
        self.assertEquals(utils.get_timeout_seconds("", True), "")

    def test_get_default_op_timeout(self):
        shutil.copy(empty_cib, temp_cib)
        utils.usefile = True
        utils.filename = temp_cib

        self.assertEquals(utils.get_default_op_timeout(), 20)
        output, retVal = pcs(temp_cib, "property set default-action-timeout=25")
        self.assertEquals(retVal, 0)
        self.assertEquals(utils.get_default_op_timeout(), 25)
        output, retVal = pcs(temp_cib, "property unset default-action-timeout")
        self.assertEquals(retVal, 0)
        self.assertEquals(utils.get_default_op_timeout(), 20)

        utils.usefile = False
        utils.filename = ""

    def test_get_resource_op_timeout(self):
        shutil.copy(empty_cib, temp_cib)
        utils.usefile = True
        utils.filename = temp_cib

        output, retVal = pcs(temp_cib, "property set default-action-timeout=25")
        ac(output, "")
        self.assertEquals(retVal, 0)
        output, retVal = pcs(
            temp_cib,
            "resource create dummy Dummy op start timeout=33s --no-default-ops"
        )
        ac(output, "")
        self.assertEquals(retVal, 0)
        dom = xml.dom.minidom.parse(temp_cib)

        self.assertEquals(
            utils.get_resource_op_timeout(dom, "dummy", "start"),
            33
        )
        self.assertEquals(
            utils.get_resource_op_timeout(dom, "dummy", "stop"),
            20
        )
        self.assertEquals(
            utils.get_resource_op_timeout(dom, "dummy0", "start"),
            25
        )

        utils.usefile = False
        utils.filename = ""

    def get_cib_status_lrm(self):
        cib_dom = self.get_cib_empty()
        new_status = xml.dom.minidom.parseString("""
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
        """).documentElement
        status = cib_dom.getElementsByTagName("status")[0]
        status.parentNode.replaceChild(new_status, status)
        return cib_dom

    def test_get_lrm_rsc_op(self):
        dom = self.get_cib_status_lrm()

        op_list = utils.get_lrm_rsc_op(dom, "dummy")
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(
            op_id_list,
            ["dummy_monitor_0", "dummy_stop_0", "dummy_start_0",
                "dummy_monitor_30000",]
        )
        op_list = utils.get_lrm_rsc_op(dom, "dummy", ["monitor"])
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(
            op_id_list,
            ["dummy_monitor_0", "dummy_monitor_30000",]
        )
        op_list = utils.get_lrm_rsc_op(dom, "dummy", ["stop", "start"])
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(
            op_id_list,
            ["dummy_stop_0", "dummy_start_0",]
        )
        op_list = utils.get_lrm_rsc_op(dom, "dummy", last_call_id=30)
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(
            op_id_list,
            ["dummy_stop_0", "dummy_start_0", "dummy_monitor_30000",]
        )
        op_list = utils.get_lrm_rsc_op(dom, "dummy", ["monitor"], 30)
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(
            op_id_list,
            ["dummy_monitor_30000",]
        )

        op_list = utils.get_lrm_rsc_op(dom, "dummy", last_call_id=340)
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(op_id_list, [])
        op_list = utils.get_lrm_rsc_op(dom, "dummy", last_call_id=34)
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(op_id_list, [])
        op_list = utils.get_lrm_rsc_op(dom, "dummy0", ["monitor"], 30)
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(op_id_list, [])
        op_list = utils.get_lrm_rsc_op(dom, "dummy0", ["monitor"])
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(op_id_list, [])
        op_list = utils.get_lrm_rsc_op(dom, "dummy0", last_call_id=30)
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(op_id_list, [])
        op_list = utils.get_lrm_rsc_op(dom, "dummy0")
        op_id_list = [op.getAttribute("id") for op in op_list]
        self.assertEquals(op_id_list, [])

    def test_get_lrm_rsc_op_failures(self):
        dom = self.get_cib_status_lrm()

        failures = utils.get_lrm_rsc_op_failures(
            utils.get_lrm_rsc_op(dom, "dummy")
        )
        self.assertEquals(
            failures,
            ["rh70-node2: failed", "Xrh70-node1X: test"]
        )

        failures = utils.get_lrm_rsc_op_failures(
            utils.get_lrm_rsc_op(dom, "dummy", ["start"])
        )
        self.assertEquals(failures, [])
        failures = utils.get_lrm_rsc_op_failures(
            utils.get_lrm_rsc_op(dom, "dummy0")
        )
        self.assertEquals(failures, [])

    def test_resource_running_on(self):
        status = xml.dom.minidom.parseString("""
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
        <clone id="myMaster">
            <resource id="myMasteredResource:1" role="Slave">
                <node name="rh70-node2" />
            </resource>
            <resource id="myMasteredResource" role="Slave">
                <node name="rh70-node3" />
            </resource>
            <resource id="myMasteredResource" role="Master">
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
        <clone id="myGroupMaster">
            <group id="myMasteredGroup:0">
                 <resource id="myMasteredGroupedResource" role="Slave">
                     <node name="rh70-node1" />
                 </resource>
            </group>
            <group id="myMasteredGroup:1">
                 <resource id="myMasteredGroupedResource" role="Master">
                     <node name="rh70-node2" />
                 </resource>
            </group>
            <group id="myMasteredGroup:2">
                 <resource id="myMasteredGroupedResource" role="Slave">
                     <node name="rh70-node3" />
                 </resource>
            </group>
        </clone>
        <resource id="myStoppedResource" role="Stopped">
        </resource>
    </resources>
</crm_mon>
        """).documentElement

        self.assertEquals(
            utils.resource_running_on("myResource", status),
            {
                'message':
                    "Resource 'myResource' is running on node rh70-node1.",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1"],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myClonedResource", status),
            {
                'message':
                    "Resource 'myClonedResource' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3.",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3"],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myClone", status),
            {
                'message':
                    "Resource 'myClone' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3.",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3"],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myMasteredResource", status),
            {
                'message':
                    "Resource 'myMasteredResource' is master on node "
                        "rh70-node1; slave on nodes rh70-node2, rh70-node3.",
                'nodes_master': ["rh70-node1"],
                'nodes_slave': ["rh70-node2", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myMaster", status),
            {
                'message':
                    "Resource 'myMaster' is master on node "
                        "rh70-node1; slave on nodes rh70-node2, rh70-node3.",
                'nodes_master': ["rh70-node1"],
                'nodes_slave': ["rh70-node2", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myGroupedResource", status),
            {
                'message':
                    "Resource 'myGroupedResource' is running on node "
                        "rh70-node2.",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node2"],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myGroup", status),
            {
                'message':
                    "Resource 'myGroup' is running on node "
                        "rh70-node2.",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node2"],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myClonedGroupedResource", status),
            {
                'message':
                    "Resource 'myClonedGroupedResource' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3",
                    "rh70-node3"],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myClonedGroup", status),
            {
                'message':
                    "Resource 'myClonedGroup' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3",
                    "rh70-node3"],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myGroupClone", status),
            {
                'message':
                    "Resource 'myGroupClone' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3",
                    "rh70-node3"],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myMasteredGroupedResource", status),
            {
                'message':
                    "Resource 'myMasteredGroupedResource' is master on node "
                        "rh70-node2; slave on nodes rh70-node1, rh70-node3.",
                'nodes_master': ["rh70-node2"],
                'nodes_slave': ["rh70-node1", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myMasteredGroup", status),
            {
                'message':
                    "Resource 'myMasteredGroup' is master on node "
                        "rh70-node2; slave on nodes rh70-node1, rh70-node3.",
                'nodes_master': ["rh70-node2"],
                'nodes_slave': ["rh70-node1", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myGroupMaster", status),
            {
                'message':
                    "Resource 'myGroupMaster' is master on node "
                        "rh70-node2; slave on nodes rh70-node1, rh70-node3.",
                'nodes_master': ["rh70-node2"],
                'nodes_slave': ["rh70-node1", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEquals(
            utils.resource_running_on("notMyResource", status),
            {
                'message':
                    "Resource 'notMyResource' is not running on any node",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': [],
            }
        )
        self.assertEquals(
            utils.resource_running_on("myStoppedResource", status),
            {
                'message':
                    "Resource 'myStoppedResource' is not running on any node",
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': [],
            }
        )

    def test_count_expected_resource_instances(self):
        dom = xml.dom.minidom.parse("empty.xml")
        new_resources = xml.dom.minidom.parseString("""
<resources>
    <primitive id="prim1">
    </primitive>
    <group id="group1">
        <primitive id="prim2">
        </primitive>
    </group>
    <clone id="clone1">
        <primitive id="prim3">
        </primitive>
    </clone>
    <clone id="clone2">
        <primitive id="prim4">
        </primitive>
        <meta_attributes>
            <nvpair name="clone-max" value="9"/>
            <nvpair name="clone-node-max" value="3"/>
        </meta_attributes>
    </clone>
    <clone id="clone3">
        <primitive id="prim5">
        </primitive>
        <meta_attributes>
            <nvpair name="clone-max" value="2"/>
            <nvpair name="clone-node-max" value="3"/>
        </meta_attributes>
    </clone>
    <clone id="clone4">
        <primitive id="prim6">
        </primitive>
        <meta_attributes>
            <nvpair name="globally-unique" value="true"/>
            <nvpair name="clone-max" value="9"/>
        </meta_attributes>
    </clone>
    <clone id="clone5">
        <primitive id="prim7">
        </primitive>
        <meta_attributes>
            <nvpair name="globally-unique" value="true"/>
            <nvpair name="clone-max" value="9"/>
            <nvpair name="clone-node-max" value="2"/>
        </meta_attributes>
    </clone>
    <clone id="clone6">
        <primitive id="prim8">
        </primitive>
        <meta_attributes>
            <nvpair name="globally-unique" value="true"/>
            <nvpair name="clone-max" value="9"/>
            <nvpair name="clone-node-max" value="4"/>
        </meta_attributes>
    </clone>
    <master id="master1">
        <primitive id="prim9">
        </primitive>
    </master>
    <master id="master2">
        <primitive id="prim10">
        </primitive>
        <meta_attributes>
            <nvpair name="clone-max" value="9"/>
            <nvpair name="clone-node-max" value="3"/>
            <nvpair name="master-max" value="5"/>
            <nvpair name="master-node-max" value="4"/>
        </meta_attributes>
    </master>
    <master id="master3">
        <primitive id="prim11">
        </primitive>
        <meta_attributes>
            <nvpair name="globally-unique" value="true"/>
            <nvpair name="clone-max" value="9"/>
            <nvpair name="clone-node-max" value="3"/>
        </meta_attributes>
    </master>
    <master id="master4">
        <primitive id="prim12">
        </primitive>
        <meta_attributes>
            <nvpair name="globally-unique" value="true"/>
            <nvpair name="clone-max" value="9"/>
            <nvpair name="clone-node-max" value="3"/>
            <nvpair name="master-max" value="3"/>
            <nvpair name="master-node-max" value="2"/>
        </meta_attributes>
    </master>
    <master id="master5">
        <primitive id="prim13">
        </primitive>
        <meta_attributes>
            <nvpair name="globally-unique" value="true"/>
            <nvpair name="clone-max" value="9"/>
            <nvpair name="clone-node-max" value="3"/>
            <nvpair name="master-max" value="12"/>
            <nvpair name="master-node-max" value="4"/>
        </meta_attributes>
    </master>
</resources>
        """).documentElement
        resources = dom.getElementsByTagName("resources")[0]
        resources.parentNode.replaceChild(new_resources, resources)

        self.assertEquals(
            1,
            utils.count_expected_resource_instances(
                utils.dom_get_resource(dom, "prim1"), 3
            )
        )
        self.assertEquals(
            1,
            utils.count_expected_resource_instances(
                utils.dom_get_group(dom, "group1"), 3
            )
        )
        self.assertEquals(
            3,
            utils.count_expected_resource_instances(
                utils.dom_get_clone(dom, "clone1"), 3
            )
        )
        self.assertEquals(
            3,
            utils.count_expected_resource_instances(
                utils.dom_get_clone(dom, "clone2"), 3
            )
        )
        self.assertEquals(
            2,
            utils.count_expected_resource_instances(
                utils.dom_get_clone(dom, "clone3"), 3
            )
        )
        self.assertEquals(
            3,
            utils.count_expected_resource_instances(
                utils.dom_get_clone(dom, "clone4"), 3
            )
        )
        self.assertEquals(
            6,
            utils.count_expected_resource_instances(
                utils.dom_get_clone(dom, "clone5"), 3
            )
        )
        self.assertEquals(
            9,
            utils.count_expected_resource_instances(
                utils.dom_get_clone(dom, "clone6"), 3
            )
        )
        self.assertEquals(
            1,
            utils.count_expected_resource_instances(
                utils.dom_get_master(dom, "master1"), 3
            )
        )
        self.assertEquals(
            3,
            utils.count_expected_resource_instances(
                utils.dom_get_master(dom, "master2"), 3
            )
        )
        self.assertEquals(
            1,
            utils.count_expected_resource_instances(
                utils.dom_get_master(dom, "master3"), 3
            )
        )
        self.assertEquals(
            3,
            utils.count_expected_resource_instances(
                utils.dom_get_master(dom, "master4"), 3
            )
        )
        self.assertEquals(
            9,
            utils.count_expected_resource_instances(
                utils.dom_get_master(dom, "master5"), 3
            )
        )

    def test_parse_cman_quorum_info(self):
        parsed = utils.parse_cman_quorum_info("""\
Version: 6.2.0
Config Version: 23
Cluster Name: cluster66
Cluster Id: 22265
Cluster Member: Yes
Cluster Generation: 3612
Membership state: Cluster-Member
Nodes: 3
Expected votes: 3
Total votes: 3
Node votes: 1
Quorum: 2 
Active subsystems: 8
Flags: 
Ports Bound: 0 
Node name: rh66-node2
Node ID: 2
Multicast addresses: 239.192.86.80
Node addresses: 192.168.122.61
---Votes---
1 M 3 rh66-node1
2 M 2 rh66-node2
3 M 1 rh66-node3
""")
        self.assertEquals(True, parsed["quorate"])
        self.assertEquals(2, parsed["quorum"])
        self.assertEquals(
            [
                {"name": "rh66-node1", "votes": 3, "local": False},
                {"name": "rh66-node2", "votes": 2, "local": True},
                {"name": "rh66-node3", "votes": 1, "local": False},
            ],
            parsed["node_list"]
        )

        parsed = utils.parse_cman_quorum_info("""\
Version: 6.2.0
Config Version: 23
Cluster Name: cluster66
Cluster Id: 22265
Cluster Member: Yes
Cluster Generation: 3612
Membership state: Cluster-Member
Nodes: 3
Expected votes: 3
Total votes: 3
Node votes: 1
Quorum: 2 Activity blocked
Active subsystems: 8
Flags: 
Ports Bound: 0 
Node name: rh66-node1
Node ID: 1
Multicast addresses: 239.192.86.80
Node addresses: 192.168.122.61
---Votes---
1 M 3 rh66-node1
2 X 2 rh66-node2
3 X 1 rh66-node3
""")
        self.assertEquals(False, parsed["quorate"])
        self.assertEquals(2, parsed["quorum"])
        self.assertEquals(
            [
                {"name": "rh66-node1", "votes": 3, "local": True},
            ],
            parsed["node_list"]
        )

        parsed = utils.parse_cman_quorum_info("")
        self.assertEquals(None, parsed)

        parsed = utils.parse_cman_quorum_info("""\
Version: 6.2.0
Config Version: 23
Cluster Name: cluster66
Cluster Id: 22265
Cluster Member: Yes
Cluster Generation: 3612
Membership state: Cluster-Member
Nodes: 3
Expected votes: 3
Total votes: 3
Node votes: 1
Quorum: 
Active subsystems: 8
Flags: 
Ports Bound: 0 
Node name: rh66-node2
Node ID: 2
Multicast addresses: 239.192.86.80
Node addresses: 192.168.122.61
---Votes---
1 M 3 rh66-node1
2 M 2 rh66-node2
3 M 1 rh66-node3
""")
        self.assertEquals(None, parsed)

        parsed = utils.parse_cman_quorum_info("""\
Version: 6.2.0
Config Version: 23
Cluster Name: cluster66
Cluster Id: 22265
Cluster Member: Yes
Cluster Generation: 3612
Membership state: Cluster-Member
Nodes: 3
Expected votes: 3
Total votes: 3
Node votes: 1
Quorum: Foo
Active subsystems: 8
Flags: 
Ports Bound: 0 
Node name: rh66-node2
Node ID: 2
Multicast addresses: 239.192.86.80
Node addresses: 192.168.122.61
---Votes---
1 M 3 rh66-node1
2 M 2 rh66-node2
3 M 1 rh66-node3
""")
        self.assertEquals(None, parsed)

        parsed = utils.parse_cman_quorum_info("""\
Version: 6.2.0
Config Version: 23
Cluster Name: cluster66
Cluster Id: 22265
Cluster Member: Yes
Cluster Generation: 3612
Membership state: Cluster-Member
Nodes: 3
Expected votes: 3
Total votes: 3
Node votes: 1
Quorum: 4
Active subsystems: 8
Flags: 
Ports Bound: 0 
Node name: rh66-node2
Node ID: 2
Multicast addresses: 239.192.86.80
Node addresses: 192.168.122.61
---Votes---
1 M 3 rh66-node1
2 M Foo rh66-node2
3 M 1 rh66-node3
""")
        self.assertEquals(None, parsed)

    def test_parse_quorumtool_output(self):
        parsed = utils.parse_quorumtool_output("""\
Quorum information
------------------
Date:             Fri Jan 16 13:03:28 2015
Quorum provider:  corosync_votequorum
Nodes:            3
Node ID:          1
Ring ID:          19860
Quorate:          Yes

Votequorum information
----------------------
Expected votes:   3
Highest expected: 3
Total votes:      3
Quorum:           2
Flags:            Quorate

Membership information
----------------------
    Nodeid      Votes    Qdevice Name
         1          3         NR rh70-node1
         2          2         NR rh70-node2 (local)
         3          1         NR rh70-node3
""")
        self.assertEquals(True, parsed["quorate"])
        self.assertEquals(2, parsed["quorum"])
        self.assertEquals(
            [
                {"name": "rh70-node1", "votes": 3, "local": False},
                {"name": "rh70-node2", "votes": 2, "local": True},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            parsed["node_list"]
        )

        parsed = utils.parse_quorumtool_output("""\
Quorum information
------------------
Date:             Fri Jan 16 13:03:35 2015
Quorum provider:  corosync_votequorum
Nodes:            1
Node ID:          1
Ring ID:          19868
Quorate:          No

Votequorum information
----------------------
Expected votes:   3
Highest expected: 3
Total votes:      1
Quorum:           2 Activity blocked
Flags:            

Membership information
----------------------
    Nodeid      Votes    Qdevice Name
             1          1         NR rh70-node1 (local)
""")
        self.assertEquals(False, parsed["quorate"])
        self.assertEquals(2, parsed["quorum"])
        self.assertEquals(
            [
                {"name": "rh70-node1", "votes": 1, "local": True},
            ],
            parsed["node_list"]
        )

        parsed = utils.parse_quorumtool_output("")
        self.assertEquals(None, parsed)

        parsed = utils.parse_quorumtool_output("""\
Quorum information
------------------
Date:             Fri Jan 16 13:03:28 2015
Quorum provider:  corosync_votequorum
Nodes:            3
Node ID:          1
Ring ID:          19860
Quorate:          Yes

Votequorum information
----------------------
Expected votes:   3
Highest expected: 3
Total votes:      3
Quorum:           
Flags:            Quorate

Membership information
----------------------
    Nodeid      Votes    Qdevice Name
         1          1         NR rh70-node1 (local)
         2          1         NR rh70-node2
         3          1         NR rh70-node3
""")
        self.assertEquals(None, parsed)

        parsed = utils.parse_quorumtool_output("""\
Quorum information
------------------
Date:             Fri Jan 16 13:03:28 2015
Quorum provider:  corosync_votequorum
Nodes:            3
Node ID:          1
Ring ID:          19860
Quorate:          Yes

Votequorum information
----------------------
Expected votes:   3
Highest expected: 3
Total votes:      3
Quorum:           Foo
Flags:            Quorate

Membership information
----------------------
    Nodeid      Votes    Qdevice Name
         1          1         NR rh70-node1 (local)
         2          1         NR rh70-node2
         3          1         NR rh70-node3
""")
        self.assertEquals(None, parsed)

        parsed = utils.parse_quorumtool_output("""\
Quorum information
------------------
Date:             Fri Jan 16 13:03:28 2015
Quorum provider:  corosync_votequorum
Nodes:            3
Node ID:          1
Ring ID:          19860
Quorate:          Yes

Votequorum information
----------------------
Expected votes:   3
Highest expected: 3
Total votes:      3
Quorum:           2
Flags:            Quorate

Membership information
----------------------
    Nodeid      Votes    Qdevice Name
         1          1         NR rh70-node1 (local)
         2        foo         NR rh70-node2
         3          1         NR rh70-node3
""")
        self.assertEquals(None, parsed)

    def test_is_node_stop_cause_quorum_loss(self):
        quorum_info = {
            "quorate": False,
        }
        self.assertEquals(
            False,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

        quorum_info = {
            "quorate": True,
            "quorum": 1,
            "node_list": [
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
        }
        self.assertEquals(
            False,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

        quorum_info = {
            "quorate": True,
            "quorum": 1,
            "node_list": [
                {"name": "rh70-node3", "votes": 1, "local": True},
            ],
        }
        self.assertEquals(
            True,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": False},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": True},
            ],
        }
        self.assertEquals(
            False,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": False},
                {"name": "rh70-node2", "votes": 2, "local": True},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
        }
        self.assertEquals(
            False,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
        }
        self.assertEquals(
            True,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )


        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
        }
        self.assertEquals(
            False,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node3"]
            )
        )

        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
        }
        self.assertEquals(
            False,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2"]
            )
        )

        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
        }
        self.assertEquals(
            True,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node1"]
            )
        )

        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 4, "local": True},
                {"name": "rh70-node2", "votes": 1, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
        }
        self.assertEquals(
            False,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2", "rh70-node3"]
            )
        )

        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
        }
        self.assertEquals(
            True,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2", "rh70-node3"]
            )
        )

    def assert_element_id(self, node, node_id):
        self.assertTrue(
            isinstance(node, xml.dom.minidom.Element),
            "element with id '%s' not found" % node_id
        )
        self.assertEquals(node.getAttribute("id"), node_id)


if __name__ == "__main__":
    unittest.main()
