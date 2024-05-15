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


class ResourceStonithIsForbidden(
    TestCase,
    get_assert_pcs_effect_mixin(
        lambda cib: etree.tostring(etree.parse(cib).findall(".//resources")[0])
    ),
):
    # pylint: disable=too-many-public-methods
    empty_cib = rc("cib-empty.xml")

    def setUp(self):
        self.temp_cib = get_tmp_file(
            "tier1_cib_resource_resource_stonith_is_forbidden"
        )
        self.pcs_runner = PcsRunner(self.temp_cib.name)
        xml_manip = XmlManipulation.from_file(self.empty_cib)
        xml_manip.append_to_first_tag_name(
            "resources",
            """
            <primitive id="S1" class="stonith" type="fence_kdump">
                <operations>
                    <op name="monitor" interval="60s"
                        id="S1-monitor-interval-60s"/>
                </operations>
            </primitive>
            """,
        )
        write_data_to_tmpfile(str(xml_manip), self.temp_cib)

    def tearDown(self):
        self.temp_cib.close()

    def test_rsc_config(self):
        self.assert_pcs_fail(
            "resource config S1".split(),
            stderr_full=(
                "Warning: Unable to find resource 'S1'\n"
                "Error: No resource found\n"
            ),
        )

    def test_rsc_create(self):
        self.assert_pcs_fail(
            "resource create S1 stonith:fence_xvm".split(),
            stderr_full=(
                "Error: This command does not accept stonith resource. "
                "Use 'pcs stonith create' command instead.\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_rsc_create_in_bundle(self):
        self.assert_pcs_fail(
            "resource create S1 stonith:fence_xvm bundle B".split(),
            stderr_full=(
                "Error: This command does not accept stonith resource. "
                "Use 'pcs stonith create' command instead.\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_rsc_create_in_clone(self):
        self.assert_pcs_fail(
            "resource create S1 stonith:fence_xvm clone".split(),
            stderr_full=(
                "Error: This command does not accept stonith resource. "
                "Use 'pcs stonith create' command instead.\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_rsc_create_in_group(self):
        self.assert_pcs_fail(
            "resource create S1 stonith:fence_xvm group G --future".split(),
            stderr_full=(
                "Error: This command does not accept stonith resource. "
                "Use 'pcs stonith create' command instead.\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_rsc_delete(self):
        self.assert_pcs_fail(
            "resource delete S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith delete' instead.\n"
            ),
        )

    def test_rsc_remove(self):
        self.assert_pcs_fail(
            "resource remove S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith delete' instead.\n"
            ),
        )

    def test_rsc_enable(self):
        self.assert_pcs_fail(
            "resource enable S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith enable' instead.\n"
            ),
        )

    def test_rsc_disable(self):
        self.assert_pcs_fail(
            "resource disable S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith disable' instead.\n"
            ),
        )

    def test_rsc_move_with_constraint(self):
        self.assert_pcs_fail(
            "resource move-with-constraint S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resource.\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_rsc_ban(self):
        self.assert_pcs_fail(
            "resource ban S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resource.\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_rsc_clear(self):
        self.assert_pcs_fail(
            "resource clear S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resource.\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_rsc_update(self):
        self.assert_pcs_fail(
            "resource update S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith update' instead.\n"
            ),
        )

    def test_rsc_op_add(self):
        self.assert_pcs_fail(
            "resource op add S1 monitor timeout=30".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith op add' instead.\n"
            ),
        )

    def test_rsc_op_delete(self):
        self.assert_pcs_fail(
            "resource op delete S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith op delete' instead.\n"
            ),
        )

    def test_rsc_op_remove(self):
        self.assert_pcs_fail(
            "resource op remove S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith op delete' instead.\n"
            ),
        )

    def test_rsc_meta(self):
        self.assert_pcs_fail(
            "resource meta S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources. "
                "Please use 'pcs stonith meta' instead.\n"
            ),
        )

    def test_rsc_group_add(self):
        self.assert_pcs_fail(
            "resource group add G S1".split(),
            stderr_full=(
                "Error: 'S1' is a stonith resource, stonith resources cannot be put into a group\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )

    def test_rsc_clone(self):
        self.assert_pcs_fail(
            "resource clone S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources.\n"
            ),
        )

    def test_rsc_promotable(self):
        self.assert_pcs_fail(
            "resource promotable S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources.\n"
            ),
        )

    def test_rsc_manage(self):
        self.assert_pcs_fail(
            "resource manage S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources.\n"
            ),
        )

    def test_rsc_unmanage(self):
        self.assert_pcs_fail(
            "resource unmanage S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources.\n"
            ),
        )

    def test_rsc_relocate_dry_run(self):
        self.assert_pcs_fail(
            "resource relocate dry-run S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources.\n"
            ),
        )

    def test_rsc_utilization(self):
        self.assert_pcs_fail(
            "resource utilization S1 test1=10".split(),
            stderr_full=(
                "Error: This command does not accept stonith resources.\n"
            ),
        )

    def test_rsc_relations(self):
        self.assert_pcs_fail(
            "resource relations S1".split(),
            stderr_full=(
                "Error: This command does not accept stonith resource.\n"
                "Error: Errors have occurred, therefore pcs is unable to continue\n"
            ),
        )
