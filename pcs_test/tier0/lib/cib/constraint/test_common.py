from unittest import TestCase

from lxml import etree

from pcs.common import reports
from pcs.lib.cib.constraint.common import (
    DuplicatesChecker,
    find_constraints_of_same_type,
    is_constraint,
    validate_constrainable_elements,
)

from pcs_test.tools import fixture
from pcs_test.tools.assertions import assert_report_item_list_equal
from pcs_test.tools.fixture import ReportItemFixture
from pcs_test.tools.xml import str_to_etree


class IsConstraint(TestCase):
    def test_is_constraint_true(self):
        for element in (
            etree.Element("rsc_colocation"),
            etree.Element("rsc_location"),
            etree.Element("rsc_order"),
            etree.Element("rsc_ticket"),
        ):
            with self.subTest(element=element):
                self.assertTrue(is_constraint(element))

    def test_is_constraint_false(self):
        self.assertFalse(is_constraint(etree.Element("element")))


def fixture_cib():
    res_set1 = """
        <resource_set>
            <resource_ref id="R1"/> <resource_ref id="R2"/>
        </resource_set>
    """
    res_set2 = """
        <resource_set>
            <resource_ref id="R2"/> <resource_ref id="R3"/>
        </resource_set>
    """
    res_set3 = """
        <resource_set>
            <resource_ref id="R1"/> <resource_ref id="R3"/>
        </resource_set>
    """
    return str_to_etree(
        f"""
            <constraints>
                <rsc_location id="LP1" rsc="R1" node="node1" score="1" />
                <rsc_location id="LP2" rsc="R2" node="node2" score="2" />
                <rsc_location id="LP3" rsc="R3" node="node3" score="3" />
                <rsc_location id="LS1" node="node1" score="1">{res_set1}</rsc_location>
                <rsc_location id="LS2" node="node2" score="2">{res_set2}</rsc_location>
                <rsc_location id="LS3" node="node3" score="3">{res_set3}</rsc_location>
                <rsc_colocation id="CP1" rsc="R1" with-rsc="R2" score="1" />
                <rsc_colocation id="CP2" rsc="R1" with-rsc="R3" score="1" />
                <rsc_colocation id="CP3" rsc="R2" with-rsc="R3" score="1" />
                <rsc_colocation id="CS1" score="1">{res_set1}</rsc_colocation>
                <rsc_colocation id="CS2" score="2">{res_set2}</rsc_colocation>
                <rsc_colocation id="CS3" score="3">{res_set3}</rsc_colocation>
                <rsc_order id="OP1" first="R1" then="R2" />
                <rsc_order id="OP2" first="R2" then="R3" />
                <rsc_order id="OP3" first="R1" then="R3" />
                <rsc_order id="OS1">{res_set1}</rsc_order>
                <rsc_order id="OS2">{res_set2}</rsc_order>
                <rsc_order id="OS3">{res_set3}</rsc_order>
                <rsc_ticket id="TP1" rsc="R1" ticket="T1" />
                <rsc_ticket id="TP2" rsc="R2" ticket="T2" />
                <rsc_ticket id="TP3" rsc="R3" ticket="T3" />
                <rsc_ticket id="TS1" ticket="T1">{res_set1}</rsc_ticket>
                <rsc_ticket id="TS2" ticket="T2">{res_set2}</rsc_ticket>
                <rsc_ticket id="TS3" ticket="T3">{res_set3}</rsc_ticket>
            </constraints>
        """
    )


class FindConstraintsOfSameType(TestCase):
    def test_found(self):
        cib = fixture_cib()
        for type_id in ("LP", "LS", "CP", "CS", "OP", "OS", "TP", "TS"):
            with self.subTest(constraint_type=type_id):
                element = cib.xpath(".//*[@id=$id]", id=f"{type_id}1")[0]
                self.assertEqual(
                    [
                        el.attrib["id"]
                        for el in find_constraints_of_same_type(cib, element)
                    ],
                    [f"{type_id}2", f"{type_id}3"],
                )

    def test_not_found(self):
        cib = fixture_cib()
        for element in cib.xpath("./*[not(contains(@id, '1'))]"):
            element.getparent().remove(element)

        for type_id in ("LP", "LS", "CP", "CS", "OP", "OS", "TP", "TS"):
            with self.subTest(constraint_type=type_id):
                element = cib.xpath(".//*[@id=$id]", id=f"{type_id}1")[0]
                self.assertEqual(
                    [
                        el.attrib["id"]
                        for el in find_constraints_of_same_type(cib, element)
                    ],
                    [],
                )


