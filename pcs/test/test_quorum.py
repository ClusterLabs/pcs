from __future__ import (
    absolute_import,
    division,
    print_function,
    unicode_literals,
)

import shutil
from unittest import TestCase

from pcs.test.tools.assertions import AssertPcsMixin
from pcs.test.tools.misc import (
    get_test_resource as rc,
)
from pcs.test.tools.pcs_runner import PcsRunner

coro_conf = rc("corosync.conf")
temp_conf = rc("corosync.conf.tmp")

class QuorumUpdateCmdTest(TestCase, AssertPcsMixin):
    def setUp(self):
        shutil.copy(coro_conf, temp_conf)
        self.pcs_runner = PcsRunner(corosync_conf_file=temp_conf)

    def test_no_options(self):
        self.assert_pcs_fail(
            "quorum update",
            stdout_start="\nUsage: pcs quorum <command>\n    update "
        )
        return

    def test_invalid_option(self):
        self.assert_pcs_fail(
            "quorum update nonsense=invalid",
            "Error: invalid quorum option 'nonsense', allowed options are: "
                + "auto_tie_breaker or last_man_standing or "
                + "last_man_standing_window or wait_for_all\n"
        )

    def test_invalid_value(self):
        self.assert_pcs_fail(
            "quorum update wait_for_all=invalid",
            "Error: 'invalid' is not a valid value for wait_for_all"
                + ", use 0 or 1\n"
        )

    def test_success(self):
        self.assert_pcs_success(
            "quorum config",
            """\
Options:
"""
        )

        self.assert_pcs_success(
            "quorum update wait_for_all=1"
        )

        self.assert_pcs_success(
            "quorum config",
            """\
Options:
 wait_for_all: 1
"""
        )
