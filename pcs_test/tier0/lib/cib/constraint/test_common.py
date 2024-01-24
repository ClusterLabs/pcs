from unittest import TestCase

from pcs.common import reports
from pcs.lib.cib.constraint.common import validate_resource_id

from pcs_test.tools.assertions import assert_report_item_list_equal
from pcs_test.tools.fixture import ReportItemFixture
from pcs_test.tools.xml import str_to_etree


class ValidateResourceId(TestCase):
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
                    validate_resource_id(self._cib, res_id),
                    [],
                )

    def _test_report(self, in_clone_allowed, severity, force_code):
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
                    validate_resource_id(self._cib, res_id, in_clone_allowed),
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