class DuplicatesCheckerTestBase(TestCase):
    def assert_success(self, cib, checker, duplicates):
        for id_to_check, id_results in duplicates.items():
            for forced in (False, True):
                with self.subTest(id_to_check=id_to_check, forced=forced):
                    real_reports = checker.check(
                        cib,
                        cib.xpath(".//*[@id=$id]", id=f"{id_to_check}")[0],
                        force_flags=([reports.codes.FORCE] if forced else []),
                    )
                    expected_reports = []
                    if id_results:
                        if forced:
                            expected_reports = [
                                fixture.warn(
                                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                                    constraint_ids=id_results,
                                )
                            ]
                        else:
                            expected_reports = [
                                fixture.error(
                                    reports.codes.DUPLICATE_CONSTRAINTS_EXIST,
                                    force_code=reports.codes.FORCE,
                                    constraint_ids=id_results,
                                )
                            ]
                    assert_report_item_list_equal(
                        real_reports, expected_reports
                    )


class DuplicatesCheckerTest(DuplicatesCheckerTestBase):
    class MockChecker(DuplicatesChecker):
        def _are_duplicate(self, constraint_to_check, constraint_el):
            return (
                int(constraint_to_check.attrib["id"][-1]) % 2
                == int(constraint_el.attrib["id"][-1]) % 2
            )

    def test_success(self):
        cib = fixture_cib()
        duplicates = {
            "LP1": ["LP3"],
            "LP2": [],
            "LP3": ["LP1"],
            "LS1": ["LS3"],
            "LS2": [],
            "LS3": ["LS1"],
            "CP1": ["CP3"],
            "CP2": [],
            "CP3": ["CP1"],
            "CS1": ["CS3"],
            "CS2": [],
            "CS3": ["CS1"],
            "OP1": ["OP3"],
            "OP2": [],
            "OP3": ["OP1"],
            "OS1": ["OS3"],
            "OS2": [],
            "OS3": ["OS1"],
            "TP1": ["TP3"],
            "TP2": [],
            "TP3": ["TP1"],
            "TS1": ["TS3"],
            "TS2": [],
            "TS3": ["TS1"],
        }
        checker = self.MockChecker()
        self.assert_success(cib, checker, duplicates)


class ValidateConstrainableElement(TestCase):
    _cib = str_to_etree(
        """
            <resources>
              <bundle id="B">
                <docker image="pcs:test" />
                <primitive id="B_R" class="ocf" type="Dummy" provider="pacemaker" />
              </bundle>
              <group id="G">
                <primitive id="G_R1" class="ocf" type="Dummy" provider="pacemaker" />
                <primitive id="G_R2" class="ocf" type="Dummy" provider="pacemaker" />
              </group>
              <clone id="C1">
                <group id="C1_G">
                  <primitive id="C1_G_R1" class="ocf" type="Stateful" provider="pacemaker" />
                  <primitive id="C1_G_R2" class="ocf" type="Stateful" provider="pacemaker" />
                </group>
              </clone>
              <clone id="C2">
                <primitive id="C2_R" class="ocf" type="Dummy" provider="pacemaker" />
              </clone>
              <primitive id="R" class="ocf" type="Dummy" provider="pacemaker" />
            </resources>
        """
    )

    def test_no_report(self):
        id_map = {
            "R": "primitive",
            "G_R1": "primitive in a group",
            "G": "group",
            "C1": "clone",
            "B": "bundle",
        }
        for res_id, res_desc in id_map.items():
            with self.subTest(
                resource_id=res_id, resource_description=res_desc
            ):
                assert_report_item_list_equal(
                    validate_constrainable_elements(
                        self._cib.xpath("//*[@id=$id]", id=res_id)
                    ),
                    [],
                )

    def _test_report(self, in_multiinstance_allowed, severity, force_code):
        id_map = {
            "B_R": "primitive in a bundle",
            "C1_G": "group in a clone",
            "C1_G_R1": "primitive in a group in a clone",
            "C2_R": "primitive in a clone",
        }
        for res_id, res_desc in id_map.items():
            with self.subTest(
                resource_id=res_id, resource_description=res_desc
            ):
                assert_report_item_list_equal(
                    validate_constrainable_elements(
                        self._cib.xpath("//*[@id=$id]", id=res_id),
                        in_multiinstance_allowed,
                    ),
                    [
                        ReportItemFixture(
                            severity,
                            reports.codes.RESOURCE_FOR_CONSTRAINT_IS_MULTIINSTANCE,
                            dict(
                                resource_id=res_id,
                                parent_type=(
                                    "bundle" if res_id == "B_R" else "clone"
                                ),
                                parent_id=res_id.split("_", 1)[0],
                            ),
                            force_code,
                            context=None,
                        )
                    ],
                )

    def test_error(self):
        self._test_report(
            False, reports.ReportItemSeverity.ERROR, reports.codes.FORCE
        )

    def test_warning(self):
        self._test_report(True, reports.ReportItemSeverity.WARNING, None)
