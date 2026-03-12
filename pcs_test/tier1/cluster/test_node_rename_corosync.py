from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import get_test_resource
from pcs_test.tools.pcs_runner import PcsRunner


class NodeRenameCorosync(AssertPcsMixin, TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(cib_file=None)

    def test_usage_error_no_args(self):
        self.assert_pcs_fail(
            ["cluster", "node", "rename-corosync"],
            stderr_start="\nUsage: pcs cluster",
        )

    def test_usage_error_one_arg(self):
        self.assert_pcs_fail(
            ["cluster", "node", "rename-corosync", "node1"],
            stderr_start="\nUsage: pcs cluster",
        )

    def test_usage_error_too_many_args(self):
        self.assert_pcs_fail(
            ["cluster", "node", "rename-corosync", "a", "b", "c"],
            stderr_start="\nUsage: pcs cluster",
        )

    def test_not_live_corosync(self):
        self.pcs_runner = PcsRunner(
            cib_file=None,
            corosync_conf_opt=get_test_resource("corosync_conf"),
        )
        self.assert_pcs_fail(
            ["cluster", "node", "rename-corosync", "old", "new"],
            stderr_full=(
                "Error: Specified option '--corosync_conf' is not supported "
                "in this command\n"
            ),
        )
