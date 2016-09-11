from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import sys
from pcs.test.tools import pcs_unittest as unittest
import xml.dom.minidom
import xml.etree.cElementTree as ET
from time import sleep

try:
    from cStringIO import StringIO
except ImportError:
    #python 3
    from io import StringIO

from pcs.test.tools.xml import dom_get_child_elements
from pcs.test.tools.misc import get_test_resource as rc

from pcs import utils

cib_with_nodes = rc("cib-empty-withnodes.xml")
empty_cib = rc("cib-empty.xml")
temp_cib = rc("temp-cib.xml")

unittest.TestCase.maxDiff = None

class UtilsTest(unittest.TestCase):

    def get_cib_empty(self):
        return xml.dom.minidom.parse(empty_cib)

    def get_cib_with_nodes_minidom(self):
        return xml.dom.minidom.parse(cib_with_nodes)

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
                  <clone id="myUniqueClone">
                      <primitive id="myUniqueClonedResource"
                          class="ocf" provider="heartbeat" type="Dummy">
                      </primitive>
                      <meta-attributes>
                        <nvpair name="globally-unique" value="true" />
                      </meta-attributes>
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
            "myUniqueClone", "myUniqueClonedResource",
            "myMaster", "myMasteredResource",
            "myGroup", "myGroupedResource",
            "myGroupClone", "myClonedGroup", "myClonedGroupedResource",
            "myGroupMaster", "myMasteredGroup", "myMasteredGroupedResource",
        ])

        resource_ids = set([
            "myResource",
            "myClonedResource", "myUniqueClonedResource",
            "myGroupedResource", "myMasteredResource",
            "myClonedGroupedResource", "myMasteredGroupedResource"
        ])
        test_dom_get(
            utils.dom_get_resource, cib_dom,
            resource_ids, all_ids - resource_ids
        )

        cloned_ids = set([
            "myClonedResource", "myUniqueClonedResource",
            "myClonedGroupedResource"
        ])
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

        clone_ids = set(["myClone", "myUniqueClone", "myGroupClone"])
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
        self.assertEqual(
            None,
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myResource")
        )
        self.assertEqual(
            None,
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myGroup")
        )
        self.assertEqual(
            None,
            utils.dom_get_resource_clone_ms_parent(cib_dom, "myGroupedResource")
        )

    def testDomGetResourceRemoteNodeName(self):
        dom = self.get_cib_empty()
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
                <primitive id="dummy3"
                        class="ocf" provider="pacemaker" type="remote">
                </primitive>
            </resources>
        """).documentElement
        resources = dom.getElementsByTagName("resources")[0]
        resources.parentNode.replaceChild(new_resources, resources)

        self.assertEqual(
            None,
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "dummy1")
            )
        )
        self.assertEqual(
            None,
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "dummy2")
            )
        )
        self.assertEqual(
            "guest1",
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "vm-guest1")
            )
        )
        self.assertEqual(
            "dummy3",
            utils.dom_get_resource_remote_node_name(
                utils.dom_get_resource(dom, "dummy3")
            )
        )

    def test_dom_get_meta_attr_value(self):
        dom = self.get_cib_empty()
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

        self.assertEqual(
            None,
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "dummy1"), "foo"
            )
        )
        self.assertEqual(
            None,
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "dummy2"), "remote-node"
            )
        )
        self.assertEqual(
            "guest1",
            utils.dom_get_meta_attr_value(
                utils.dom_get_resource(dom, "vm-guest1"), "remote-node"
            )
        )
        self.assertEqual(
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
        self.assertEqual(None, utils.dom_get_element_with_id(dom, "dd", "bb1"))
        self.assertEqual(None, utils.dom_get_element_with_id(dom, "bb", "bb4"))
        self.assertEqual(None, utils.dom_get_element_with_id(dom, "bb", "cc1"))
        self.assertEqual(
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

        self.assertEqual(None, utils.dom_get_parent_by_tag_name(bb1, "cc"))
        self.assertEqual(None, utils.dom_get_parent_by_tag_name(cc1, "dd"))
        self.assertEqual(None, utils.dom_get_parent_by_tag_name(cc1, "ee"))

    def testValidateConstraintResource(self):
        dom = self.get_cib_resources()
        self.assertEqual(
            (True, "", "myClone"),
            utils.validate_constraint_resource(dom, "myClone")
        )
        self.assertEqual(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myGroupClone")
        )
        self.assertEqual(
            (True, "", "myMaster"),
            utils.validate_constraint_resource(dom, "myMaster")
        )
        self.assertEqual(
            (True, "", "myGroupMaster"),
            utils.validate_constraint_resource(dom, "myGroupMaster")
        )
        self.assertEqual(
            (True, "", "myResource"),
            utils.validate_constraint_resource(dom, "myResource")
        )
        self.assertEqual(
            (True, "", "myGroup"),
            utils.validate_constraint_resource(dom, "myGroup")
        )
        self.assertEqual(
            (True, "", "myGroupedResource"),
            utils.validate_constraint_resource(dom, "myGroupedResource")
        )

        self.assertEqual(
            (False, "Resource 'myNonexistent' does not exist", None),
            utils.validate_constraint_resource(dom, "myNonexistent")
        )

        message = (
            "%s is a clone resource, you should use the clone id: "
            "%s when adding constraints. Use --force to override."
        )
        self.assertEqual(
            (
                False,
                message % ("myClonedResource", "myClone"),
                "myClone"
            ),
            utils.validate_constraint_resource(dom, "myClonedResource")
        )
        self.assertEqual(
            (
                False,
                message % ("myClonedGroup", "myGroupClone"),
                "myGroupClone"
            ),
            utils.validate_constraint_resource(dom, "myClonedGroup")
        )
        self.assertEqual(
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
        self.assertEqual(
            (
                False,
                message % ("myMasteredResource", "myMaster"),
                "myMaster"
            ),
            utils.validate_constraint_resource(dom, "myMasteredResource")
        )
        self.assertEqual(
            (
                False,
                message % ("myMasteredGroup", "myGroupMaster"),
                "myGroupMaster"
            ),
            utils.validate_constraint_resource(dom, "myMasteredGroup")
        )
        self.assertEqual(
            (
                False,
                message % ("myMasteredGroupedResource", "myGroupMaster"),
                "myGroupMaster"
            ),
            utils.validate_constraint_resource(dom, "myMasteredGroupedResource")
        )

        utils.pcs_options["--force"] = True
        self.assertEqual(
            (True, "", "myClone"),
            utils.validate_constraint_resource(dom, "myClonedResource")
        )
        self.assertEqual(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myClonedGroup")
        )
        self.assertEqual(
            (True, "", "myGroupClone"),
            utils.validate_constraint_resource(dom, "myClonedGroupedResource")
        )
        self.assertEqual(
            (True, "", "myMaster"),
            utils.validate_constraint_resource(dom, "myMasteredResource")
        )
        self.assertEqual(
            (True, "", "myGroupMaster"),
            utils.validate_constraint_resource(dom, "myMasteredGroup")
        )
        self.assertEqual(
            (True, "", "myGroupMaster"),
            utils.validate_constraint_resource(dom, "myMasteredGroupedResource")
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
            utils.validate_xml_id("", "test id")
        )

        msg = "invalid test id '%s', '%s' is not a valid first character for a test id"
        self.assertEqual(
            (False, msg % ("0", "0")),
            utils.validate_xml_id("0", "test id")
        )
        self.assertEqual(
            (False, msg % ("-", "-")),
            utils.validate_xml_id("-", "test id")
        )
        self.assertEqual(
            (False, msg % (".", ".")),
            utils.validate_xml_id(".", "test id")
        )
        self.assertEqual(
            (False, msg % (":", ":")),
            utils.validate_xml_id(":", "test id")
        )
        self.assertEqual(
            (False, msg % ("0dummy", "0")),
            utils.validate_xml_id("0dummy", "test id")
        )
        self.assertEqual(
            (False, msg % ("-dummy", "-")),
            utils.validate_xml_id("-dummy", "test id")
        )
        self.assertEqual(
            (False, msg % (".dummy", ".")),
            utils.validate_xml_id(".dummy", "test id")
        )
        self.assertEqual(
            (False, msg % (":dummy", ":")),
            utils.validate_xml_id(":dummy", "test id")
        )

        msg = "invalid test id '%s', '%s' is not a valid character for a test id"
        self.assertEqual(
            (False, msg % ("dum:my", ":")),
            utils.validate_xml_id("dum:my", "test id")
        )
        self.assertEqual(
            (False, msg % ("dummy:", ":")),
            utils.validate_xml_id("dummy:", "test id")
        )
        self.assertEqual(
            (False, msg % ("dum?my", "?")),
            utils.validate_xml_id("dum?my", "test id")
        )
        self.assertEqual(
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

        self.assertEqual(
            utils.resource_running_on("myResource", status),
            {
                'message':
                    "Resource 'myResource' is running on node rh70-node1.",
                'is_running': True,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1"],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myClonedResource", status),
            {
                'message':
                    "Resource 'myClonedResource' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3.",
                'is_running': True,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3"],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myClone", status),
            {
                'message':
                    "Resource 'myClone' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3.",
                'is_running': True,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3"],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myMasteredResource", status),
            {
                'message':
                    "Resource 'myMasteredResource' is master on node "
                        "rh70-node1; slave on nodes rh70-node2, rh70-node3.",
                'is_running': True,
                'nodes_master': ["rh70-node1"],
                'nodes_slave': ["rh70-node2", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myMaster", status),
            {
                'message':
                    "Resource 'myMaster' is master on node "
                        "rh70-node1; slave on nodes rh70-node2, rh70-node3.",
                'is_running': True,
                'nodes_master': ["rh70-node1"],
                'nodes_slave': ["rh70-node2", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myGroupedResource", status),
            {
                'message':
                    "Resource 'myGroupedResource' is running on node "
                        "rh70-node2.",
                'is_running': True,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node2"],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myGroup", status),
            {
                'message':
                    "Resource 'myGroup' is running on node "
                        "rh70-node2.",
                'is_running': True,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node2"],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myClonedGroupedResource", status),
            {
                'message':
                    "Resource 'myClonedGroupedResource' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                'is_running': True,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3",
                    "rh70-node3"],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myClonedGroup", status),
            {
                'message':
                    "Resource 'myClonedGroup' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                'is_running': True,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3",
                    "rh70-node3"],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myGroupClone", status),
            {
                'message':
                    "Resource 'myGroupClone' is running on nodes "
                        "rh70-node1, rh70-node2, rh70-node3, rh70-node3.",
                'is_running': True,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': ["rh70-node1", "rh70-node2", "rh70-node3",
                    "rh70-node3"],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myMasteredGroupedResource", status),
            {
                'message':
                    "Resource 'myMasteredGroupedResource' is master on node "
                        "rh70-node2; slave on nodes rh70-node1, rh70-node3.",
                'is_running': True,
                'nodes_master': ["rh70-node2"],
                'nodes_slave': ["rh70-node1", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myMasteredGroup", status),
            {
                'message':
                    "Resource 'myMasteredGroup' is master on node "
                        "rh70-node2; slave on nodes rh70-node1, rh70-node3.",
                'is_running': True,
                'nodes_master': ["rh70-node2"],
                'nodes_slave': ["rh70-node1", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myGroupMaster", status),
            {
                'message':
                    "Resource 'myGroupMaster' is master on node "
                        "rh70-node2; slave on nodes rh70-node1, rh70-node3.",
                'is_running': True,
                'nodes_master': ["rh70-node2"],
                'nodes_slave': ["rh70-node1", "rh70-node3"],
                'nodes_started': [],
            }
        )
        self.assertEqual(
            utils.resource_running_on("notMyResource", status),
            {
                'message':
                    "Resource 'notMyResource' is not running on any node",
                'is_running': False,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': [],
            }
        )
        self.assertEqual(
            utils.resource_running_on("myStoppedResource", status),
            {
                'message':
                    "Resource 'myStoppedResource' is not running on any node",
                'is_running': False,
                'nodes_master': [],
                'nodes_slave': [],
                'nodes_started': [],
            }
        )

    def test_get_operations_from_transitions(self):
        transitions = utils.parse(rc("transitions01.xml"))
        self.assertEqual(
            [
                {
                    'id': 'dummy',
                    'long_id': 'dummy',
                    'operation': 'stop',
                    'on_node': 'rh7-3',
                },
                {
                    'id': 'dummy',
                    'long_id': 'dummy',
                    'operation': 'start',
                    'on_node': 'rh7-2',
                },
                {
                    'id': 'd0',
                    'long_id': 'd0:1',
                    'operation': 'stop',
                    'on_node': 'rh7-1',
                },
                {
                    'id': 'd0',
                    'long_id': 'd0:1',
                    'operation': 'start',
                    'on_node': 'rh7-2',
                },
                {
                    'id': 'state',
                    'long_id': 'state:0',
                    'operation': 'stop',
                    'on_node': 'rh7-3',
                },
                {
                    'id': 'state',
                    'long_id': 'state:0',
                    'operation': 'start',
                    'on_node': 'rh7-2',
                },
            ],
            utils.get_operations_from_transitions(transitions)
        )

        transitions = utils.parse(rc("transitions02.xml"))
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
                }
            ],
            utils.get_operations_from_transitions(transitions)
        )

    def test_get_resources_location_from_operations(self):
        cib_dom = self.get_cib_resources()

        operations = []
        self.assertEqual(
            {},
            utils.get_resources_location_from_operations(cib_dom, operations)
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
                'myResource': {
                    'id': 'myResource',
                    'id_for_constraint': 'myResource',
                    'long_id': 'myResource',
                    'start_on_node': 'rh7-1',
                 },
            },
            utils.get_resources_location_from_operations(cib_dom, operations)
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
                'myResource': {
                    'id': 'myResource',
                    'id_for_constraint': 'myResource',
                    'long_id': 'myResource',
                    'start_on_node': 'rh7-2',
                 },
            },
            utils.get_resources_location_from_operations(cib_dom, operations)
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
                'myResource': {
                    'id': 'myResource',
                    'id_for_constraint': 'myResource',
                    'long_id': 'myResource',
                    'start_on_node': 'rh7-1',
                 },
                'myClonedResource:0': {
                    'id': 'myClonedResource',
                    'id_for_constraint': 'myClone',
                    'long_id': 'myClonedResource:0',
                    'start_on_node': 'rh7-2',
                 },
                'myClonedResource:1': {
                    'id': 'myClonedResource',
                    'id_for_constraint': 'myClone',
                    'long_id': 'myClonedResource:1',
                    'start_on_node': 'rh7-3',
                 },
            },
            utils.get_resources_location_from_operations(cib_dom, operations)
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
                'myUniqueClonedResource:0': {
                    'id': 'myUniqueClonedResource:0',
                    'id_for_constraint': 'myUniqueClone',
                    'long_id': 'myUniqueClonedResource:0',
                    'start_on_node': 'rh7-1',
                 },
                'myUniqueClonedResource:2': {
                    'id': 'myUniqueClonedResource:2',
                    'id_for_constraint': 'myUniqueClone',
                    'long_id': 'myUniqueClonedResource:2',
                    'start_on_node': 'rh7-3',
                 },
            },
            utils.get_resources_location_from_operations(cib_dom, operations)
        )

        operations = [
            {
                "id": "myMasteredGroupedResource",
                "long_id": "myMasteredGroupedResource:0",
                "operation": "start",
                "on_node": "rh7-1",
            },
            {
                "id": "myMasteredGroupedResource",
                "long_id": "myMasteredGroupedResource:1",
                "operation": "demote",
                "on_node": "rh7-2",
            },
            {
                "id": "myMasteredGroupedResource",
                "long_id": "myMasteredGroupedResource:1",
                "operation": "promote",
                "on_node": "rh7-3",
            },
        ]
        self.assertEqual(
            {
                'myMasteredGroupedResource:0': {
                    'id': 'myMasteredGroupedResource',
                    'id_for_constraint': 'myGroupMaster',
                    'long_id': 'myMasteredGroupedResource:0',
                    'start_on_node': 'rh7-1',
                 },
                'myMasteredGroupedResource:1': {
                    'id': 'myMasteredGroupedResource',
                    'id_for_constraint': 'myGroupMaster',
                    'long_id': 'myMasteredGroupedResource:1',
                    'promote_on_node': 'rh7-3',
                 },
            },
            utils.get_resources_location_from_operations(cib_dom, operations)
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
            utils.get_resources_location_from_operations(cib_dom, operations)
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
        #assertIsNone is not supported in python 2.6
        self.assertTrue(utils.dom_get_node(cib, "non-existing-node") is None)
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
            "rh7-1-utilization"
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
        nv_set = xml.dom.minidom.parseString("""
        <nv_set>
            <nvpair id="prefix-test_name" name="test_name" value="test_val"/>
            <nvpair id="prefix2-another_name" name="another_name" value="value"/>
        </nv_set>
        """).documentElement
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
        nv_set = xml.dom.minidom.parseString("""
        <nv_set>
            <nvpair id="prefix-test_name" name="test_name" value="test_val"/>
            <nvpair id="prefix2-another_name" name="another_name" value="value"/>
        </nv_set>
        """).documentElement
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
            [("key", "value"), ("key2", "val=ue"), ("k e y", " v a l u e ")]
        )

    def test_dom_update_utilization_invalid(self):
        #commands writes to stderr
        #we want clean test output, so we capture it
        tmp_stderr = sys.stderr
        sys.stderr = StringIO()

        el = xml.dom.minidom.parseString("""
        <resource id="test_id"/>
        """).documentElement
        self.assertRaises(
            SystemExit,
            utils.dom_update_utilization, el, {"name": "invalid_val"}
        )

        self.assertRaises(
            SystemExit,
            utils.dom_update_utilization, el, {"name": "0.01"}
        )

        sys.stderr = tmp_stderr

    def test_dom_update_utilization_add(self):
        el = xml.dom.minidom.parseString("""
        <resource id="test_id"/>
        """).documentElement
        utils.dom_update_utilization(
            el,
            {
                "name": "",
                "key": "-1",
                "keys": "90",
            }
        )

        self.assertEqual(len(dom_get_child_elements(el)), 1)
        u = dom_get_child_elements(el)[0]
        self.assertEqual(u.tagName, "utilization")
        self.assertEqual(u.getAttribute("id"), "test_id-utilization")
        self.assertEqual(len(dom_get_child_elements(u)), 2)

        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("id"),
            "test_id-utilization-key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("name"),
            "key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("value"),
            "-1"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("id"),
            "test_id-utilization-keys"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("name"),
            "keys"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("value"),
            "90"
        )

    def test_dom_update_utilization_update_remove(self):
        el = xml.dom.minidom.parseString("""
        <resource id="test_id">
            <utilization id="test_id-utilization">
                <nvpair id="test_id-utilization-key" name="key" value="-1"/>
                <nvpair id="test_id-utilization-keys" name="keys" value="90"/>
            </utilization>
        </resource>
        """).documentElement
        utils.dom_update_utilization(
            el,
            {
                "key": "100",
                "keys": "",
            }
        )

        u = dom_get_child_elements(el)[0]
        self.assertEqual(len(dom_get_child_elements(u)), 1)
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("id"),
            "test_id-utilization-key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("name"),
            "key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("value"),
            "100"
        )

    def test_dom_update_meta_attr_add(self):
        el = xml.dom.minidom.parseString("""
        <resource id="test_id"/>
        """).documentElement
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
            "test_id-meta_attributes-key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("name"),
            "key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("value"),
            "test"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("id"),
            "test_id-meta_attributes-key2"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("name"),
            "key2"
        )
        self.assertEqual(
            dom_get_child_elements(u)[1].getAttribute("value"),
            "val"
        )

    def test_dom_update_meta_attr_update_remove(self):
        el = xml.dom.minidom.parseString("""
        <resource id="test_id">
            <meta_attributes id="test_id-utilization">
                <nvpair id="test_id-meta_attributes-key" name="key" value="test"/>
                <nvpair id="test_id-meta_attributes-key2" name="key2" value="val"/>
            </meta_attributes>
        </resource>
        """).documentElement
        utils.dom_update_meta_attr(
            el, [("key", "another_val"), ("key2", "")]
        )

        u = dom_get_child_elements(el)[0]
        self.assertEqual(len(dom_get_child_elements(u)), 1)
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("id"),
            "test_id-meta_attributes-key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("name"),
            "key"
        )
        self.assertEqual(
            dom_get_child_elements(u)[0].getAttribute("value"),
            "another_val"
        )

    def test_get_utilization(self):
        el = xml.dom.minidom.parseString("""
        <resource id="test_id">
            <utilization id="test_id-utilization">
                <nvpair id="test_id-utilization-key" name="key" value="-1"/>
                <nvpair id="test_id-utilization-keys" name="keys" value="90"/>
            </utilization>
        </resource>
        """).documentElement
        self.assertEqual({"key": "-1", "keys": "90"}, utils.get_utilization(el))

    def test_get_utilization_str(self):
        el = xml.dom.minidom.parseString("""
        <resource id="test_id">
            <utilization id="test_id-utilization">
                <nvpair id="test_id-utilization-key" name="key" value="-1"/>
                <nvpair id="test_id-utilization-keys" name="keys" value="90"/>
            </utilization>
        </resource>
        """).documentElement
        self.assertEqual("key=-1 keys=90", utils.get_utilization_str(el))

    def test_get_cluster_property_from_xml_enum(self):
        el = ET.fromstring("""
        <parameter name="no-quorum-policy" unique="0">
            <shortdesc lang="en">What to do when the cluster does not have quorum</shortdesc>
            <content type="enum" default="stop"/>
            <longdesc lang="en">What to do when the cluster does not have quorum  Allowed values: stop, freeze, ignore, suicide</longdesc>
        </parameter>
        """)
        expected = {
            "name": "no-quorum-policy",
            "shortdesc": "What to do when the cluster does not have quorum",
            "longdesc": "",
            "type": "enum",
            "default": "stop",
            "enum": ["stop", "freeze", "ignore", "suicide"]
        }
        self.assertEqual(expected, utils.get_cluster_property_from_xml(el))

    def test_get_cluster_property_from_xml(self):
        el = ET.fromstring("""
        <parameter name="default-resource-stickiness" unique="0">
            <shortdesc lang="en"></shortdesc>
            <content type="integer" default="0"/>
            <longdesc lang="en"></longdesc>
        </parameter>
        """)
        expected = {
            "name": "default-resource-stickiness",
            "shortdesc": "",
            "longdesc": "",
            "type": "integer",
            "default": "0"
        }
        self.assertEqual(expected, utils.get_cluster_property_from_xml(el))

    def test_get_cluster_property_default(self):
        definition = {
            "default-resource-stickiness": {
                "name": "default-resource-stickiness",
                "shortdesc": "",
                "longdesc": "",
                "type": "integer",
                "default": "0",
                "source": "pengine"
            },
            "no-quorum-policy": {
                "name": "no-quorum-policy",
                "shortdesc": "What to do when the cluster does not have quorum",
                "longdesc": "What to do when the cluster does not have quorum  Allowed values: stop, freeze, ignore, suicide",
                "type": "enum",
                "default": "stop",
                "enum": ["stop", "freeze", "ignore", "suicide"],
                "source": "pengine"
            },
            "enable-acl": {
                "name": "enable-acl",
                "shortdesc": "Enable CIB ACL",
                "longdesc": "Enable CIB ACL",
                "type": "boolean",
                "default": "false",
                "source": "cib"
            }
        }
        self.assertEqual(
            utils.get_cluster_property_default(
                definition, "default-resource-stickiness"
            ),
            "0"
        )
        self.assertEqual(
            utils.get_cluster_property_default(definition, "no-quorum-policy"),
            "stop"
        )
        self.assertEqual(
            utils.get_cluster_property_default(definition, "enable-acl"),
            "false"
        )
        self.assertRaises(
            utils.UnknownPropertyException,
            utils.get_cluster_property_default, definition, "non-existing"
        )

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
            "default-resource-stickiness": {
                "name": "default-resource-stickiness",
                "shortdesc": "",
                "longdesc": "",
                "type": "integer",
                "default": "0",
                "source": "pengine"
            },
            "no-quorum-policy": {
                "name": "no-quorum-policy",
                "shortdesc": "What to do when the cluster does not have quorum",
                "longdesc": "What to do when the cluster does not have quorum  Allowed values: stop, freeze, ignore, suicide",
                "type": "enum",
                "default": "stop",
                "enum": ["stop", "freeze", "ignore", "suicide"],
                "source": "pengine"
            },
            "enable-acl": {
                "name": "enable-acl",
                "shortdesc": "Enable CIB ACL",
                "longdesc": "Enable CIB ACL",
                "type": "boolean",
                "default": "false",
                "source": "cib"
            }
        }
        self.assertTrue(utils.is_valid_cluster_property(
            definition, "default-resource-stickiness", "10"
        ))
        self.assertTrue(utils.is_valid_cluster_property(
            definition, "default-resource-stickiness", "-1"
        ))
        self.assertTrue(utils.is_valid_cluster_property(
            definition, "no-quorum-policy", "freeze"
        ))
        self.assertTrue(utils.is_valid_cluster_property(
            definition, "no-quorum-policy", "suicide"
        ))
        self.assertTrue(utils.is_valid_cluster_property(
            definition, "enable-acl", "true"
        ))
        self.assertTrue(utils.is_valid_cluster_property(
            definition, "enable-acl", "false"
        ))
        self.assertTrue(utils.is_valid_cluster_property(
            definition, "enable-acl", "on"
        ))
        self.assertTrue(utils.is_valid_cluster_property(
            definition, "enable-acl", "OFF"
        ))
        self.assertFalse(utils.is_valid_cluster_property(
            definition, "default-resource-stickiness", "test"
        ))
        self.assertFalse(utils.is_valid_cluster_property(
            definition, "default-resource-stickiness", "1.2"
        ))
        self.assertFalse(utils.is_valid_cluster_property(
            definition, "no-quorum-policy", "invalid"
        ))
        self.assertFalse(utils.is_valid_cluster_property(
            definition, "enable-acl", "not"
        ))
        self.assertRaises(
            utils.UnknownPropertyException,
            utils.is_valid_cluster_property, definition, "unknown", "value"
        )

    def assert_element_id(self, node, node_id):
        self.assertTrue(
            isinstance(node, xml.dom.minidom.Element),
            "element with id '%s' not found" % node_id
        )
        self.assertEqual(node.getAttribute("id"), node_id)


class RunParallelTest(unittest.TestCase):
    def fixture_create_worker(self, log, name, sleepSeconds=0):
        def worker():
            sleep(sleepSeconds)
            log.append(name)
        return worker

    def test_run_all_workers(self):
        log = []
        utils.run_parallel(
            [
                self.fixture_create_worker(log, 'first'),
                self.fixture_create_worker(log, 'second'),
            ],
            wait_seconds=.1
        )

        self.assertEqual(
            sorted(log),
            sorted(['first', 'second'])
        )

    def test_wait_for_slower_workers(self):
        log = []
        utils.run_parallel(
            [
                self.fixture_create_worker(log, 'first', .03),
                self.fixture_create_worker(log, 'second'),
            ],
            wait_seconds=.01
        )

        self.assertEqual(log, ['second', 'first'])


class PrepareNodeNamesTest(unittest.TestCase):
    def test_return_original_when_is_in_pacemaker_nodes(self):
        node = 'test'
        self.assertEqual(
            node,
            utils.prepare_node_name(node, {1: node}, {})
        )

    def test_return_original_when_is_not_in_corosync_nodes(self):
        node = 'test'
        self.assertEqual(
            node,
            utils.prepare_node_name(node, {}, {})
        )

    def test_return_original_when_corosync_id_not_in_pacemaker(self):
        node = 'test'
        self.assertEqual(
            node,
            utils.prepare_node_name(node, {}, {1: node})
        )

    def test_return_modified_name(self):
        node = 'test'
        self.assertEqual(
            'another (test)',
            utils.prepare_node_name(node, {1: 'another'}, {1: node})
        )

    def test_return_modified_name_with_pm_null_case(self):
        node = 'test'
        self.assertEqual(
            '*Unknown* (test)',
            utils.prepare_node_name(node, {1: '(null)'}, {1: node})
        )


class NodeActionTaskTest(unittest.TestCase):
    def test_can_run_action(self):
        def action(node, arg, kwarg=None):
            return (0, ':'.join([node, arg, kwarg]))

        report_list = []
        def report(node, returncode, output):
            report_list.append('|'.join([node, str(returncode), output]))

        task = utils.create_task(report, action, 'node', 'arg', kwarg='kwarg')
        task()

        self.assertEqual(['node|0|node:arg:kwarg'], report_list)


class ParseCmanQuorumInfoTest(unittest.TestCase):
    def test_error_empty_string(self):
        parsed = utils.parse_cman_quorum_info("")
        self.assertEqual(None, parsed)

    def test_quorate_no_qdevice(self):
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
        self.assertEqual(True, parsed["quorate"])
        self.assertEqual(2, parsed["quorum"])
        self.assertEqual(
            [
                {"name": "rh66-node1", "votes": 3, "local": False},
                {"name": "rh66-node2", "votes": 2, "local": True},
                {"name": "rh66-node3", "votes": 1, "local": False},
            ],
            parsed["node_list"]
        )
        self.assertEqual([], parsed["qdevice_list"])

    def test_no_quorate_no_qdevice(self):
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
        self.assertEqual(False, parsed["quorate"])
        self.assertEqual(2, parsed["quorum"])
        self.assertEqual(
            [
                {"name": "rh66-node1", "votes": 3, "local": True},
            ],
            parsed["node_list"]
        )
        self.assertEqual([], parsed["qdevice_list"])

    def test_error_missing_quorum(self):
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
        self.assertEqual(None, parsed)

    def test_error_quorum_garbage(self):
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
        self.assertEqual(None, parsed)

    def test_error_node_votes_garbage(self):
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
        self.assertEqual(None, parsed)


class ParseQuorumtoolOutputTest(unittest.TestCase):
    def test_error_empty_string(self):
        parsed = utils.parse_quorumtool_output("")
        self.assertEqual(None, parsed)

    def test_quorate_no_qdevice(self):
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
        self.assertEqual(True, parsed["quorate"])
        self.assertEqual(2, parsed["quorum"])
        self.assertEqual(
            [
                {"name": "rh70-node1", "votes": 3, "local": False},
                {"name": "rh70-node2", "votes": 2, "local": True},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            parsed["node_list"]
        )
        self.assertEqual([], parsed["qdevice_list"])

    def test_quorate_with_qdevice(self):
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
Expected votes:   10
Highest expected: 10
Total votes:      10
Quorum:           6
Flags:            Quorate Qdevice

Membership information
----------------------
    Nodeid      Votes    Qdevice Name
         1          3    A,V,MNW rh70-node1
         2          2    A,V,MNW rh70-node2 (local)
         3          1    A,V,MNW rh70-node3
         0          4            Qdevice
""")
        self.assertEqual(True, parsed["quorate"])
        self.assertEqual(6, parsed["quorum"])
        self.assertEqual(
            [
                {"name": "rh70-node1", "votes": 3, "local": False},
                {"name": "rh70-node2", "votes": 2, "local": True},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            parsed["node_list"]
        )
        self.assertEqual(
            [
                {"name": "Qdevice", "votes": 4, "local": False},
            ],
            parsed["qdevice_list"]
        )

    def test_quorate_with_qdevice_lost(self):
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
Expected votes:   10
Highest expected: 10
Total votes:      6
Quorum:           6
Flags:            Quorate Qdevice

Membership information
----------------------
    Nodeid      Votes    Qdevice Name
         1          3   NA,V,MNW rh70-node1
         2          2   NA,V,MNW rh70-node2 (local)
         3          1   NA,V,MNW rh70-node3
         0          0            Qdevice (votes 4)
""")
        self.assertEqual(True, parsed["quorate"])
        self.assertEqual(6, parsed["quorum"])
        self.assertEqual(
            [
                {"name": "rh70-node1", "votes": 3, "local": False},
                {"name": "rh70-node2", "votes": 2, "local": True},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            parsed["node_list"]
        )
        self.assertEqual(
            [
                {"name": "Qdevice", "votes": 0, "local": False},
            ],
            parsed["qdevice_list"]
        )

    def test_no_quorate_no_qdevice(self):
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
        self.assertEqual(False, parsed["quorate"])
        self.assertEqual(2, parsed["quorum"])
        self.assertEqual(
            [
                {"name": "rh70-node1", "votes": 1, "local": True},
            ],
            parsed["node_list"]
        )
        self.assertEqual([], parsed["qdevice_list"])

    def test_no_quorate_with_qdevice(self):
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
Flags:            Qdevice

Membership information
----------------------
    Nodeid      Votes    Qdevice Name
         1          1         NR rh70-node1 (local)
         0          0            Qdevice (votes 1)
""")
        self.assertEqual(False, parsed["quorate"])
        self.assertEqual(2, parsed["quorum"])
        self.assertEqual(
            [
                {"name": "rh70-node1", "votes": 1, "local": True},
            ],
            parsed["node_list"]
        )
        self.assertEqual(
            [
                {"name": "Qdevice", "votes": 0, "local": False},
            ],
            parsed["qdevice_list"]
        )

    def test_error_missing_quorum(self):
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
        self.assertEqual(None, parsed)

    def test_error_quorum_garbage(self):
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
        self.assertEqual(None, parsed)

    def test_error_node_votes_garbage(self):
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
        self.assertEqual(None, parsed)


