from unittest import TestCase

from pcs_test.tools.assertions import AssertPcsMixin
from pcs_test.tools.misc import get_test_resource
from pcs_test.tools.pcs_runner import PcsRunner


class ClusterRename(AssertPcsMixin, TestCase):
    def setUp(self):
        self.pcs_runner = PcsRunner(None)

    def test_no_args(self):
        self.assert_pcs_fail(
            ["cluster", "rename"],
            stderr_start="\nUsage: pcs cluster rename...\n",
        )

    def test_too_many_args(self):
        self.assert_pcs_fail(
            ["cluster", "rename", "A", "B"],
            stderr_start="\nUsage: pcs cluster rename...\n",
        )

    def test_not_live_pcmk(self):
        self.pcs_runner = PcsRunner(cib_file=get_test_resource("cib-empty.xml"))
        self.assert_pcs_fail(
            ["cluster", "rename", "A"],
            stderr_full=(
                "Error: Specified option '-f' is not supported in this "
                "command\n"
            ),
        )

    def test_not_live_corosync(self):
        self.pcs_runner = PcsRunner(
            cib_file=None,
            corosync_conf_opt=get_test_resource("corosync_conf"),
        )
        self.assert_pcs_fail(
            ["cluster", "rename", "A"],
            stderr_full=(
                "Error: Specified option '--corosync_conf' is not supported in "
                "this command\n"
            ),
        )
