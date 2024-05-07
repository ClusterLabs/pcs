from unittest import TestCase

from lxml import etree

from pcs_test.tools.cib import get_assert_pcs_effect_mixin
from pcs_test.tools.misc import get_test_resource as rc
from pcs_test.tools.misc import (
    get_tmp_file,
    write_data_to_tmpfile,
)
from pcs_test.tools.pcs_runner import PcsRunner
from pcs_test.tools.xml import XmlManipulation


class StonithIsForbidden(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
    ),
):
    # pylint: disable=too-many-public-methods
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file(
            "tier1_cib_resource_stonith_resource_is_forbidden"
        )
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name(
            "resources",
            """
            <primitive id="R1" class="ocf" type="Dummy" provider="pacemaker">
                <operations>
                    <op name="monitor" timeout="20s" interval="10s"
                        id="R5-monitor-interval-10s"/>
                </operations>
            </primitive>
            """,
        )
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def tearDown(self):
        self.temp_cib.close()

    def test_stonith_config(self):
        self.assert_pcs_fail(
            "stonith config R1".split(),
            stderr_full=(
                "Warning: Unable to find stonith device 'R1'\n"
                "Error: No stonith device found\n"
            ),
        )

    def test_stonith_update(self):
        self.assert_pcs_fail(
            "stonith update R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource update' instead.\n"
            ),
        )

    def test_stonith_delete(self):
        self.assert_pcs_fail(
            "stonith delete R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource delete' instead.\n"
            ),
        )

    def test_stonith_remove(self):
        self.assert_pcs_fail(
            "stonith remove R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource delete' instead.\n"
            ),
        )

    def test_stonith_op_add(self):
        self.assert_pcs_fail(
            "stonith op add R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource op add' instead.\n"
            ),
        )

    def test_stonith_op_delete(self):
        self.assert_pcs_fail(
            "stonith op delete R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource op delete' instead.\n"
            ),
        )

    def test_stonith_op_remove(self):
        self.assert_pcs_fail(
            "stonith op delete R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource op delete' instead.\n"
            ),
        )

    def test_stonith_enable(self):
        self.assert_pcs_fail(
            "stonith enable R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource enable' instead.\n"
            ),
        )

    def test_stonith_disable(self):
        self.assert_pcs_fail(
            "stonith disable R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource disable' instead.\n"
            ),
        )

    def test_stonith_level_add(self):
        self.assert_pcs_fail(
            "stonith level add 1 node1 R1".split(),
            stderr_full="Error: This command does not accept resources.\n",
        )

    def test_stonith_meta(self):
        self.assert_pcs_fail(
            "stonith meta R1".split(),
            stderr_full=(
                "Error: This command does not accept resources. "
                "Please use 'pcs resource meta' instead.\n"
            ),
        )