class IsNodeStopCauseQuorumLossTest(unittest.TestCase):
    def test_not_quorate(self):
        quorum_info = {
            "quorate": False,
        }
        self.assertEqual(
            False,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

    def test_local_node_not_in_list(self):
        quorum_info = {
            "quorate": True,
            "quorum": 1,
            "node_list": [
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            "qdevice_list": [],
        }
        self.assertEqual(
            False,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

    def test_local_node_alone_in_list(self):
        quorum_info = {
            "quorate": True,
            "quorum": 1,
            "node_list": [
                {"name": "rh70-node3", "votes": 1, "local": True},
            ],
            "qdevice_list": [],
        }
        self.assertEqual(
            True,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

    def test_local_node_still_quorate(self):
        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": False},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": True},
            ],
            "qdevice_list": [],
        }
        self.assertEqual(
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
            "qdevice_list": [],
        }
        self.assertEqual(
            False,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

    def test_local_node_quorum_loss(self):
        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            "qdevice_list": [],
        }
        self.assertEqual(
            True,
            utils.is_node_stop_cause_quorum_loss(quorum_info, True)
        )

    def test_one_node_still_quorate(self):
        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            "qdevice_list": [],
        }
        self.assertEqual(
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
            "qdevice_list": [],
        }
        self.assertEqual(
            False,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2"]
            )
        )

    def test_one_node_quorum_loss(self):
        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            "qdevice_list": [],
        }
        self.assertEqual(
            True,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node1"]
            )
        )

    def test_more_nodes_still_quorate(self):
        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 4, "local": True},
                {"name": "rh70-node2", "votes": 1, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            "qdevice_list": [],
        }
        self.assertEqual(
            False,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2", "rh70-node3"]
            )
        )

    def test_more_nodes_quorum_loss(self):
        quorum_info = {
            "quorate": True,
            "quorum": 4,
            "node_list": [
                {"name": "rh70-node1", "votes": 3, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            "qdevice_list": [],
        }
        self.assertEqual(
            True,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2", "rh70-node3"]
            )
        )

    def test_qdevice_still_quorate(self):
        quorum_info = {
            "quorate": True,
            "quorum": 3,
            "node_list": [
                {"name": "rh70-node1", "votes": 1, "local": True},
                {"name": "rh70-node2", "votes": 1, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            "qdevice_list": [
                {"name": "Qdevice", "votes": 1, "local": False},
            ],
        }
        self.assertEqual(
            False,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2"]
            )
        )

    def test_qdevice_quorum_lost(self):
        quorum_info = {
            "quorate": True,
            "quorum": 3,
            "node_list": [
                {"name": "rh70-node1", "votes": 1, "local": True},
                {"name": "rh70-node2", "votes": 1, "local": False},
                {"name": "rh70-node3", "votes": 1, "local": False},
            ],
            "qdevice_list": [
                {"name": "Qdevice", "votes": 1, "local": False},
            ],
        }
        self.assertEqual(
            True,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2", "rh70-node3"]
            )
        )

    def test_qdevice_lost_still_quorate(self):
        quorum_info = {
            "quorate": True,
            "quorum": 4, # expect qdevice votes == 1
            "node_list": [
                {"name": "rh70-node1", "votes": 2, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 2, "local": False},
            ],
            "qdevice_list": [
                {"name": "Qdevice", "votes": 0, "local": False},
            ],
        }
        self.assertEqual(
            False,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2"]
            )
        )

    def test_qdevice_lost_quorum_lost(self):
        quorum_info = {
            "quorate": True,
            "quorum": 4, # expect qdevice votes == 1
            "node_list": [
                {"name": "rh70-node1", "votes": 2, "local": True},
                {"name": "rh70-node2", "votes": 2, "local": False},
                {"name": "rh70-node3", "votes": 2, "local": False},
            ],
            "qdevice_list": [
                {"name": "Qdevice", "votes": 0, "local": False},
            ],
        }
        self.assertEqual(
            True,
            utils.is_node_stop_cause_quorum_loss(
                quorum_info, False, ["rh70-node2", "rh70-node3"]
            )
        )
