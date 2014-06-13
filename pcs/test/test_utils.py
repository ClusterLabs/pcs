import os
import sys
import unittest
import xml.dom.minidom
parentdir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, parentdir)
import utils

class UtilsTest(unittest.TestCase):
    def testDomGetResources(self):
        def assert_element_id(node, node_id):
            self.assertTrue(
                isinstance(node, xml.dom.minidom.Element),
                "element with id '%s' not found" % node_id
            )
            self.assertEquals(node.getAttribute("id"), node_id)

        def test_dom_get(method, dom, ok_ids, bad_ids):
            for element_id in ok_ids:
                assert_element_id(method(dom, element_id), element_id)
            for element_id in bad_ids:
                self.assertFalse(method(dom, element_id))

        cib_dom = xml.dom.minidom.parse("empty.xml")
        self.assertFalse(utils.dom_get_resource(cib_dom, "myResource"))
        self.assertFalse(
            utils.dom_get_resource_clone(cib_dom, "myClonedResource")
        )
        self.assertFalse(
            utils.dom_get_resource_masterslave(cib_dom, "myMasteredResource")
        )
        self.assertFalse(utils.dom_get_group(cib_dom, "myGroup"))
        self.assertFalse(utils.dom_get_group_clone(cib_dom, "myClonedGroup"))
        self.assertFalse(utils.dom_get_clone(cib_dom, "myClone"))
        self.assertFalse(utils.dom_get_master(cib_dom, "myMaster"))
        self.assertFalse(utils.dom_get_clone_ms_resource(cib_dom, "myClone"))
        self.assertFalse(utils.dom_get_clone_ms_resource(cib_dom, "myMaster"))

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

        master_ids = set(["myMaster", "myGroupMaster"])
        test_dom_get(
            utils.dom_get_master, cib_dom,
            master_ids, all_ids - master_ids
        )


        assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myClone"),
            "myClonedResource"
        )
        assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myGroupClone"),
            "myClonedGroup"
        )
        assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myMaster"),
            "myMasteredResource"
        )
        assert_element_id(
            utils.dom_get_clone_ms_resource(cib_dom, "myGroupMaster"),
            "myMasteredGroup"
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

if __name__ == "__main__":
    unittest.main()
